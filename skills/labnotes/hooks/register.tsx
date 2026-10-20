import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { Experiment, Run } from '../types'
import { applyEvent, describeDone, parseEvent, splitLines } from './runs'

const PANE = 'labnotes'
const COMMAND = 'labnotes-runs'
const STATUS = ['uvx', 'labnotes', 'run', 'status', '--follow', '--json']
const experiments = atom({ plugin: 'labnotes', key: 'experiments' } as const, [])

const COLORS: Partial<Record<Run['state'], string>> = {
  running: 'warning',
  stopping: 'warning',
  passed: 'success',
  failed: 'error',
}

const shortName = (run: string) => run.slice(run.lastIndexOf('/') + 1)

const describeParams = (params: Record<string, unknown>) =>
  Object.entries(params)
    .map(([name, value]) => `${name}=${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(' ')

const describeExperiment = (experiment: Experiment) => {
  if (experiment.error !== null) return `stopped: ${experiment.error}`
  return experiment.isFinished ? 'finished' : 'running'
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description: "Show this project's labnotes runs in a pane",
    })
    const started = await next(e)
    void (async () => {
      let held = ''
      for await (const { stream, text } of $.process.spawn({ argv: STATUS })) {
        if (stream !== 'stdout') continue
        const [lines, rest] = splitLines(held, text)
        held = rest
        for (const line of lines) {
          const event = parseEvent(line)
          if (event === undefined) continue
          let said: string | undefined
          await update($, experiments, list => {
            const changed = applyEvent(list, event)
            said = describeDone(changed, event)
            return changed
          })
          if (said !== undefined) $.ui.toast(said, { timeoutMs: 10000 })
        }
      }
    })().catch(() => {})
    return started
  })

  on('command.run', { command: COMMAND }, async $ => {
    await $.ui.open({ id: PANE, title: 'labnotes' })
    return { text: 'labnotes pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const list = await read($, experiments)
    return (
      <Box flexDirection="column">
        {list.length === 0 && <Text dimColor>No labnotes runs yet.</Text>}
        {list.map(experiment => (
          <Box flexDirection="column" key={experiment.name}>
            <Text bold>
              {experiment.name} <Text dimColor>{describeExperiment(experiment)}</Text>
            </Text>
            {experiment.runs.map(run => (
              <Text
                key={run.run}
                wrap="truncate-end"
                dimColor={run.state === 'pending' || run.state === 'skipped'}
              >
                <Text color={COLORS[run.state]}>{run.state.padEnd(8)}</Text> {shortName(run.run)}{' '}
                {describeParams(run.params)}
                {run.line === undefined ? '' : <Text dimColor> {run.line}</Text>}
              </Text>
            ))}
          </Box>
        ))}
      </Box>
    )
  })
}
