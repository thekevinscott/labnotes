import { describe, expect, test } from 'claude-code/testing'

import fixture from '../fixtures/run'
import {
  applyBlock,
  applyEvent,
  blockRows,
  cleanLine,
  describeDone,
  describeEvent,
  formatElapsed,
  paramArgs,
  parseEvent,
  rowCells,
  splitLines,
} from './runs'
import type { Block } from '../types'
import type { LabnotesEvent } from './runs'

const planned: LabnotesEvent = {
  event: 'planned',
  experiment: 'exp',
  title: 'Exp',
  concurrency: 2,
  runs: [
    { run: 's/a-1', params: { m: 'a' } },
    { run: 's/b-2', params: { m: 'b' } },
  ],
}

const fold = (...events: LabnotesEvent[]) =>
  events.reduce(
    (list, event, index) => applyEvent(list, { experiment: 'exp', ...event }, (index + 1) * 1000),
    applyEvent([], planned, 0),
  )

describe('the recorded run shared with the Python TUI', () => {
  test('shows the same rows after every event', () => {
    const step = fixture.step * 1000
    let list = applyEvent([], { event: 'none' }, 0)
    const seen = fixture.events.flatMap((event, index) => {
      list = applyEvent(list, event, index * step)
      if (event.event === 'output' || event.event === 'done') return []
      const [experiment] = list
      return [
        {
          after: index + 1,
          title: experiment?.title,
          concurrency: experiment?.concurrency,
          rows: experiment?.rows.map(row => {
            const cells = rowCells(row, index * step)
            return { ...cells, status: cells.status ?? 'running' }
          }),
        },
      ]
    })
    expect(seen).toEqual(fixture.checkpoints)
  })

  test('writes params the same way', () => {
    for (const [params, args] of fixture.params) expect(paramArgs(params)).toBe(args)
  })

  test('writes elapsed time the same way', () => {
    for (const [seconds, text] of fixture.elapsed) expect(formatElapsed(seconds as number)).toBe(text)
  })
})

describe('splitLines', () => {
  test('holds back an unfinished line and keeps blank ones', () => {
    expect(splitLines('', '{"a":1}\n{"b"')).toEqual([['{"a":1}'], '{"b"'])
    expect(splitLines('{"b"', ':2}\n\n')).toEqual([['{"b":2}', ''], ''])
  })
})

describe('parseEvent', () => {
  test('reads an event and skips anything else', () => {
    expect(parseEvent('{"event":"idle"}')).toEqual({ event: 'idle' })
    expect(parseEvent('not json')).toBeUndefined()
    expect(parseEvent('[1]')).toBeUndefined()
    expect(parseEvent('null')).toBeUndefined()
  })
})

describe('cleanLine', () => {
  test('keeps what a terminal would show last', () => {
    expect(cleanLine('\x1b[31mred\x1b[0m')).toBe('red')
    expect(cleanLine('\x1b]0;title\x07text')).toBe('text')
    expect(cleanLine('10%\r50%\r')).toBe('50%')
    expect(cleanLine('a\tb\x07')).toBe('a    b')
    expect(cleanLine('')).toBe('')
  })
})

const logged = (...records: unknown[]) =>
  records.reduce<Block[]>(
    (blocks, record) => applyBlock(blocks, typeof record === 'string' ? record : JSON.stringify(record)),
    [],
  )

describe('applyBlock', () => {
  test('adds a complete block and skips lines that are not blocks', () => {
    expect(logged({ content: 'a', timestamp: 't' }, 'not json', '[1]', 'null', { content: 3 })).toEqual([
      { id: 'null', body: 'a', isOpen: false },
      { id: 'null', body: '3', isOpen: false },
    ])
  })

  test('grows a streaming block in place until it stops', () => {
    expect(
      logged(
        { id: 't1', phase: 'start', type: 'thinking' },
        { id: 't1', phase: 'delta', content: 'par' },
        { content: 'between' },
        { id: 't1', phase: 'delta', content: 'tial' },
        { id: 't1', phase: 'stop', content: '.' },
      ),
    ).toEqual([
      { id: '"t1"', body: 'partial.', isOpen: false },
      { id: 'null', body: 'between', isOpen: false },
    ])
  })

  test('keeps streams apart by id and leaves an unstopped one open', () => {
    expect(
      logged(
        { id: 'a', phase: 'start', content: 'A' },
        { id: 'b', phase: 'delta', content: 'B' },
        { id: 'a', phase: 'delta', content: 'a' },
        { id: 'b', phase: 'stop' },
      ),
    ).toEqual([
      { id: '"a"', body: 'Aa', isOpen: true },
      { id: '"b"', body: 'B', isOpen: false },
    ])
  })

  test('ignores a stray stop and opens anew after one', () => {
    expect(
      logged(
        { id: 't1', phase: 'stop', content: 'lost' },
        { id: 't1', phase: 'start', content: 'one' },
        { id: 't1', phase: 'stop' },
        { id: 't1', phase: 'delta', content: 'two' },
        { id: 't1', phase: 'update', content: 'three' },
      ),
    ).toEqual([
      { id: '"t1"', body: 'one', isOpen: false },
      { id: '"t1"', body: 'two', isOpen: true },
      { id: '"t1"', body: 'three', isOpen: false },
    ])
  })
})

