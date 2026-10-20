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

const expand = (group, open) => {
  group.classList.toggle("open", open);
  group.querySelector(".group-toggle").setAttribute("aria-expanded", String(open));
};

document.addEventListener("click", (event) => {
  const header = event.target.closest(".group-row");
  if (header) expand(header.parentElement, !header.parentElement.classList.contains("open"));
  const row = event.target.closest(".run-row");
  if (!row || getSelection().toString()) return;
  const record = row.nextElementSibling;
  record.hidden = !record.hidden;
  row.setAttribute("aria-expanded", String(!record.hidden));
});

const filters = document.querySelector("#run-filters");

if (filters) {
  const runs = document.querySelector("#runs");
  let pending;
  let latest;

  const refresh = async () => {
    clearTimeout(pending);
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(filters)) {
      if (value) params.append(key, value);
    }
    const url = new URL(location.href);
    url.search = params;
    latest = url.href;
    const response = await fetch(url);
    if (latest !== url.href) return;
    const fresh = new DOMParser()
      .parseFromString(await response.text(), "text/html")
      .querySelector("#runs");
    runs.querySelector(".narrowed")?.remove();
    const narrowed = fresh.querySelector(".narrowed");
    if (narrowed) runs.prepend(narrowed);
    runs.querySelector("thead tr").replaceWith(fresh.querySelector("thead tr"));
    const table = runs.querySelector("table");
    const opened = new Set([...table.querySelectorAll(".group.open")].map((group) => group.dataset.name));
    for (const body of table.querySelectorAll("tbody")) body.remove();
    for (const body of fresh.querySelectorAll("tbody")) {
      table.append(body);
      if (opened.has(body.dataset.name)) expand(body, true);
    }
    const summaries = fresh.querySelectorAll(".pick summary");
    runs.querySelectorAll(".pick summary").forEach((summary, index) => {
      summary.textContent = summaries[index].textContent;
    });
    history.replaceState(null, "", url);
  };

  filters.addEventListener("submit", (event) => {
    event.preventDefault();
    refresh();
  });
  document.addEventListener("input", (event) => {
    if (event.target.form !== filters || event.target.type !== "search") return;
    clearTimeout(pending);
    pending = setTimeout(refresh, 250);
  });
  document.addEventListener("change", (event) => {
    if (event.target.form === filters && event.target.type === "checkbox") refresh();
  });
  document.addEventListener("click", (event) => {
    for (const pick of runs.querySelectorAll(".pick[open]")) {
      if (!pick.contains(event.target)) pick.open = false;
    }
  });
}
