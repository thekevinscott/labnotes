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
  isHiding: boolean
  note: string
  frame: number
  now: number
  nextRuns: string
  grab: Grab | null
  opened: string[]
}

type Grab = { experiment: string; run: string; place: number }

type Shown = { experiment: Experiment; row: Row }

const COLUMNS = ['run', 'params', 'status', 'time'] as const

const KEYS =
  'enter log · n next · m move · space deselect · D deselect shown · x stop · X stop all · f hide failed · r retry · +/- at once · / filter · q back'

const shownRows = (experiments: Experiment[], state: PaneState): Shown[] =>
  experiments.flatMap(experiment =>
    experiment.rows
      .filter(row => row.params.includes(state.filter))
      .filter(row => !(state.isHiding && row.status === 'failed'))
      .map(row => ({ experiment, row })),
  )

const pendingOf = (experiment: Experiment) => experiment.rows.filter(row => row.status === 'pending')

// Draw a grabbed run at its new place among the pending runs, as the TUI does before it drops.
const arranged = (experiments: Experiment[], grab: Grab | null): Experiment[] =>
  experiments.map(experiment => {
    if (grab === null || experiment.name !== grab.experiment) return experiment
    const pending = pendingOf(experiment)
    const grabbed = pending.find(row => row.run === grab.run)
    if (grabbed === undefined) return experiment
    const order = pending.filter(row => row !== grabbed)
    order.splice(grab.place, 0, grabbed)
    let at = 0
    return { ...experiment, rows: experiment.rows.map(row => (row.status === 'pending' ? order[at++] ?? row : row)) }
  })

const nextRunsOf = (experiments: Experiment[]) => experiments.map(one => one.nextRun ?? '').join('\n')

const isTypable = (event: ClientKeyEvent) => event.key.length === 1 && !event.ctrl && !event.meta

const Pane: ClientModule<PaneProps, PaneState> = (props, surface) => {
  const { Box, Text } = surface.elements
  const { log } = props
  const fresh: PaneState = surface.state ?? {
    cursor: 0,
    filter: '',
    isTyping: false,
    isHiding: false,
    note: '',
    frame: 0,
    now: Date.now(),
    nextRuns: nextRunsOf(props.experiments),
    grab: null,
    opened: [],
  }
  const grabbed = props.experiments
    .find(one => one.name === fresh.grab?.experiment)
    ?.rows.find(row => row.run === fresh.grab?.run)
  // A grabbed run that starts meanwhile goes back where it was.
  const state = grabbed?.status === 'pending' ? fresh : { ...fresh, grab: null }
  const experiments = arranged(props.experiments, state.grab)
  const shown = shownRows(experiments, state)
  const set = (change: Partial<PaneState>) => surface.setState({ ...state, note: '', ...change })
  const post = (message: PaneMessage) => surface.post(message as JsonValue)
  const control = (experiment: Experiment, action: string, ...args: string[]) =>
    post({ controls: [{ experiment: experiment.name, action, args }] })

  // Follow a run sent to the front of the queue, as the TUI's cursor does.
  const nextRuns = nextRunsOf(experiments)
  if (surface.state !== undefined && nextRuns !== state.nextRuns) {
    const queued = experiments.find(one => one.nextRun !== null && !state.nextRuns.includes(one.nextRun))
    const at = shown.findIndex(({ row }) => row.run === queued?.nextRun)
    set({ nextRuns, note: state.note, cursor: at === -1 ? state.cursor : at })
  }

  const cursor = Math.max(0, Math.min(state.cursor, shown.length - 1))
  const current = shown[cursor]

  const stopAll = (experiment: Experiment | undefined) => {
    if (experiment !== undefined) control(experiment, experiment.isIdle ? 'finish' : 'interrupt')
  }

  const shift = (grab: Grab, step: number) => {
    const experiment = experiments.find(one => one.name === grab.experiment)
    const place = grab.place + step
    if (experiment === undefined || place < 0 || place >= pendingOf(experiment).length) return
    const moved = { ...grab, place }
    const at = shownRows(arranged(props.experiments, moved), state).findIndex(({ row }) => row.run === grab.run)
    set({ grab: moved, note: state.note, cursor: at === -1 ? cursor : at })
  }

  const drop = (grab: Grab) => {
    post({ controls: [{ experiment: grab.experiment, action: 'move', args: [grab.run, String(grab.place)] }] })
    set({ grab: null })
  }

  const onGrabbing = (grab: Grab, event: ClientKeyEvent) => {
    switch (event.key) {
      case 'j':
      case 'down':
        return shift(grab, 1)
      case 'k':
      case 'up':
        return shift(grab, -1)
      case 'return':
      case 'm':
        return drop(grab)
      case 'q': {
        const at = shownRows(props.experiments, state).findIndex(({ row }) => row.run === grab.run)
        return set({ grab: null, cursor: at === -1 ? cursor : at })
      }
    }
  }

  const onKey = (event: ClientKeyEvent) => {
    if (state.grab !== null) return onGrabbing(state.grab, event)
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
      case 'n':
        if (current !== undefined) control(current.experiment, 'run_next', current.row.run)
        return
      case 'm':
        if (current?.row.status !== 'pending') return
        return set({
          grab: {
            experiment: current.experiment.name,
            run: current.row.run,
            place: pendingOf(current.experiment).indexOf(current.row),
          },
          note: `Moving ${current.row.run}. j/k moves it, enter drops it, q puts it back.`,
        })
      case 'space':
        if (current !== undefined) control(current.experiment, 'toggle', current.row.run)
        return
      case 'D':
        return post({
          controls: shown
            .filter(({ row }) => row.status === 'pending')
            .map(({ experiment, row }) => ({ experiment: experiment.name, action: 'toggle', args: [row.run] })),
        })
      case 'x':
        if (current !== undefined) control(current.experiment, 'kill', current.row.run)
        return
      case 'X':
        return stopAll(current?.experiment ?? (experiments.length === 1 ? experiments[0] : undefined))
      case 'f':
        return set({
          isHiding: !state.isHiding,
          note: state.isHiding ? 'Failed runs shown.' : 'Failed runs hidden.',
        })
      case 'r':
        if (current?.row.status === 'failed') control(current.experiment, 'retry', current.row.run)
        return
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
      {state.note !== '' && <Text dimColor>{state.note}</Text>}
      {experiments.length > 0 && (
        <Text dimColor wrap="truncate-end">
          {KEYS}
        </Text>
      )}
    </Box>
  )
}

export default Pane
