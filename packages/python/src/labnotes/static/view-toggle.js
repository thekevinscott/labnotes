const ledger = document.querySelector(".ledger");
const buttons = document.querySelectorAll(".view-toggle button");

function show(view) {
  ledger.dataset.view = view;
  for (const button of buttons) {
    button.setAttribute("aria-pressed", String(button.dataset.view === view));
  }
  localStorage.setItem("labnotes.view", view);
}

for (const button of buttons) {
  button.addEventListener("click", () => show(button.dataset.view));
}
show(localStorage.getItem("labnotes.view") ?? "table");
