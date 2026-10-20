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

const opened = new Set();

document.addEventListener("click", (event) => {
  const group = event.target.closest(".group-row")?.parentElement;
  if (!group) return;
  const opening = !group.classList.contains("open");
  expand(group, opening);
  if (opening) opened.add(group.dataset.name);
  else opened.delete(group.dataset.name);
});

const filters = document.querySelector("#run-filters");

if (filters) {
  const runs = document.querySelector("#runs");
  let pending;
  let latest;

  const load = async (url) => {
    clearTimeout(pending);
    latest = url.href;
    const response = await fetch(url);
    if (latest !== url.href) return;
    const fresh = new DOMParser()
      .parseFromString(await response.text(), "text/html")
      .querySelector("#runs");
    const scroller = runs.querySelector(".scroll");
    const { scrollX, scrollY } = window;
    const { scrollLeft } = scroller;
    const header = runs.querySelector("thead tr");
    const focused = [...header.querySelectorAll("a.sort")].indexOf(document.activeElement);
    runs.querySelector(".narrowed")?.remove();
    const narrowed = fresh.querySelector(".narrowed");
    if (narrowed) runs.prepend(narrowed);
    const freshHeader = fresh.querySelector("thead tr");
    header.replaceWith(freshHeader);
    for (const input of filters.querySelectorAll("input[type=hidden]")) input.remove();
    filters.prepend(...fresh.querySelectorAll("#run-filters input[type=hidden]"));
    const table = runs.querySelector("table");
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
    scroller.scrollLeft = scrollLeft;
    window.scrollTo(scrollX, scrollY);
    if (focused >= 0) freshHeader.querySelectorAll("a.sort")[focused].focus({ preventScroll: true });
  };

  const refresh = () => {
    const params = new URLSearchParams();
    for (const [key, value] of new FormData(filters)) {
      if (value) params.append(key, value);
    }
    const url = new URL(location.href);
    url.search = params;
    return load(url);
  };

  runs.addEventListener("click", (event) => {
    const link = event.target.closest("a.sort");
    if (!link || event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    load(new URL(link.href));
  });

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
