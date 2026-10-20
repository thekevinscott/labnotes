const summary = document.querySelector(".config-summary");
const open = document.querySelector(".config-open");
const dialog = document.querySelector(".config-file");

if (summary) {
  const fit = () => {
    open.hidden = summary.scrollWidth <= summary.clientWidth;
  };
  new ResizeObserver(fit).observe(summary);
  open.addEventListener("click", () => dialog.showModal());
  dialog.querySelector(".config-close").addEventListener("click", () => dialog.close());
}

for (const row of document.querySelectorAll(".run-row")) {
  row.addEventListener("click", () => {
    if (getSelection().toString()) return;
    const record = row.nextElementSibling;
    record.hidden = !record.hidden;
    row.setAttribute("aria-expanded", String(!record.hidden));
  });
}
