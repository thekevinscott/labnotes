// Safari ignores position: relative on <tr>, so a stretched ::after link covers the whole page.
// Delegated, so rows the runs filter swaps in stay clickable.
document.addEventListener("click", (event) => {
  const link = event.target.closest(".ledger tbody tr, .run-row")?.querySelector(".title-link, .run-link");
  if (!link || event.target.closest("a") || getSelection().toString()) return;
  if (event.metaKey || event.ctrlKey) window.open(link.href, "_blank");
  else location.href = link.href;
});
