const pad = (number) => String(number).padStart(2, "0");

const localize = (root) => {
  for (const time of root.querySelectorAll("time[datetime]")) {
    const at = new Date(time.dateTime);
    const day = `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
    time.textContent = `${day} ${pad(at.getHours())}:${pad(at.getMinutes())}:${pad(at.getSeconds())}`;
  }
};

localize(document);
new MutationObserver((records) => {
  for (const record of records) {
    for (const node of record.addedNodes) {
      if (node instanceof Element) localize(node);
    }
  }
}).observe(document.body, { childList: true, subtree: true });
