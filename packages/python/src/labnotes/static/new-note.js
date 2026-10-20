for (const button of document.querySelectorAll(".new-note")) {
  button.addEventListener("click", async () => {
    button.disabled = true;
    const response = await fetch(button.dataset.url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (response.ok) location.assign((await response.json()).url);
    else button.disabled = false;
  });
}
