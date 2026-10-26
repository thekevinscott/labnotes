import type { Block, Experiment, Row, RunStatus } from '../types'

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

const say = (experiment: Experiment, event: LabnotesEvent, rows = experiment.rows): Experiment => ({
  ...experiment,
  rows,
  message: describeEvent(event),
})

const applyRun = (experiment: Experiment, event: LabnotesEvent, now: number): Experiment => {
  const { rows } = experiment
  switch (event.event) {
    case 'started': {
      return {
        ...experiment,
        isIdle: false,
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
    case 'retried':
      return say(experiment, event, [...rows, planned({ run: event.retry, params: event.params })])
    case 'idle': {
      const idle = { ...experiment, isIdle: true }
      return { ...idle, message: summarize(idle) }
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

const parseRecord = (line: string): Record<string, unknown> | undefined => {
  try {
    const record: unknown = JSON.parse(line)
    if (typeof record === 'object' && record !== null && !Array.isArray(record)) {
      return record as Record<string, unknown>
    }
  } catch {}
  return undefined
}

// The TUI's rules: start and delta open a block by id, delta and stop grow it, stop closes it.
export const applyBlock = (blocks: readonly Block[], line: string): Block[] => {
  const record = parseRecord(line)
  if (record === undefined) return [...blocks]
  const { phase } = record
  const id = JSON.stringify(record.id ?? null)
  const body = record.content === undefined ? '' : String(record.content)
  const at = blocks.findLastIndex(block => block.isOpen && block.id === id)
  if (at !== -1 && (phase === 'delta' || phase === 'stop')) {
    return blocks.map((block, index) =>
      index === at ? { id, body: block.body + body, isOpen: phase === 'delta' } : block,
    )
  }
  if (phase === 'stop') return [...blocks]
  return [...blocks, { id, body, isOpen: phase === 'start' || phase === 'delta' }]
}

const chunks = (line: string, width: number): string[] => {
  if (line === '') return ['']
  const size = Math.max(width, 1)
  return Array.from({ length: Math.ceil(line.length / size) }, (_, index) =>
    line.slice(index * size, (index + 1) * size),
  )
}

export const blockRows = (block: Block, isExpanded: boolean, width: number): string[] => {
  const lines = block.body.split('\n').map(cleanLine)
  if (!isExpanded) return [`▸ ${lines.join(' ')}`]
  return `▾ ${lines.join('\n')}`.split('\n').flatMap(line => chunks(line, width))
}
