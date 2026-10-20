const note = document.querySelector(".note[data-save-url]");

if (note) {
  const prose = note.querySelector(".prose");
  const status = note.querySelector(".edit-status");
  const editor = import(note.dataset.editor);
  editor.then(
    () => prose.classList.add("editable"),
    () => {
      status.textContent = "Editing needs the network: the editor loads from esm.sh.";
      status.hidden = false;
    },
  );

  const open = async (event) => {
    if (event.target.closest("a, button, output") || getSelection().toString()) return;
    const { edit } = await editor;
    if (!prose.isConnected) return;
    prose.removeEventListener("click", open);
    edit(note, prose, status);
  };
  prose.addEventListener("click", open);
}
