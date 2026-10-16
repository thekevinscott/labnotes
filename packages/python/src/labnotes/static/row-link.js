// Safari ignores position: relative on <tr>, so a stretched ::after link covers the whole page.
for (const row of document.querySelectorAll(".ledger tbody tr")) {
  const link = row.querySelector(".title-link");
  row.addEventListener("click", (event) => {
    if (event.target.closest("a") || getSelection().toString()) return;
    if (event.metaKey || event.ctrlKey) window.open(link.href, "_blank");
    else location.href = link.href;
  });
}