describe('blockRows', () => {
  const block = { id: 'null', body: '\x1b[1mfirst\x1b[0m line\nsecond', isOpen: false }

  test('folds a block onto one line', () => {
    expect(blockRows(block, false, 8)).toEqual(['▸ first line second'])
  })

  test('opens a block over as many rows as its lines take', () => {
    expect(blockRows(block, true, 8)).toEqual(['▾ first ', 'line', 'second'])
    expect(blockRows({ ...block, body: 'a\n\nb' }, true, 0)).toEqual(['▾', ' ', 'a', '', 'b'])
  })
})

describe('describeEvent', () => {
  test('words each event as the TUI does', () => {
    const said = [
      { event: 'planned', runs: [1, 2], concurrency: 2 },
      { event: 'started', run: 'r', params: {} },
      { event: 'ended', run: 'r', exit_code: 2, error: null },
      { event: 'ended', run: 'r', exit_code: null, error: 'boom' },
      { event: 'stopping run', run: 'r' },
      { event: 'killing run', run: 'r' },
      { event: 'retried', run: 'r', retry: 's' },
      { event: 'idle' },
      { event: 'concurrency', concurrency: 3 },
      { event: 'stopping' },
      { event: 'killing' },
    ].map(describeEvent)
    expect(said).toEqual([
      '2 runs to go, 2 at a time.',
      'r started',
      'r exited 2',
      'r boom',
      'Stopping r.',
      'Killing r.',
      'r retried as s.',
      'No runs left.',
      '3 at a time.',
      'Stopping runs. X again to kill them.',
      'Killing runs.',
    ])
  })
})

describe('applyEvent', () => {
  test('says what happened, and keeps the note when a run starts', () => {
    const [other] = fold(
      { event: 'stopping run', run: 's/a-1' },
      { event: 'started', run: 's/b-2', params: { m: 'b' }, folder: '/f' },
    )
    expect(other?.message).toBe('Stopping s/a-1.')
  })

  test('sums up once idle and wakes when a run starts', () => {
    const [idle] = fold(
      { event: 'started', run: 's/a-1', params: { m: 'a' }, folder: '/a' },
      { event: 'ended', run: 's/a-1', exit_code: 0, error: null },
      { event: 'idle' },
    )
    expect(idle?.isIdle).toBe(true)
    expect(idle?.message).toBe('1 passed, 0 failed.')
    expect(idle?.rows[0]?.folder).toBe('/a')
    const [woken] = fold({ event: 'idle' }, { event: 'started', run: 's/b-2', params: {}, folder: '/b' })
    expect(woken?.isIdle).toBe(false)
  })

  test('marks the end of a session', () => {
    const [stopped] = fold({ event: 'done', error: 'boom' })
    expect(stopped).toMatchObject({ isFinished: true, error: 'boom', message: 'Stopped: boom' })
    const [finished] = fold({ event: 'idle' }, { event: 'done', error: null })
    expect(finished).toMatchObject({ isFinished: true, error: null, message: '0 passed, 0 failed.' })
  })

  test('starts an experiment over when it is planned again', () => {
    const done = fold({ event: 'done', error: null })
    const [again] = applyEvent(done, { ...planned, runs: [{ run: 't/c-1', params: {} }] }, 9)
    expect(again).toMatchObject({ isFinished: false, rows: [{ run: 't/c-1', params: '' }] })
  })

  test('keeps experiments apart and ignores events it cannot place', () => {
    const list = applyEvent(fold(), { ...planned, experiment: 'other', runs: [] }, 0)
    expect(list.map(one => one.name)).toEqual(['exp', 'other'])
    expect(applyEvent(list, { event: 'idle' }, 0)).toEqual(list)
    expect(applyEvent(list, { event: 'started', experiment: 'gone', run: 'x' }, 0)).toEqual(list)
    expect(applyEvent(list, { event: 'output', experiment: 'exp', run: 's/a-1' }, 0)).toEqual(list)
  })

  test('defaults what an older planned event left out', () => {
    const [bare] = applyEvent([], { event: 'planned', experiment: 'exp' }, 0)
    expect(bare).toMatchObject({ title: 'exp', concurrency: 1, rows: [] })
  })
})

describe('describeDone', () => {
  test('counts what passed and failed', () => {
    const done: LabnotesEvent = { event: 'done', experiment: 'exp', error: null }
    const list = fold(
      { event: 'ended', run: 's/a-1', exit_code: 0, error: null },
      { event: 'ended', run: 's/b-2', exit_code: 1, error: null },
      done,
    )
    expect(describeDone(list, done)).toBe('exp finished, 1 passed, 1 failed.')
  })

  test('says why a session stopped', () => {
    const done: LabnotesEvent = { event: 'done', experiment: 'exp', error: 'boom' }
    expect(describeDone(fold(done), done)).toBe('exp stopped: boom')
  })

  test('says nothing for other events', () => {
    expect(describeDone(fold(), { event: 'idle', experiment: 'exp' })).toBeUndefined()
    expect(describeDone([], { event: 'done', experiment: 'exp', error: null })).toBeUndefined()
  })
})
