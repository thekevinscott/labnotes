export type RunState = 'pending' | 'running' | 'stopping' | 'passed' | 'failed' | 'skipped'

export type Run = {
  run: string
  params: Record<string, unknown>
  state: RunState
  line?: string
}

export type Experiment = {
  name: string
  runs: Run[]
  isFinished: boolean
  error: string | null
}

declare module 'claude-code' {
  interface PluginState {
    labnotes: { experiments: Experiment[] }
  }
}
