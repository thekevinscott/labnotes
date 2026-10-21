import { AnsiUp } from "https://esm.sh/ansi_up@6.0.6";

const output = document.querySelector(".run-output");
const state = document.querySelector(".run-state");
const source = new EventSource(output.dataset.url);

let parsers = {};

// The server resends the whole log on each connection, so a reconnect starts clean.
source.addEventListener("open", () => {
  output.replaceChildren();
  parsers = {};
});

source.addEventListener("message", (event) => {
  const { stream, text } = JSON.parse(event.data);
  const following = output.scrollTop + output.clientHeight >= output.scrollHeight - 4;
  const chunk = document.createElement("span");
  chunk.className = stream;
  parsers[stream] ??= new AnsiUp();
  chunk.innerHTML = parsers[stream].ansi_to_html(text);
  output.append(chunk);
  if (following) output.scrollTop = output.scrollHeight;
});

source.addEventListener("end", (event) => {
  source.close();
  const code = JSON.parse(event.data);
  state.textContent = code === null ? "ended" : `exit ${code}`;
  state.classList.add(code === 0 ? "good" : "bad");
  output.dataset.ended = "";
});
