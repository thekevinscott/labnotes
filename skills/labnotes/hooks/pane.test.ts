import { expect, test } from 'claude-code/testing'
import type { Engine } from 'claude-code/testing'
import type { On } from 'claude-code'

import { PLANNED, SLOW, lines, mountPane, shown, start } from './harness'

const CONTROL = ['uvx', 'labnotes', 'run', 'control', 'exp']

const THREE = { ...PLANNED, runs: [...PLANNED.runs, { run: 's/c-3', params: { m: 'c' } }] }

const open = async ($: Engine, on: On, ...events: object[]) => {
  const started = await start($, on)
  started.send(lines(THREE, ...events))
  await started.settle()
  const pane = await mountPane($)
  const press = (key: string, more: { shift?: true } = {}) => pane.key({ key, in: 'runs', ...more })
  const cursor = async () => {
    const rows = await pane.findAll({ type: 'Text', in: 'runs' })
    return rows.find(row => row.props.inverse === true)?.text.split(' ')[0]
  }
  const order = async () => {
    const rows = await pane.findAll({ type: 'Text', in: 'runs' })
    return [...new Set(rows.map(row => row.text.split(' ')[0]).filter(name => /^[abc]-\d$/.test(name ?? '')))]
  }
  return { started, pane, press, cursor, order }
}

test('moves the cursor as the TUI does', SLOW, async ($, on) => {
  const { press, cursor } = await open($, on)
  expect(await cursor()).toBe('a-1')
  await press('j')
  expect(await cursor()).toBe('b-2')
  await press('down')
  await press('j')
  expect(await cursor()).toBe('c-3')
  await press('k')
  expect(await cursor()).toBe('b-2')
  await press('g')
  expect(await cursor()).toBe('a-1')
  await press('G')
  expect(await cursor()).toBe('c-3')
  await press('up')
  await press('g', { shift: true })
  expect(await cursor()).toBe('c-3')
})

test('steers the run under the cursor through the labnotes CLI', SLOW, async ($, on) => {
  const { started, press } = await open($, on)
  await press('j')
  await press('n')
  await press('space')
  await press('x')
  await press('+')
  await press('-')
  await press('r')
  expect(started.ran).toEqual([
    [...CONTROL, 'run_next', 's/b-2'],
    [...CONTROL, 'toggle', 's/b-2'],
    [...CONTROL, 'kill', 's/b-2'],
    [...CONTROL, 'set_concurrency', '2'],
    [...CONTROL, 'set_concurrency', '0'],
  ])
})

test('retries only a failed run', SLOW, async ($, on) => {
  const { started, press } = await open($, on, {
    event: 'ended',
    experiment: 'exp',
    run: 's/a-1',
    exit_code: 1,
    error: null,
  })
  await press('r')
  expect(started.ran).toEqual([[...CONTROL, 'retry', 's/a-1']])
})

test('deselects every pending run shown at once', SLOW, async ($, on) => {
  const { started, press } = await open($, on, {
    event: 'started',
    experiment: 'exp',
    run: 's/a-1',
    params: { m: 'a' },
    folder: '/r/a',
  })
  await press('D')
  expect(started.ran).toEqual([
    [...CONTROL, 'toggle', 's/b-2'],
    [...CONTROL, 'toggle', 's/c-3'],
  ])
})

test('stops everything, finishing once idle', SLOW, async ($, on) => {
  const { started, press } = await open($, on)
  await press('X')
  started.send(lines({ event: 'idle', experiment: 'exp' }))
  await started.settle()
  await press('X')
  expect(started.ran).toEqual([
    [...CONTROL, 'interrupt'],
    [...CONTROL, 'finish'],
  ])
})

test('hides failed runs and filters by params', SLOW, async ($, on) => {
  const { pane, press } = await open($, on, {
    event: 'ended',
    experiment: 'exp',
    run: 's/a-1',
    exit_code: 1,
    error: null,
  })
  await press('f')
  expect(await shown(pane)).not.toContain('a-1')
  expect(await shown(pane)).toContain('Failed runs hidden.')
  await press('f')
  expect(await shown(pane)).toContain('a-1')

  await press('/')
  await press('-')
  await press('-')
  await press('m')
  await press('space')
  await press('c')
  await press('x')
  await press('backspace')
  await press('return')
  const filtered = await shown(pane)
  expect(filtered).toContain('/--m c')
  expect(filtered).toContain('c-3')
  expect(filtered).not.toContain('b-2')

  await press('q')
  expect(await shown(pane)).toContain('b-2')
})

test('opens the log under the cursor and leaves it with q', SLOW, async ($, on) => {
  const { pane, press } = await open($, on)
  await press('j')
  await press('return')
  expect(await shown(pane)).toContain('q back · X stop all')
  await press('j')
  await press('q')
  const back = await shown(pane)
  expect(back).toContain('1 at a time')
})

test('follows a run sent to the front of the queue', SLOW, async ($, on) => {
  const { started, press, cursor } = await open($, on)
  await press('j')
  started.send(lines({ event: 'queued', experiment: 'exp', run: 's/c-3', pending: ['s/c-3', 's/a-1', 's/b-2'], held: [] }))
  await started.settle()
  expect(await cursor()).toBe('c-3')
})

test('moves a pending run through the queue and drops it there', SLOW, async ($, on) => {
  const { started, pane, press, cursor, order } = await open($, on)
  await press('m')
  expect(await shown(pane)).toContain('Moving s/a-1.')
  await press('j')
  await press('j')
  await press('j')
  expect(await cursor()).toBe('a-1')
  expect(await order()).toEqual(['b-2', 'c-3', 'a-1'])
  await press('x')
  await press('k')
  await press('return')
  expect(started.ran).toEqual([[...CONTROL, 'move', 's/a-1', '1']])
})

test('puts a grabbed run back with q, and grabs only pending runs', SLOW, async ($, on) => {
  const { started, press, cursor, order } = await open($, on, {
    event: 'started',
    experiment: 'exp',
    run: 's/a-1',
    params: { m: 'a' },
    folder: '/r/a',
  })
  await press('m')
  await press('j')
  expect(await cursor()).toBe('b-2')
  await press('m')
  await press('j')
  expect(await order()).toEqual(['a-1', 'c-3', 'b-2'])
  expect(await cursor()).toBe('b-2')
  await press('q')
  expect(await order()).toEqual(['a-1', 'b-2', 'c-3'])
  expect(await cursor()).toBe('b-2')
  await press('m')
  await press('m')
  expect(started.ran).toEqual([[...CONTROL, 'move', 's/b-2', '0']])
})
