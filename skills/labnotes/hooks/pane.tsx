import type { ClientKeyEvent, ClientModule, JsonValue } from 'claude-code'

import type { Experiment, Log, Row } from '../types'
import { SPINNER, blockRows, rowCells } from './runs'

export type PaneProps = { experiments: Experiment[]; log: Log | null; rows: number }

export type Control = { experiment: string; action: string; args: string[] }

export type PaneMessage = { controls: Control[] } | { view: string } | { leave: true }

type PaneState = {
  cursor: number
  filter: string
  isTyping: boolean
  frame: number
  now: number
  opened: string[]
}

type Shown = { experiment: Experiment; row: Row }

const COLUMNS = ['run', 'params', 'status', 'time'] as const

const KEYS = 'enter log · x stop · X stop all · +/- at once · / filter · q back'

const shownRows = (experiments: Experiment[], state: PaneState): Shown[] =>
  experiments.flatMap(experiment =>
    experiment.rows
      .filter(row => row.params.includes(state.filter))
      .map(row => ({ experiment, row })),
  )

const isTypable = (event: ClientKeyEvent) => event.key.length === 1 && !event.ctrl && !event.meta

const Pane: ClientModule<PaneProps, PaneState> = (props, surface) => {
  const { Box, Text } = surface.elements
  const { log } = props
  const state: PaneState = surface.state ?? {
    cursor: 0,
    filter: '',
    isTyping: false,
    frame: 0,
    now: Date.now(),
    opened: [],
  }
  const { experiments } = props
  const shown = shownRows(experiments, state)
  const set = (change: Partial<PaneState>) => surface.setState({ ...state, ...change })
  const post = (message: PaneMessage) => surface.post(message as JsonValue)
  const control = (experiment: Experiment, action: string, ...args: string[]) =>
    post({ controls: [{ experiment: experiment.name, action, args }] })

  const cursor = Math.max(0, Math.min(state.cursor, shown.length - 1))
  const current = shown[cursor]

  const stopAll = (experiment: Experiment | undefined) => {
    if (experiment !== undefined) control(experiment, experiment.isIdle ? 'finish' : 'interrupt')
  }

  const onKey = (event: ClientKeyEvent) => {
    if (state.isTyping) {
      if (event.key === 'return') set({ isTyping: false })
      else if (event.key === 'backspace' || event.key === 'delete') set({ filter: state.filter.slice(0, -1) })
      else if (event.key === 'space') set({ filter: `${state.filter} ` })
      else if (isTypable(event)) set({ filter: state.filter + event.key })
      return
    }
    if (log !== null) {
      if (event.key === 'q') post({ leave: true })
      if (event.key === 'X') stopAll(experiments.find(one => one.rows.some(row => row.run === log.run)))
      return
    }
    switch (event.key) {
      case 'j':
      case 'down':
        return set({ cursor: Math.min(cursor + 1, shown.length - 1) })
      case 'k':
      case 'up':
        return set({ cursor: Math.max(cursor - 1, 0) })
      case 'g':
        return set({ cursor: event.shift ? shown.length - 1 : 0 })
      case 'G':
        return set({ cursor: shown.length - 1 })
      case 'return':
        if (current !== undefined) post({ view: current.row.run })
        return
      case 'x':
        if (current !== undefined) control(current.experiment, 'kill', current.row.run)
        return
      case 'X':
        return stopAll(current?.experiment ?? (experiments.length === 1 ? experiments[0] : undefined))
      case '+':
      case '=':
        if (current !== undefined)
          control(current.experiment, 'set_concurrency', String(current.experiment.concurrency + 1))
        return
      case '-':
        if (current !== undefined)
          control(current.experiment, 'set_concurrency', String(current.experiment.concurrency - 1))
        return
      case '/':
        return set({ isTyping: true })
      case 'q':
        return set({ filter: '', isTyping: false })
    }
  }

  if (surface.state === undefined) {
    surface.setState(state)
    surface.every(100, () => {
      const latest = surface.state ?? state
      surface.setState({ ...latest, frame: (latest.frame + 1) % SPINNER.length, now: Date.now() })
    })
  }
  surface.onKey(onKey)
  surface.onPointer(() => {})

  if (log !== null) {
    const room = Math.max(props.rows - 2, 1)
    const width = surface.columns || 80
    const allBlockRows = log.blocks.flatMap((block, index) => {
      const key = `${log.run}#${index}`
      return blockRows(block, state.opened.includes(key), width).map(text => ({ key, text }))
    })
    const shownBlocks = allBlockRows.slice(-Math.floor(room / 2) || allBlockRows.length)
    surface.onPointer(event => {
      const key = event.type === 'down' ? shownBlocks[event.y - 1]?.key : undefined
      if (key === undefined) return
      set({ opened: state.opened.includes(key) ? state.opened.filter(one => one !== key) : [...state.opened, key] })
    })
    return (
      <Box flexDirection="column">
        <Text bold>{log.run}</Text>
        {shownBlocks.map(({ key, text }, index) => (
          <Text key={`${key}:${index}`} wrap="truncate-end">
            {text === '' ? ' ' : text}
          </Text>
        ))}
        {log.lines.slice(-(room - shownBlocks.length) || log.lines.length).map((line, index) => (
          <Text key={String(index)} wrap="truncate-end">
            {line === '' ? ' ' : line}
          </Text>
        ))}
        <Text dimColor>q back · X stop all{log.blocks.length > 0 ? ' · click a block to open it' : ''}</Text>
      </Box>
    )
  }

  const cells = shown.map(({ row }) => rowCells(row, state.now))
  const widths = COLUMNS.map(column =>
    Math.max(column.length, ...cells.map(cell => (column === 'status' ? (cell.status ?? ' ') : cell[column]).length)),
  )
  const pad = (text: string, column: number) => text.padEnd(widths[column] ?? 0)

  let at = 0
  return (
    <Box flexDirection="column">
      {experiments.length === 0 && <Text dimColor>No labnotes runs yet.</Text>}
      {experiments.map(experiment => {
        const own = cells.slice(at, at + shown.filter(one => one.experiment === experiment).length)
        const first = at
        at += own.length
        return (
          <Box flexDirection="column" key={experiment.name}>
            <Box justifyContent="space-between">
              <Text bold>{experiment.title}</Text>
              <Text>{experiment.concurrency} at a time</Text>
            </Box>
            <Text bold>{COLUMNS.map((column, index) => pad(column, index)).join('  ')}</Text>
            {own.map((cell, index) => (
              <Text key={shown[first + index]?.row.run} inverse={first + index === cursor} wrap="truncate-end">
                <Text dimColor={cell.dim}>
                  {pad(cell.run, 0)}  {pad(cell.params, 1)}
                </Text>
                {'  '}
                <Text dimColor={cell.statusStyle === 'dim'} color={cell.statusStyle === 'red' ? 'error' : undefined}>
                  {pad(cell.status ?? SPINNER[state.frame] ?? '|', 2)}
                </Text>
                {'  '}
                {cell.time}
              </Text>
            ))}
            {experiment.message !== '' && <Text dimColor>{experiment.message}</Text>}
          </Box>
        )
      })}
      {(state.isTyping || state.filter !== '') && (
        <Text>
          /{state.filter}
          {state.isTyping ? '█' : ''}
        </Text>
      )}
      {experiments.length > 0 && (
        <Text dimColor wrap="truncate-end">
          {KEYS}
        </Text>
      )}
    </Box>
  )
}

export default Pane
