import { expect, test } from 'claude-code/testing'

import { PLANNED, PROPS, SLOW, lines, mountPane, shown, start } from './harness'

test('follows labnotes status, registers its tool and says when runs finish', SLOW, async ($, on) => {
  const started = await start($, on)
  expect(started.tools).toEqual(['show_runs'])
  expect(started.commands).toEqual(['labnotes-runs'])
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

test('opens the pane from /labnotes-runs, with no model turn', SLOW, async ($, on) => {
  const started = await start($, on)
  expect(await $.command.run({ command: 'labnotes-runs', args: '' })).toMatchObject({
    text: 'labnotes pane opened. Click it to use its keys.',
  })
  started.isPlaced = false
  expect(await $.command.run({ command: 'labnotes-runs', args: '' })).toMatchObject({
    text: 'labnotes pane opened but not shown: too narrow',
  })
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
  expect(started.spawned[2]).toEqual({ argv: ['tail', '-n', '+1', '-F', 'log.jsonl'], cwd: '/r/b' })
  expect(await shown(pane)).toContain('hello')
  expect(await shown(pane)).toContain('world')

  await pane.post({ leave: true })
  await started.settle()
  expect(await shown(pane)).toContain('--m a')

  await pane.post({ view: 's/b-2' })
  await started.settle()
  expect(started.spawned).toHaveLength(5)
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

