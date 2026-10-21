import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { PaneMessage } from './pane'
import type { Log } from '../types'
import { applyBlock, applyEvent, cleanLine, describeDone, parseEvent, splitLines } from './runs'
import type { LabnotesEvent } from './runs'

const PANE = 'labnotes'
const TOOL = 'show_runs'
const NOT_OPENED = 'The labnotes pane could not open.'
const STATUS = ['uvx', 'labnotes', 'run', 'status', '--follow', '--json']
const CONTROL = ['uvx', 'labnotes', 'run', 'control']
const TAIL = ['tail', '-q', '-n', '500', '-F', 'stdout.log', 'stderr.log']
const BLOCK_TAIL = ['tail', '-n', '+1', '-F', 'log.jsonl']
const LOG_LINES = 200
const experiments = atom({ plugin: 'labnotes', key: 'experiments' } as const, [])
const log = atom({ plugin: 'labnotes', key: 'log' } as const, null)

const isLoneAdhoc = (event: LabnotesEvent) =>
  event.event === 'planned' && event.mode === 'adhoc' && (event.runs as unknown[]).length === 1

let stopTail = () => {}

const follow = ($: EngineInterface, run: string, folder: string) => {
  stopTail()
  const tail = $.process.spawn({ argv: TAIL, cwd: folder })
  const blockTail = $.process.spawn({ argv: BLOCK_TAIL, cwd: folder })
  stopTail = () => {
    void tail.return(undefined as never)
    void blockTail.return(undefined as never)
  }
  const read = async (from: typeof tail, add: (now: Log, lines: string[]) => Log) => {
    let held = ''
    for await (const { stream, text } of from) {
      if (stream !== 'stdout') continue
      const [lines, rest] = splitLines(held, text)
      held = rest
      await update($, log, now => (now?.run === run ? add(now, lines) : now))
    }
  }
  void (async () => {
    await update($, log, now => (now?.run === run ? { run, lines: [], blocks: [] } : now))
    await Promise.all([
      read(tail, (now, lines) => ({ ...now, lines: [...now.lines, ...lines.map(cleanLine)].slice(-LOG_LINES) })),
      read(blockTail, (now, lines) => ({ ...now, blocks: lines.reduce(applyBlock, now.blocks).slice(-LOG_LINES) })),
    ])
  })().catch(() => {})
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const started = await next(e)
    await $.tool.register({
      name: TOOL,
      description:
        "Open the labnotes pane: a live table of this project's runs, with keys to steer them (the same view as the terminal's `labnotes experiments NAME run`). Call it after starting runs, or when the person asks to watch them.",
    })
    void (async () => {
      let held = ''
      for await (const { stream, text } of $.process.spawn({ argv: STATUS })) {
        if (stream !== 'stdout') continue
        const [lines, rest] = splitLines(held, text)
        held = rest
        for (const line of lines) {
          const event = parseEvent(line)
          if (event === undefined) continue
          let said: string | undefined
          const now = await $.clock.now()
          await update($, experiments, list => {
            const changed = applyEvent(list, event, now)
            said = describeDone(changed, event)
            return changed
          })
          if (said !== undefined) $.ui.toast(said, { timeoutMs: 10000 })
          if (isLoneAdhoc(event)) {
            const [only] = event.runs as { run: string }[]
            stopTail()
            await update($, log, () => ({ run: only?.run ?? '', lines: [], blocks: [] }))
          }
          const viewing = await read($, log)
          if (event.event === 'started' && viewing?.run === event.run) {
            follow($, String(event.run), String(event.folder))
          }
        }
      }
    })().catch(() => {})
    return started
  })

  on('tool.call', { tool: 'mcp__labnotes__show_runs' }, async $ => {
    const opened = await $.ui.open({ id: PANE, title: 'labnotes' })
    const said = opened.isPlaced
      ? 'labnotes pane opened. Click it to use its keys.'
      : `labnotes pane opened but not shown: ${opened.reason}`
    return { result: said, text: said }
  }).catch(() => ({ result: NOT_OPENED, text: NOT_OPENED, isError: true as const }))

  on('ui.message', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const message = e.data as PaneMessage
    if ('leave' in message) {
      stopTail()
      await update($, log, () => null)
    } else if ('view' in message) {
      const run = message.view
      await update($, log, () => ({ run, lines: [], blocks: [] }))
      const folder = (await read($, experiments)).flatMap(one => one.rows).find(row => row.run === run)?.folder
      if (folder === undefined) stopTail()
      else follow($, run, folder)
    } else {
      void (async () => {
        for (const { experiment, action, args } of message.controls) {
          const { exitCode, stderr } = await $.process.run([...CONTROL, experiment, action, ...args])
          const reason = stderr.trim().split('\n').pop()
          if (exitCode !== 0) $.ui.toast(reason || `labnotes run control ${action} failed.`, { timeoutMs: 10000 })
        }
      })().catch(() => {})
    }
    return {}
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    if (e.surface !== 'terminal' && e.surface !== 'desktop') {
      const { Text } = $.ui.resolve(e)
      return <Text>The labnotes pane needs a terminal.</Text>
    }
    const { Client } = $.ui.resolve(e)
    const props = { experiments: await read($, experiments), log: await read($, log), rows: e.props.scroll.bodyRows }
    return <Client key="runs" module="./pane.tsx" props={props} flexGrow={1} />
  })
}
