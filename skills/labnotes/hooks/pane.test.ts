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
  return { started, pane, press, cursor }
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
  await press('x')
  await press('+')
  await press('-')
  expect(started.ran).toEqual([
    [...CONTROL, 'kill', 's/b-2'],
    [...CONTROL, 'set_concurrency', '2'],
    [...CONTROL, 'set_concurrency', '0'],
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

test('filters by params', SLOW, async ($, on) => {
  const { pane, press } = await open($, on)
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

test('shows log blocks above the output, one line each until clicked', SLOW, async ($, on) => {
  const started = await start($, on)
  started.tail.push('printed\n')
  started.blockTail.push(
    lines({ content: 'first line\nsecond line' }, { id: 't1', phase: 'start', content: 'think' }),
  )
  started.send(lines(PLANNED, { event: 'started', experiment: 'exp', run: 's/a-1', params: { m: 'a' }, folder: '/r/a' }))
  await started.settle()
  const pane = await mountPane($)
  await pane.post({ view: 's/a-1' })
  await started.settle()
  const rows = async () => (await shown(pane)).split('\n')
  const click = (y: number) => pane.pointer({ type: 'down', x: 2, y, button: 'left' })

  expect(await rows()).toEqual([
    's/a-1',
    '▸ first line second line',
    '▸ think',
    'printed',
    'q back · X stop all · click a block to open it',
  ])
  await click(1)
  expect((await rows()).slice(1, 4)).toEqual(['▾ first line', 'second line', '▸ think'])
  await click(3)
  await pane.pointer({ type: 'up', x: 2, y: 1, button: 'left' })
  await click(5)
  expect((await rows()).slice(1, 5)).toEqual(['▾ first line', 'second line', '▾ think', 'printed'])
  await click(2)
  expect((await rows()).slice(1, 4)).toEqual(['▸ first line second line', '▾ think', 'printed'])
})
