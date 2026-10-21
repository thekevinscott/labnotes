import { describe, expect, test } from 'claude-code/testing'

import { applyEvent, describeDone, parseEvent, splitLines } from './runs'
import type { LabnotesEvent } from './runs'

const planned: LabnotesEvent = {
  event: 'planned',
  experiment: 'exp',
  runs: [
    { run: 's/a-1', params: { m: 'a' } },
    { run: 's/b-2', params: { m: 'b' } },
  ],
}

const fold = (...events: LabnotesEvent[]) =>
  events.reduce((list, event) => applyEvent(list, { experiment: 'exp', ...event }), applyEvent([], planned))

describe('splitLines', () => {
  test('holds back an unfinished line', () => {
    expect(splitLines('', '{"a":1}\n{"b"')).toEqual([['{"a":1}'], '{"b"'])
    expect(splitLines('{"b"', ':2}\n\n')).toEqual([['{"b":2}'], ''])
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

describe('applyEvent', () => {
  test('lists planned runs as pending', () => {
    expect(fold()).toEqual([
      {
        name: 'exp',
        isFinished: false,
        error: null,
        runs: [
          { run: 's/a-1', params: { m: 'a' }, state: 'pending' },
          { run: 's/b-2', params: { m: 'b' }, state: 'pending' },
        ],
      },
    ])
  })

  test('follows a run from start to end with its latest line', () => {
    const [experiment] = fold(
      { event: 'started', run: 's/a-1' },
      { event: 'output', run: 's/a-1', line: 'tick 1' },
      { event: 'output', run: 's/a-1', line: 'tick 2' },
      { event: 'started', run: 's/b-2' },
      { event: 'stopping run', run: 's/b-2' },
    )
    expect(experiment?.runs.map(run => [run.state, run.line])).toEqual([
      ['running', 'tick 2'],
      ['stopping', undefined],
    ])
  })

  test('tells passed runs from failed ones', () => {
    const [experiment] = fold(
      { event: 'ended', run: 's/a-1', exit_code: 0, error: null },
      { event: 'ended', run: 's/b-2', exit_code: 3, error: null },
    )
    expect(experiment?.runs.map(run => run.state)).toEqual(['passed', 'failed'])
    const [errored] = fold({ event: 'ended', run: 's/a-1', exit_code: 0, error: 'lost' })
    expect(errored?.runs[0]?.state).toBe('failed')
  })

  test('skips, requeues and retries runs', () => {
    const [experiment] = fold(
      { event: 'deselected', run: 's/a-1' },
      { event: 'deselected', run: 's/b-2' },
      { event: 'reselected', run: 's/b-2' },
      { event: 'retried', run: 's/b-2', retry: 's/b-3', params: { m: 'b' } },
    )
    expect(experiment?.runs.map(run => [run.run, run.state])).toEqual([
      ['s/a-1', 'skipped'],
      ['s/b-2', 'pending'],
      ['s/b-3', 'pending'],
    ])
  })

  test('marks the end of a session and the runs it never finished', () => {
    const [experiment] = fold(
      { event: 'ended', run: 's/a-1', exit_code: 0, error: null },
      { event: 'started', run: 's/b-2' },
      { event: 'done', error: 'boom' },
    )
    expect(experiment?.isFinished).toBe(true)
    expect(experiment?.error).toBe('boom')
    expect(experiment?.runs.map(run => run.state)).toEqual(['passed', 'skipped'])
  })

  test('starts an experiment over when it is planned again', () => {
    const done = fold({ event: 'done', error: null })
    const again = applyEvent(done, { ...planned, runs: [{ run: 't/c-1', params: {} }] })
    expect(again).toEqual([
      {
        name: 'exp',
        isFinished: false,
        error: null,
        runs: [{ run: 't/c-1', params: {}, state: 'pending' }],
      },
    ])
  })

  test('keeps experiments apart and ignores events it cannot place', () => {
    const list = applyEvent(fold(), { ...planned, experiment: 'other', runs: [] })
    expect(list.map(one => one.name)).toEqual(['exp', 'other'])
    expect(applyEvent(list, { event: 'idle' })).toEqual(list)
    expect(applyEvent(list, { event: 'started', experiment: 'gone', run: 'x' })).toEqual(list)
    expect(applyEvent(list, { event: 'idle', experiment: 'exp' })).toEqual(list)
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
