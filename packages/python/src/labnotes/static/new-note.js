function show(note, button) {
  let tabs = document.querySelector(".tabs.sub");
  if (!tabs) {
    tabs = document.createElement("nav");
    tabs.className = "tabs sub";
    button.closest(".empty").replaceWith(tabs);
    tabs.append(button);
  }
  const search = `?tab=notebooks&note=${encodeURIComponent(note.dataset.note)}`;
  const link = document.createElement("a");
  link.href = search;
  link.textContent = note.dataset.note;
  link.setAttribute("aria-current", "page");
  for (const other of tabs.querySelectorAll("a")) other.removeAttribute("aria-current");
  button.before(link);
  const count = document.querySelector(".tabs:not(.sub) [aria-current] .count");
  count.textContent = Number(count.textContent) + 1;
  const old = document.querySelector(".note");
  if (old) old.replaceWith(note);
  else tabs.after(note);
  history.replaceState(null, "", search);
}

for (const button of document.querySelectorAll(".new-note")) {
  button.addEventListener("click", async () => {
    button.disabled = true;
    const response = await fetch(button.dataset.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    button.disabled = false;
    if (!response.ok) return;
    const holder = document.createElement("template");
    holder.innerHTML = await response.text();
    const note = holder.content.querySelector(".note");
    const { attach } = await import(button.dataset.module);
    show(note, button);
    attach(note, true);
  });
}
