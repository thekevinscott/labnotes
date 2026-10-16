for (const note of document.querySelectorAll(".note[data-run-url]")) {
  for (const cell of note.querySelectorAll(".cell")) {
    const button = cell.querySelector(".run");
    const output = cell.querySelector(".cell-output");
    button.addEventListener("click", async () => {
      button.disabled = true;
      button.textContent = "Running";
      try {
        const response = await fetch(note.dataset.runUrl, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ block: Number(cell.dataset.block) }),
        });
        output.innerHTML = response.ok
          ? await response.text()
          : `<pre class="error">${response.status} ${response.statusText}</pre>`;
      } finally {
        button.disabled = false;
        button.textContent = "Run";
      }
    });
  }
}
