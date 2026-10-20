const note = document.querySelector(".note[data-save-url]");

if (note) {
  const prose = note.querySelector(".prose");
  const status = note.querySelector(".edit-status");
  const editor = import(note.dataset.editor);
  const source = JSON.parse(note.querySelector(".note-source").textContent);
  let editing = null;

  editor.then(
    () => prose.classList.add("editable"),
    () => {},
  );

  const open = async (event) => {
    if (event.target.closest("a, button, output") || getSelection().toString()) return;
    const { edit } = await editor;
    if (editing) return;
    prose.removeEventListener("click", open);
    editing = edit(note, prose, status);
  };
  prose.addEventListener("click", open);
  if (location.hash === "#edit") {
    history.replaceState(null, "", location.pathname + location.search);
    open({ target: prose });
  }

  new EventSource(note.dataset.changesUrl).addEventListener("message", (event) => {
    if (JSON.parse(event.data) !== note.dataset.note) return;
    if (editing) return editing.pull();
    // A touch or a duplicate event leaves the text alone, and reloading then
    // would swallow a click that is opening the editor.
    fetch(note.dataset.saveUrl, { cache: "no-store" })
      .then((response) => response.text())
      .then((text) => {
        if (text !== source) location.reload();
      });
  });
}
