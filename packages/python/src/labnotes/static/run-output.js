import { AnsiUp } from "/static/vendor/ansi_up.js";

const log = document.querySelector(".run-log");
const state = document.querySelector(".run-state");
const source = new EventSource(log.dataset.url);
const tabs = [...log.querySelectorAll('[role="tab"]')];
const panes = Object.fromEntries(
  [...log.querySelectorAll(".run-output")].map((pane) => [pane.dataset.stream, pane]),
);

const blocks = document.querySelector(".run-blocks");

let parsers = {};
let counts = {};
let streaming = new Map();

function relabel() {
  for (const tab of tabs) {
    tab.querySelector(".count").textContent = counts[tab.dataset.stream] ?? 0;
  }
}

// A hidden pane can't scroll, so each pane remembers whether it was at the end.
const pinned = new Map(Object.values(panes).map((pane) => [pane, true]));

function pin(pane) {
  if (pinned.get(pane)) pane.scrollTop = pane.scrollHeight;
}

for (const pane of Object.values(panes)) {
  pane.addEventListener("scroll", () => {
    if (!pane.hidden) pinned.set(pane, pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 4);
  });
}

for (const tab of tabs) {
  tab.addEventListener("click", () => {
    for (const other of tabs) other.setAttribute("aria-selected", String(other === tab));
    for (const [stream, pane] of Object.entries(panes)) pane.hidden = stream !== tab.dataset.stream;
    pin(panes[tab.dataset.stream]);
  });
}

// The server resends the whole log on each connection, so a reconnect starts clean.
source.addEventListener("open", () => {
  for (const pane of Object.values(panes)) pane.replaceChildren();
  parsers = {};
  counts = {};
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
  const { stream, text } = JSON.parse(event.data);
  const output = panes[stream];
  const chunk = document.createElement("span");
  chunk.className = stream;
  parsers[stream] ??= new AnsiUp();
  chunk.innerHTML = parsers[stream].ansi_to_html(text);
  output.append(chunk);
  pin(output);
  counts[stream] = (counts[stream] ?? 0) + text.split("\n").length - 1;
  relabel();
});

source.addEventListener("end", (event) => {
  source.close();
  const code = JSON.parse(event.data);
  state.textContent = code === null ? "ended" : `exit ${code}`;
  state.classList.add(code === 0 ? "good" : "bad");
  log.dataset.ended = "";
});
