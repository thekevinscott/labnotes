import { AnsiUp } from "/static/vendor/ansi_up.js";

// Lines kept above and below the visible ones, so short scrolls need no fetch.
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
      measure: pane.querySelector(".measure"),
      pinned: true,
    },
  ]),
);

const blocks = document.querySelector(".run-blocks");

let streaming = new Map();

function clear(view) {
  Object.assign(view, {
    segments: [],
    bottom: 0,
    tail: [],
    cache: { first: 0, lines: [] },
    stale: true,
    generation: (view.generation ?? 0) + 1,
  });
  view.window.replaceChildren();
  view.window.style.height = "0px";
  view.rows.style.height = "0px";
  view.pane.dataset.rows = 0;
}

// Each invocation's log is its own segment; lines run on across them.
const total = (view) => view.segments.reduce((sum, segment) => sum + segment.rows, 0);

function count(view) {
  const last = view.segments.at(-1);
  return last ? total(view) - last.rows + last.lines : 0;
}

const rowHeight = (view) => parseFloat(getComputedStyle(view.pane).lineHeight);
const tallest = (view) => parseFloat(getComputedStyle(view.pane).maxHeight);
const fits = (view) => Math.ceil(tallest(view) / rowHeight(view)) + 1;
// Scrolling moves one log line per row height, whatever the line wraps to.
const topLine = (view) => Math.round(view.pane.scrollTop / rowHeight(view));

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

function draw(element, lines) {
  const ansi = new AnsiUp();
  element.replaceChildren(
    ...lines.map((line) => {
      const row = document.createElement("div");
      row.innerHTML = ansi.ansi_to_html(line);
      return row;
    }),
  );
}

// Wrap the last lines offscreen to find the top line of the bottom view.
function settle(view, lines) {
  draw(view.measure, lines);
  const heights = [...view.measure.children].map((row) => row.offsetHeight);
  view.measure.replaceChildren();
  const limit = tallest(view);
  let filled = 0;
  let kept = 0;
  while (kept < heights.length && filled < limit) {
    kept += 1;
    filled += heights[heights.length - kept];
  }
  const height = Math.min(filled, limit);
  view.bottom = total(view) - kept;
  view.tail = lines.slice(lines.length - kept);
  view.window.style.height = `${height}px`;
  view.rows.style.height = `${view.bottom * rowHeight(view) + height}px`;
  view.pane.dataset.rows = total(view);
}

async function show(view) {
  const top = topLine(view);
  if (top >= view.bottom) {
    view.window.dataset.end = "";
    draw(view.window, view.tail);
    return;
  }
  const shown = fits(view);
  let { first, lines } = view.cache;
  if (top < first || Math.min(top + shown, total(view)) > first + lines.length) {
    const { generation } = view;
    first = Math.max(0, top - BUFFER);
    lines = await fetchRows(view, first, shown + 2 * BUFFER);
    if (lines === null || generation !== view.generation) return;
    view.cache = { first, lines };
  }
  delete view.window.dataset.end;
  draw(view.window, lines.slice(top - first, top - first + shown));
}

// One update runs at a time; anything that changes during it runs another.
async function update(view) {
  if (view.pane.hidden) return;
  if (view.loading) {
    view.again = true;
    return;
  }
  view.loading = true;
  do {
    view.again = false;
    if (view.stale) {
      view.stale = false;
      const { generation } = view;
      const wanted = fits(view);
      const lines = await fetchRows(view, Math.max(0, total(view) - wanted), wanted);
      if (lines === null || generation !== view.generation) {
        view.stale = true;
        if (lines === null) break;
        continue;
      }
      settle(view, lines);
      if (view.pinned) view.pane.scrollTop = view.pane.scrollHeight;
    }
    await show(view);
  } while (view.again || view.stale);
  view.loading = false;
}

for (const view of Object.values(views)) {
  clear(view);
  // At the bottom the view follows new output; scrolling up lets go of it.
  view.pane.addEventListener("scroll", () => {
    if (view.pane.hidden) return;
    view.pinned = topLine(view) >= view.bottom;
    update(view);
  });
}

for (const tab of tabs) {
  tab.addEventListener("click", () => {
    for (const other of tabs) other.setAttribute("aria-selected", String(other === tab));
    for (const [stream, view] of Object.entries(views)) view.pane.hidden = stream !== tab.dataset.stream;
    const view = views[tab.dataset.stream];
    view.stale = true;
    update(view);
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
  if (view.cache.first + view.cache.lines.length > settled) view.cache = { first: 0, lines: [] };
  view.stale = true;
  update(view);
  relabel();
});

source.addEventListener("end", (event) => {
  source.close();
  const code = JSON.parse(event.data);
  state.textContent = code === null ? "ended" : `exit ${code}`;
  state.classList.add(code === 0 ? "good" : "bad");
  log.dataset.ended = "";
});
