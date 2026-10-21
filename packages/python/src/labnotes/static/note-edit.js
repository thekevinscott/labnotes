let detach = () => {};

export function attach(note, focus) {
  detach();
  const prose = note.querySelector(".prose");
  const status = note.querySelector(".edit-status");
  const source = JSON.parse(note.querySelector(".note-source").textContent);
  let editing = null;
  let attached = true;

  import(note.dataset.editor).then(
    ({ edit }) => {
      if (!attached) return;
      editing = edit(note, prose, status);
      if (focus) editing.view.focus();
    },
    () => {},
  );

  const changes = new EventSource(note.dataset.changesUrl);
  changes.addEventListener("message", (event) => {
    if (JSON.parse(event.data) !== note.dataset.note) return;
    if (editing) return editing.pull();
    // Without the editor the note is rendered HTML. A touch or a duplicate
    // event leaves the text alone, and reloading then is wasted.
    fetch(note.dataset.saveUrl, { cache: "no-store" })
      .then((response) => response.text())
      .then((text) => {
        if (text !== source) location.reload();
      });
  });

  detach = () => {
    attached = false;
    changes.close();
    editing?.detach();
  };
}

const note = document.querySelector(".note[data-save-url]");
if (note) attach(note, false);
