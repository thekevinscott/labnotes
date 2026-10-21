import { mock } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

export const lines = (...events: object[]) => events.map(event => JSON.stringify(event) + '\n').join('')

export const PROPS = {
  title: 'labnotes',
  isFocused: false,
  bodyColumns: 80,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
}

// An open labnotes status stream holds each act of the kit for about half a second.
export const SLOW = { timeoutMs: 30000 }

export const PLANNED = {
  event: 'planned',
  experiment: 'exp',
  title: 'Exp',
  concurrency: 1,
  mode: 'matrix',
  runs: [
    { run: 's/a-1', params: { m: 'a' } },
    { run: 's/b-2', params: { m: 'b' } },
  ],
}

export type Started = {
  spawned: { argv: readonly string[]; cwd?: string }[]
  ran: (readonly string[])[]
  toasts: string[]
  tools: string[]
  send: (text: string) => void
  tail: string[]
  blockTail: string[]
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

export const start = async (
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
    blockTail: [],
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
      const texts = e.argv.includes('log.jsonl') ? started.blockTail : started.tail
      for (const text of texts) yield { stream: 'stdout' as const, text }
      return { value: { code: 0, signal: null } }
    }
    yield { stream: 'stderr' as const, text: 'warning\n' }
    for await (const text of status.drain(next.signal)) yield { stream: 'stdout' as const, text }
    return { value: { code: 0, signal: null } }
  })
  await $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })
  return started
}

export const mountPane = async ($: Engine) =>
  $.ui.mount({ plugin: 'labnotes', surface: 'terminal', component: 'Pane', requestId: 'labnotes', props: PROPS })

export const shown = async (pane: Awaited<ReturnType<typeof mountPane>>) =>
  (await pane.findAll({ type: 'Text', in: 'runs' })).map(found => found.text).join('\n')
