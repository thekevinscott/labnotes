const format = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const pad = (n) => String(n).padStart(2, "0");
  if (hours) return `${hours}h ${pad(minutes % 60)}m`;
  if (minutes) return `${minutes}m ${pad(seconds % 60)}s`;
  return `${seconds}s`;
};

const tick = () => {
  for (const cell of document.querySelectorAll(".elapsed[data-since]")) {
    const seconds = Math.max(0, Math.floor((Date.now() - Date.parse(cell.dataset.since)) / 1000));
    cell.textContent = format(seconds);
  }
};

tick();
setInterval(tick, 1000);
