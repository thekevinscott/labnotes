import { expect, mock, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

const lines = (...events: object[]) => events.map(event => JSON.stringify(event) + '\n').join('')

const PROPS = {
  title: 'labnotes',
  isFocused: false,
  bodyColumns: 80,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
}

// An open labnotes status stream holds each act of the kit for about half a second.
const SLOW = { timeoutMs: 30000 }

const PLANNED = {
  event: 'planned',
  experiment: 'exp',
  title: 'Exp',
  concurrency: 1,
  mode: 'fill',
  runs: [
    { run: 's/a-1', params: { m: 'a' } },
    { run: 's/b-2', params: { m: 'b' } },
  ],
}

type Started = {
  spawned: { argv: readonly string[]; cwd?: string }[]
  ran: (readonly string[])[]
  toasts: string[]
  tools: string[]
  send: (text: string) => void
  tail: string[]
  opened: string[]
  isPlaced: boolean
  settle: () => Promise<void>
}

const queue = () => {
  const waiting: string[] = []
  let wake = () => {}
  return {
    push: (text: string) => {
      waiting.push(text)
      wake()
    },
    async *drain(signal: AbortSignal) {
      while (!signal.aborted) {
        while (waiting.length > 0) yield waiting.shift() as string
        await new Promise<void>(resolve => {
          wake = resolve
          signal.addEventListener('abort', () => resolve())
        })
      }
    },
  }
}

const start = async (
  $: Engine,
  on: On,
  control = { exitCode: 0, stderr: '' },
): Promise<Started> => {
  const clock = mock.clock(on, { now: 1000 })
  const started: Started = {
    spawned: [],
    ran: [],
    toasts: [],
    tools: [],
    send: () => {},
    tail: [],
    opened: [],
    isPlaced: true,
    settle: clock.settle,
  }
  const status = queue()
  started.send = status.push
  on('session.start', async (_, e) => ({ cwd: e.cwd }))
  on('tool.register', async (_, e) => {
    started.tools.push(e.name)
    return { value: { tool: e.name } }
  })
  on('ui.toast', async (_, e) => {
    started.toasts.push(e.text)
    return { value: undefined }
  })
  on('ui.open', async (_, e) => {
    started.opened.push(e.id)
    return {
      value: started.isPlaced ? { isPlaced: true as const } : { isPlaced: false as const, reason: 'too narrow' },
    }
  })
  on('process.run', async (_, e) => {
    started.ran.push(e.argv)
    return { value: { ...control, stdout: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('process.spawn', async function* (_, e, next) {
    started.spawned.push({ argv: e.argv, cwd: e.cwd })
    if (e.argv[0] === 'tail') {
      for (const text of started.tail) yield { stream: 'stdout' as const, text }
      return { value: { code: 0, signal: null } }
    }
    yield { stream: 'stderr' as const, text: 'warning\n' }
    for await (const text of status.drain(next.signal)) yield { stream: 'stdout' as const, text }
    return { value: { code: 0, signal: null } }
  })
  await $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })
  return started
}

const mountPane = async ($: Engine) =>
  $.ui.mount({ plugin: 'labnotes', surface: 'terminal', component: 'Pane', requestId: 'labnotes', props: PROPS })

const shown = async (pane: Awaited<ReturnType<typeof mountPane>>) =>
  (await pane.findAll({ type: 'Text', in: 'runs' })).map(found => found.text).join('\n')

test('follows labnotes status, registers its tool and says when runs finish', SLOW, async ($, on) => {
  const started = await start($, on)
  expect(started.tools).toEqual(['show_runs'])
  expect(started.spawned).toEqual([{ argv: ['uvx', 'labnotes', 'run', 'status', '--follow', '--json'] }])

  const text = lines(
    PLANNED,
    { event: 'started', experiment: 'exp', run: 's/a-1', params: { m: 'a' }, folder: '/r/a' },
    { event: 'ended', experiment: 'exp', run: 's/b-2', exit_code: 2, error: null },
  )
  started.send(text.slice(0, 40))
  started.send(text.slice(40) + 'noise\n')
  await started.settle()
  const pane = await mountPane($)
  const drawn = await shown(pane)
  expect(drawn).toContain('Exp')
  expect(drawn).toContain('1 at a time')
  expect(drawn).toContain('a-1')
  expect(drawn).toContain('--m b')
  expect(drawn).toContain('✗ exited 2')
  expect(started.toasts).toEqual([])

  started.send(lines({ event: 'idle', experiment: 'exp' }, { event: 'done', experiment: 'exp', error: null }))
  await started.settle()
  expect(started.toasts).toEqual(['exp finished, 0 passed, 1 failed.'])
})

test('opens the pane from its tool, saying when it cannot show it', SLOW, async ($, on) => {
  const started = await start($, on)
  const call = { tool: 'mcp__labnotes__show_runs' as const, tool_use_id: 't1', input: {} }
  expect(await $.tool.call(call)).toMatchObject({ text: 'labnotes pane opened. Click it to use its keys.' })
  started.isPlaced = false
  expect(await $.tool.call(call)).toMatchObject({ text: 'labnotes pane opened but not shown: too narrow' })
  expect(started.opened).toEqual(['labnotes', 'labnotes'])
})

test('sends controls through the labnotes CLI and says when one is refused', SLOW, async ($, on) => {
  const started = await start($, on, { exitCode: 1, stderr: 'Usage...\nError: No retry for exp.\n' })
  started.send(lines(PLANNED))
  await started.settle()
  const pane = await mountPane($)
  await pane.post({ controls: [{ experiment: 'exp', action: 'kill', args: ['s/a-1'] }] })
  await started.settle()
  expect(started.ran).toEqual([['uvx', 'labnotes', 'run', 'control', 'exp', 'kill', 's/a-1']])
  expect(started.toasts).toEqual(['Error: No retry for exp.'])
})

test('follows a run’s output once it has a folder, and stops on leaving', SLOW, async ($, on) => {
  const started = await start($, on)
  started.send(lines(PLANNED))
  await started.settle()
  const pane = await mountPane($)

  await pane.post({ view: 's/b-2' })
  expect(started.spawned).toHaveLength(1)
  expect(await shown(pane)).toContain('s/b-2')

  started.tail.push('\x1b[1mhello\x1b[0m\nwor', 'ld\n')
  started.send(lines({ event: 'started', experiment: 'exp', run: 's/b-2', params: { m: 'b' }, folder: '/r/b' }))
  await started.settle()
  expect(started.spawned[1]).toEqual({
    argv: ['tail', '-q', '-n', '500', '-F', 'stdout.log', 'stderr.log'],
    cwd: '/r/b',
  })
  expect(await shown(pane)).toContain('hello')
  expect(await shown(pane)).toContain('world')

  await pane.post({ leave: true })
  await started.settle()
  expect(await shown(pane)).toContain('--m a')

  await pane.post({ view: 's/b-2' })
  await started.settle()
  expect(started.spawned).toHaveLength(3)
})

test('opens a lone adhoc run straight into its output', SLOW, async ($, on) => {
  const started = await start($, on)
  started.send(
    lines(
      { ...PLANNED, mode: 'adhoc', runs: [{ run: 's/c-3', params: {} }] },
      { event: 'started', experiment: 'exp', run: 's/c-3', params: {}, folder: '/r/c' },
    ),
  )
  await started.settle()
  expect(started.spawned[1]?.cwd).toBe('/r/c')
  const pane = await mountPane($)
  expect(await shown(pane)).toContain('q back')
})

test('says when nothing has run, and where it cannot draw', SLOW, async ($, on) => {
  await start($, on)
  const pane = await mountPane($)
  expect(await shown(pane)).toContain('No labnotes runs yet.')
  const phone = await $.ui.mount({
    plugin: 'labnotes',
    surface: 'mobile',
    component: 'Pane',
    requestId: 'labnotes',
    props: PROPS,
  })
  expect((await phone.find({ type: 'Text' }))?.text).toBe('The labnotes pane needs a terminal.')
})

