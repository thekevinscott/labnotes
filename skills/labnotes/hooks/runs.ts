import type { Experiment, Row, RunStatus } from '../types'

export type LabnotesEvent = { event: string; [field: string]: unknown }

export type Cells = {
  run: string
  params: string
  status: string | undefined
  statusStyle: '' | 'dim' | 'red'
  dim: boolean
  time: string
}

export const GLYPHS: Record<Exclude<RunStatus, 'running' | 'failed'>, string> = {
  pending: '○',
  passed: '✓',
  skipped: '–',
  deselected: '⊘',
}
export const SPINNER = '|/-\\'

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
  return [lines, rest]
}

// Python's json.dumps: ", " and ": " separators, non-ASCII escaped.
const pythonJson = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(pythonJson).join(', ')}]`
  if (typeof value === 'object' && value !== null) {
    const pairs = Object.entries(value).map(([key, item]) => `${pythonJson(key)}: ${pythonJson(item)}`)
    return `{${pairs.join(', ')}}`
  }
  return (JSON.stringify(value) ?? 'null').replace(
    /[\u007f-￿]/g,
    char => `\\u${char.charCodeAt(0).toString(16).padStart(4, '0')}`,
  )
}

const paramText = (value: unknown): string => {
  if (typeof value === 'boolean') return value ? '1' : '0'
  if (typeof value === 'string') return value
  if (typeof value === 'object' && value !== null) return pythonJson(value)
  return String(value)
}

export const paramArgs = (params: unknown): string =>
  Object.entries((params ?? {}) as Record<string, unknown>)
    .flatMap(([name, value]) => [`--${name}`, paramText(value)])
    .join(' ')

export const formatElapsed = (seconds: number): string => {
  const whole = Math.trunc(seconds)
  const rest = whole % 60
  const minutes = Math.trunc(whole / 60) % 60
  const hours = Math.trunc(whole / 3600)
  const pad = (count: number) => String(count).padStart(2, '0')
  if (hours) return `${hours}h ${pad(minutes)}m`
  if (minutes) return `${minutes}m ${pad(rest)}s`
  return `${rest}s`
}

export const shortName = (run: string) => run.slice(run.lastIndexOf('/') + 1)

export const describeEvent = (event: LabnotesEvent): string => {
  switch (event.event) {
    case 'planned':
      return `${(event.runs as unknown[]).length} runs to go, ${event.concurrency} at a time.`
    case 'started':
      return `${event.run} started ${paramArgs(event.params)}`.trimEnd()
    case 'ended':
      return `${event.run} ${event.error || `exited ${event.exit_code}`}`
    case 'queued':
      return `${event.run} runs next.`
    case 'moved': {
      const pending = event.pending as string[]
      return `${event.run} moved to ${pending.indexOf(String(event.run)) + 1} of ${pending.length} in the queue.`
    }
    case 'deselected':
      return `${event.run} deselected.`
    case 'reselected':
      return `${event.run} back in the queue.`
    case 'stopping run':
      return `Stopping ${event.run}.`
    case 'killing run':
      return `Killing ${event.run}.`
    case 'retried':
      return `${event.run} retried as ${event.retry}.`
    case 'idle':
      return 'No runs left.'
    case 'concurrency':
      return `${event.concurrency} at a time.`
    case 'stopping':
      return 'Stopping runs. X again to kill them.'
    default:
      return 'Killing runs.'
  }
}

export const summarize = (experiment: Experiment): string => {
  const ended = experiment.rows.filter(row => row.endedAt !== undefined).length
  const failed = experiment.rows.filter(row => row.status === 'failed').length
  return `${ended - failed} passed, ${failed} failed.`
}

const planned = (run: unknown): Row => {
  const { run: name, params } = run as { run: string; params: unknown }
  return { run: name, params: paramArgs(params), status: 'pending', dim: true }
}

const setRow = (rows: Row[], name: unknown, change: Partial<Row>): Row[] =>
  rows.map(row => (row.run === name ? { ...row, ...change } : row))

const reorder = (rows: Row[], event: LabnotesEvent): Row[] => {
  const waiting = [...(event.pending as string[]), ...(event.held as string[])]
  const moved = waiting.flatMap(name => rows.filter(row => row.run === name))
  return [...rows.filter(row => !waiting.includes(row.run)), ...moved]
}

const say = (experiment: Experiment, event: LabnotesEvent, rows = experiment.rows): Experiment => ({
  ...experiment,
  rows,
  message: describeEvent(event),
  nextRun: null,
})

const applyRun = (experiment: Experiment, event: LabnotesEvent, now: number): Experiment => {
  const { rows } = experiment
  switch (event.event) {
    case 'started': {
      const isNext = event.run === experiment.nextRun
      return {
        ...experiment,
        isIdle: false,
        message: isNext ? '' : experiment.message,
        nextRun: isNext ? null : experiment.nextRun,
        rows: setRow(rows, event.run, {
          params: paramArgs(event.params),
          status: 'running',
          dim: false,
          startedAt: now,
          folder: String(event.folder),
        }),
      }
    }
    case 'ended': {
      const reason = event.error || (event.exit_code ? `exited ${event.exit_code}` : undefined)
      const status = reason === undefined ? 'passed' : 'failed'
      return { ...experiment, rows: setRow(rows, event.run, { status, reason: reason as string, endedAt: now }) }
    }
    case 'queued':
      return { ...say(experiment, event, reorder(rows, event)), nextRun: String(event.run) }
    case 'moved':
      return say(experiment, event, reorder(rows, event))
    case 'deselected':
      return say(experiment, event, reorder(setRow(rows, event.run, { status: 'deselected' }), event))
    case 'reselected':
      return say(experiment, event, reorder(setRow(rows, event.run, { status: 'pending' }), event))
    case 'retried':
      return say(experiment, event, [...rows, planned({ run: event.retry, params: event.params })])
    case 'idle': {
      const idle = { ...experiment, isIdle: true }
      return { ...idle, message: summarize(idle), nextRun: null }
    }
    case 'concurrency':
      return { ...experiment, concurrency: Number(event.concurrency) }
    case 'stopping':
      return say(
        experiment,
        event,
        rows.map(row => (row.status === 'pending' ? { ...row, status: 'skipped' } : row)),
      )
    case 'done': {
      const error = (event.error as string | null) ?? null
      return {
        ...experiment,
        isFinished: true,
        error,
        message: error === null ? experiment.message : `Stopped: ${error}`,
      }
    }
    case 'output':
      return experiment
    default:
      return say(experiment, event)
  }
}

export const applyEvent = (
  experiments: readonly Experiment[],
  event: LabnotesEvent,
  now: number,
): Experiment[] => {
  const name = event.experiment
  if (typeof name !== 'string') return [...experiments]
  if (event.event === 'planned') {
    const fresh: Experiment = {
      name,
      title: String(event.title ?? name),
      concurrency: Number(event.concurrency ?? 1),
      rows: ((event.runs as unknown[]) ?? []).map(planned),
      message: '',
      nextRun: null,
      isIdle: false,
      isFinished: false,
      error: null,
    }
    return [...experiments.filter(one => one.name !== name), fresh]
  }
  return experiments.map(one => (one.name === name ? applyRun(one, event, now) : one))
}

export const rowCells = (row: Row, now: number): Cells => ({
  run: shortName(row.run),
  params: row.params,
  status:
    row.status === 'running'
      ? undefined
      : row.status === 'failed'
        ? `✗ ${row.reason}`
        : GLYPHS[row.status],
  statusStyle: row.status === 'failed' ? 'red' : row.status === 'running' || row.status === 'passed' ? '' : 'dim',
  dim: row.dim,
  time: row.startedAt === undefined ? '' : formatElapsed(((row.endedAt ?? now) - row.startedAt) / 1000),
})

export const describeDone = (
  experiments: readonly Experiment[],
  event: LabnotesEvent,
): string | undefined => {
  if (event.event !== 'done') return undefined
  const experiment = experiments.find(one => one.name === event.experiment)
  if (experiment === undefined) return undefined
  if (experiment.error !== null) return `${experiment.name} stopped: ${experiment.error}`
  return `${experiment.name} finished, ${summarize(experiment)}`
}

export const cleanLine = (line: string): string =>
  line
    .replace(/\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)?/g, '')
    .split('\r')
    .filter(part => part !== '')
    .pop()
    ?.replace(/\t/g, '    ')
    .replace(/[\x00-\x1f\x7f]/g, '') ?? ''
