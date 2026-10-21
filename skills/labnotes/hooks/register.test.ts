import { expect, test } from 'claude-code/testing'

const lines = (...events: object[]) => events.map(event => JSON.stringify(event) + '\n').join('')

const PROPS = {
  title: 'labnotes',
  isFocused: false,
  bodyColumns: 80,
  placement: 'dock' as const,
  scroll: { offset: 0, bodyRows: 20 },
  view: {},
}

const STATUS = lines(
  {
    event: 'planned',
    experiment: 'exp',
    runs: [
      { run: 's/a-1', params: { m: 'a' } },
      { run: 's/b-2', params: { m: 'b' } },
    ],
  },
  { event: 'started', experiment: 'exp', run: 's/a-1' },
  { event: 'output', experiment: 'exp', run: 's/a-1', stream: 'stdout', line: 'tick 3' },
  { event: 'ended', experiment: 'exp', run: 's/b-2', exit_code: 2, error: null },
)
const DONE = lines({ event: 'done', experiment: 'exp', error: null })

test('follows labnotes status, shows it in a pane and says when runs finish', async ($, on) => {
  const spawned: (readonly string[])[] = []
  const toasts: string[] = []
  const opened: string[] = []
  let finish = () => {}
  const finished = new Promise<void>(resolve => {
    finish = resolve
  })
  let resume = () => {}
  const paused = new Promise<void>(resolve => {
    resume = resolve
  })

  const registered: string[] = []
  on('session.start', async (_, e) => ({ cwd: e.cwd }))
  on('command.register', async (_, e) => {
    registered.push(e.name)
    return { value: { command: e.name } }
  })
  on('ui.open', async (_, e) => {
    opened.push(e.id)
    return { value: { isPlaced: true as const } }
  })
  on('ui.toast', async (_, e) => {
    toasts.push(e.text)
    finish()
    return { value: undefined }
  })
  on('process.spawn', async function* (_, e) {
    spawned.push(e.argv)
    yield { stream: 'stderr' as const, text: 'warning\n' }
    yield { stream: 'stdout' as const, text: STATUS.slice(0, 40) }
    yield { stream: 'stdout' as const, text: STATUS.slice(40) + 'noise\n' }
    await paused
    yield { stream: 'stdout' as const, text: DONE }
    return { value: { code: 0, signal: null } }
  })

  await $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })
  expect(registered).toEqual(['labnotes-runs'])
  expect(spawned).toEqual([['uvx', 'labnotes', 'run', 'status', '--follow', '--json']])

  const ran = await $.command.run({ command: 'labnotes-runs', args: '', origin: { kind: 'composer' },
    presentation: { isFullscreen: false, columns: 80 },
  })
  expect(ran).toEqual({ text: 'labnotes pane opened.' })
  expect(opened).toEqual(['labnotes'])

    const pane = await $.ui.mount({
    plugin: 'labnotes',
    surface: 'terminal',
    component: 'Pane',
    requestId: 'labnotes',
    props: PROPS,
  })
  const drawn = (await pane.findAll({ type: 'Text' })).map(found => found.text).join('\n')
  expect(drawn).toContain('exp running')
  expect(drawn).toContain('a-1 m=a tick 3')
  expect(drawn).toContain('b-2 m=b')
  expect(drawn).toContain('failed')
  expect(toasts).toEqual([])

  resume()
  await finished
  expect(toasts).toEqual(['exp finished, 0 passed, 1 failed.'])
})

test('says when nothing has run', async ($, on) => {
  on('session.start', async (_, e) => ({ cwd: e.cwd }))
  on('command.register', async (_, e) => ({ value: { command: e.name } }))
  on('process.spawn', async function* () {
    return { value: { code: 1, signal: null } }
  })
  await $.session.start({ cwd: '/p', surface: 'terminal', isInteractive: true })

  for (const surface of ['terminal', 'desktop'] as const) {
    const pane = await $.ui.mount({
      plugin: 'labnotes',
      surface,
      component: 'Pane',
      requestId: 'labnotes',
      props: PROPS,
    })
    expect((await pane.find({ type: 'Text', text: 'No labnotes runs yet.' }))?.text).toBe(
      'No labnotes runs yet.',
    )
  }
})
