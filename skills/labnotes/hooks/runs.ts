import type { Experiment, Run, RunState } from '../types'

export type LabnotesEvent = { event: string; [field: string]: unknown }

export const parseEvent = (line: string): LabnotesEvent | undefined => {
  try {
    const event: unknown = JSON.parse(line)
    if (typeof event === 'object' && event !== null && 'event' in event) {
      return event as LabnotesEvent
    }
  } catch {}
  return undefined
}

export const splitLines = (held: string, text: string): [string[], string] => {
  const lines = (held + text).split('\n')
  const rest = lines.pop() ?? ''
  return [lines.filter(line => line.trim() !== ''), rest]
}

const toRun = (planned: unknown): Run => {
  const { run, params } = planned as { run: string; params: Record<string, unknown> }
  return { run, params, state: 'pending' }
}

const setRun = (runs: Run[], name: unknown, change: Partial<Run>): Run[] =>
  runs.map(run => (run.run === name ? { ...run, ...change } : run))

const stateOf = (event: LabnotesEvent): RunState =>
  event.exit_code === 0 && !event.error ? 'passed' : 'failed'

const applyRun = (experiment: Experiment, event: LabnotesEvent): Experiment => {
  const { runs } = experiment
  switch (event.event) {
    case 'started':
      return { ...experiment, runs: setRun(runs, event.run, { state: 'running' }) }
    case 'stopping run':
      return { ...experiment, runs: setRun(runs, event.run, { state: 'stopping' }) }
    case 'ended':
      return { ...experiment, runs: setRun(runs, event.run, { state: stateOf(event) }) }
    case 'deselected':
      return { ...experiment, runs: setRun(runs, event.run, { state: 'skipped' }) }
    case 'reselected':
      return { ...experiment, runs: setRun(runs, event.run, { state: 'pending' }) }
    case 'output':
      return { ...experiment, runs: setRun(runs, event.run, { line: String(event.line) }) }
    case 'retried':
      return {
        ...experiment,
        runs: [...runs, toRun({ run: event.retry, params: event.params })],
      }
    case 'done':
      return {
        ...experiment,
        isFinished: true,
        error: (event.error as string | null) ?? null,
        runs: runs.map(run =>
          run.state === 'pending' || run.state === 'running' || run.state === 'stopping'
            ? { ...run, state: 'skipped' }
            : run,
        ),
      }
    default:
      return experiment
  }
}

export const applyEvent = (
  experiments: readonly Experiment[],
  event: LabnotesEvent,
): Experiment[] => {
  const name = event.experiment
  if (typeof name !== 'string') return [...experiments]
  if (event.event === 'planned') {
    const fresh: Experiment = {
      name,
      runs: ((event.runs as unknown[]) ?? []).map(toRun),
      isFinished: false,
      error: null,
    }
    return [...experiments.filter(one => one.name !== name), fresh]
  }
  return experiments.map(one => (one.name === name ? applyRun(one, event) : one))
}

export const describeDone = (
  experiments: readonly Experiment[],
  event: LabnotesEvent,
): string | undefined => {
  if (event.event !== 'done') return undefined
  const experiment = experiments.find(one => one.name === event.experiment)
  if (experiment === undefined) return undefined
  if (experiment.error !== null) return `${experiment.name} stopped: ${experiment.error}`
  const count = (state: RunState) => experiment.runs.filter(run => run.state === state).length
  return `${experiment.name} finished, ${count('passed')} passed, ${count('failed')} failed.`
}
