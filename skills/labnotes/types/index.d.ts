export type RunStatus = 'pending' | 'running' | 'passed' | 'failed' | 'skipped' | 'deselected'

export type Row = {
  run: string
  params: string
  status: RunStatus
  reason?: string
  dim: boolean
  startedAt?: number
  endedAt?: number
  folder?: string
}

export type Experiment = {
  name: string
  title: string
  concurrency: number
  rows: Row[]
  message: string
  nextRun: string | null
  isIdle: boolean
  isFinished: boolean
  error: string | null
}

export type Block = { id: string; body: string; isOpen: boolean }

export type Log = { run: string; lines: string[]; blocks: Block[] }

declare module 'claude-code' {
  interface PluginState {
    labnotes: { experiments: Experiment[]; log: Log | null }
  }
}
