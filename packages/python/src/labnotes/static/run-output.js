import { AnsiUp } from "/static/vendor/ansi_up.js";

// Rows kept above and below the visible ones, so short scrolls need no fetch.
const BUFFER = 100;

const log = document.querySelector(".run-log");
const state = document.querySelector(".run-state");
const source = new EventSource(log.dataset.url);
const tabs = [...log.querySelectorAll('[role="tab"]')];
const views = Object.fromEntries(
  [...log.querySelectorAll(".run-output")].map((pane) => [
    pane.dataset.stream,
    {
      pane,
      rows: pane.querySelector(".rows"),
      window: pane.querySelector(".window"),
      pinned: true,
    },
  ]),
);

const blocks = document.querySelector(".run-blocks");

let streaming = new Map();

function clear(view) {
  Object.assign(view, { segments: [], first: 0, loaded: 0, stale: true, generation: (view.generation ?? 0) + 1 });
  view.window.replaceChildren();
  resize(view);
}

// Each invocation's log is its own segment; rows run on across them.
const total = (view) => view.segments.reduce((sum, segment) => sum + segment.rows, 0);

function count(view) {
  const last = view.segments.at(-1);
  return last ? total(view) - last.rows + last.lines : 0;
}

const rowHeight = (view) => parseFloat(getComputedStyle(view.window).lineHeight);

function resize(view) {
  view.rows.style.height = `${total(view) * rowHeight(view)}px`;
  view.pane.dataset.rows = total(view);
}

function relabel() {
  for (const tab of tabs) {
    tab.querySelector(".count").textContent = count(views[tab.dataset.stream]);
  }
}

async function fetchRows(view, first, wanted) {
  const lines = [];
  for (const segment of view.segments) {
    if (lines.length >= wanted) break;
    if (first >= segment.rows) {
      first -= segment.rows;
      continue;
    }
    const url = new URL(log.dataset.lines, location.href);
    url.search = new URLSearchParams({ file: segment.file, first, count: wanted - lines.length });
    const response = await fetch(url);
    if (!response.ok) return null;
    lines.push(...(await response.json()).lines);
    first = 0;
  }
  return lines;
}

async function load(view) {
  if (view.pane.hidden) return;
  if (view.loading) {
    view.again = true;
    return;
  }
  const height = rowHeight(view);
  const top = Math.floor(Math.max(0, view.pane.scrollTop - view.rows.offsetTop) / height);
  const shown = Math.ceil(view.pane.clientHeight / height) + 1;
  const needed = Math.min(top + shown, total(view));
  if (!view.stale && top >= view.first && needed <= view.first + view.loaded) return;
  // Rows that change during the fetch mark the view stale again.
  Object.assign(view, { loading: true, stale: false });
  const { generation } = view;
  const first = Math.max(0, top - BUFFER);
  const lines = await fetchRows(view, first, shown + 2 * BUFFER);
  view.loading = false;
  if (lines === null) view.stale = true;
  else if (generation === view.generation) {
    view.window.innerHTML = new AnsiUp().ansi_to_html(lines.join("\n"));
    view.window.style.top = `${first * height}px`;
    Object.assign(view, { first, loaded: lines.length });
  }
  if (view.again) {
    view.again = false;
    load(view);
  }
}

// A hidden pane can't scroll, so each one remembers whether it was at the end.
function pin(view) {
  if (view.pinned && !view.pane.hidden) view.pane.scrollTop = view.pane.scrollHeight;
}

for (const view of Object.values(views)) {
  clear(view);
  view.pane.addEventListener("scroll", () => {
    if (view.pane.hidden) return;
    view.pinned = view.pane.scrollTop + view.pane.clientHeight >= view.pane.scrollHeight - 4;
    load(view);
  });
}

for (const tab of tabs) {
  tab.addEventListener("click", () => {
    for (const other of tabs) other.setAttribute("aria-selected", String(other === tab));
    for (const [stream, view] of Object.entries(views)) view.pane.hidden = stream !== tab.dataset.stream;
    const view = views[tab.dataset.stream];
    pin(view);
    load(view);
  });
}

// The server recounts every log on each connection, so a reconnect starts clean.
source.addEventListener("open", () => {
  for (const view of Object.values(views)) clear(view);
  relabel();
  blocks.replaceChildren();
  blocks.hidden = true;
  streaming = new Map();
});

source.addEventListener("block", (event) => {
  const { id, phase, content = "" } = JSON.parse(event.data);
  const open = streaming.get(id);
  if (open && (phase === "delta" || phase === "stop")) {
    open.textContent += content;
    if (phase === "stop") streaming.delete(id);
    return;
  }
  if (phase === "stop") return;
  const line = document.createElement("button");
  line.type = "button";
  line.className = "log-block";
  line.setAttribute("aria-expanded", "false");
  line.textContent = content;
  line.addEventListener("click", () => {
    const expanded = line.getAttribute("aria-expanded") === "true";
    line.setAttribute("aria-expanded", String(!expanded));
  });
  if (phase === "start" || phase === "delta") streaming.set(id, line);
  blocks.append(line);
  blocks.hidden = false;
});

source.addEventListener("message", (event) => {
  const { stream, file, fresh, rows, lines } = JSON.parse(event.data);
  const view = views[stream];
  const settled = count(view);
  if (fresh && view.segments.at(-1)?.file === file) clear(view);
  if (view.segments.at(-1)?.file !== file) view.segments.push({ file });
  Object.assign(view.segments.at(-1), { rows, lines });
  if (view.first + view.loaded > settled) view.stale = true;
  resize(view);
  pin(view);
  load(view);
  relabel();
});

source.addEventListener("end", (event) => {
  source.close();
  const code = JSON.parse(event.data);
  state.textContent = code === null ? "ended" : `exit ${code}`;
  state.classList.add(code === 0 ? "good" : "bad");
  log.dataset.ended = "";
});
