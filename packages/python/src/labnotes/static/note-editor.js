import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { pythonLanguage } from "@codemirror/lang-python";
import {
  HighlightStyle,
  Language,
  defineLanguageFacet,
  ensureSyntaxTree,
  languageDataProp,
  syntaxHighlighting,
  syntaxTree,
} from "@codemirror/language";
import { EditorState, StateField } from "@codemirror/state";
import { Decoration, EditorView, WidgetType, keymap } from "@codemirror/view";
import { inlinePreview } from "@atomic-editor/editor/inline-preview";
import { tags } from "@lezer/highlight";
import { GFM, parseCode, parser } from "@lezer/markdown";
import { DIFF_DELETE, DIFF_EQUAL, diff_match_patch } from "diff-match-patch";

// Built from @lezer/markdown rather than @codemirror/lang-markdown, which
// imports HTML, CSS and JavaScript support that notes never use.
const data = defineLanguageFacet();
const markdown = new Language(
  data,
  parser.configure([
    GFM,
    parseCode({
      codeParser: (info) => (info.split(/\s/)[0] === "python" ? pythonLanguage.parser : null),
    }),
    { props: [languageDataProp.add({ Document: data })] },
  ]),
  [],
  "markdown",
);

const style = HighlightStyle.define([
  { tag: [tags.processingInstruction, tags.contentSeparator], class: "md-mark" },
  { tag: [tags.keyword, tags.operatorKeyword, tags.bool, tags.null], class: "py-keyword" },
  { tag: [tags.string, tags.special(tags.string)], class: "py-string" },
  { tag: tags.comment, class: "py-comment" },
  { tag: tags.number, class: "py-number" },
  { tag: [tags.function(tags.variableName), tags.definition(tags.variableName)], class: "py-name" },
]);

class RunButton extends WidgetType {
  constructor(block, run) {
    super();
    this.block = block;
    this.run = run;
  }
  eq(other) {
    return other.block === this.block;
  }
  toDOM() {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "run";
    button.textContent = "Run";
    button.addEventListener("click", () => this.run(this.block, button));
    return button;
  }
  ignoreEvent() {
    return true;
  }
}

class CellOutput extends WidgetType {
  constructor(block, outputs) {
    super();
    this.block = block;
    this.outputs = outputs;
  }
  eq(other) {
    return other.block === this.block;
  }
  toDOM() {
    const cell = document.createElement("div");
    cell.className = "cell-below";
    if (!this.outputs.has(this.block)) {
      const output = document.createElement("output");
      output.className = "cell-output";
      this.outputs.set(this.block, output);
    }
    cell.append(this.outputs.get(this.block));
    return cell;
  }
  ignoreEvent() {
    return true;
  }
}

// Numbered in document order, as python_blocks numbers them on the server.
function cellWidgets(state, run, outputs) {
  const widgets = [];
  let block = 0;
  const tree = ensureSyntaxTree(state, state.doc.length, 200) ?? syntaxTree(state);
  tree.iterate({
    enter(node) {
      if (node.name !== "FencedCode") return;
      const info = node.node.getChild("CodeInfo");
      if (info && state.doc.sliceString(info.from, info.to).split(/\s/)[0] === "python") {
        const open = state.doc.lineAt(node.from);
        widgets.push(Decoration.widget({ widget: new RunButton(block, run), side: 1 }).range(open.to));
        widgets.push(
          Decoration.widget({ widget: new CellOutput(block, outputs), block: true, side: 1 }).range(node.to),
        );
        block += 1;
      }
      return false;
    },
  });
  return Decoration.set(widgets, true);
}

function cells(run, outputs) {
  return StateField.define({
    create: (state) => cellWidgets(state, run, outputs),
    update(widgets, tr) {
      if (!tr.docChanged && syntaxTree(tr.state) === syntaxTree(tr.startState)) return widgets;
      return cellWidgets(tr.state, run, outputs);
    },
    provide: (field) => EditorView.decorations.from(field),
  });
}

function show(status, message) {
  status.textContent = message;
  status.hidden = false;
}

const dmp = new diff_match_patch();

// Minimal changes, so the cursor and undo history survive.
function setText(view, text) {
  const changes = [];
  let at = 0;
  for (const [op, chunk] of dmp.diff_main(view.state.doc.toString(), text)) {
    if (op === DIFF_EQUAL) at += chunk.length;
    else if (op === DIFF_DELETE) {
      changes.push({ from: at, to: at + chunk.length });
      at += chunk.length;
    } else changes.push({ from: at, insert: chunk });
  }
  if (changes.length) view.dispatch({ changes });
}

export function edit(note, prose, status) {
  let base = JSON.parse(note.querySelector(".note-source").textContent);
  let timer;
  let deadline;
  let queue = Promise.resolve();

  const host = document.createElement("div");
  host.className = "editor";
  prose.replaceWith(host);

  const notice = (message) => {
    show(status, message);
    setTimeout(() => {
      if (status.textContent === message) status.hidden = true;
    }, 4000);
  };

  const run = (task) =>
    (queue = queue.then(task).catch((error) => show(status, `Not saved: ${error.message}`)));

  // Three-way: what changed on disk since base, applied onto the editor's text.
  // A patch that will not apply leaves the editor alone and keeps the disk
  // version in a sibling file, as Obsidian Sync does.
  const absorb = async (theirs) => {
    const ours = view.state.doc.toString();
    const [merged, applied] = dmp.patch_apply(dmp.patch_make(base, theirs), ours);
    const name = note.dataset.note;
    if (applied.every(Boolean)) {
      setText(view, merged);
      if (ours !== base) notice(`${name} was modified externally, merging changes automatically`);
    } else {
      const response = await fetch(note.dataset.conflictUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: theirs }),
      });
      if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
      const copy = (await response.json()).name;
      show(
        status,
        `${name} was modified externally and could not be merged. The outside version is saved as ${copy}.`,
      );
    }
    base = theirs;
  };

  const push = async () => {
    clearTimeout(timer);
    deadline = undefined;
    for (;;) {
      const content = view.state.doc.toString();
      if (content === base) return;
      const response = await fetch(note.dataset.saveUrl, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base, content }),
      });
      if (response.status !== 409) {
        if (response.ok) base = content;
        else show(status, `Not saved: ${response.status} ${response.statusText}`);
        return;
      }
      await absorb((await response.json()).content);
    }
  };

  const pull = async () => {
    const response = await fetch(note.dataset.saveUrl, { cache: "no-store" });
    if (!response.ok) return show(status, `Not synced: ${response.status} ${response.statusText}`);
    const theirs = await response.text();
    if (theirs === base) return;
    await absorb(theirs);
    await push();
  };

  const save = () => run(push);

  // The rendered note's outputs move into the editor, so a run started
  // before the editor loaded still shows its result.
  const outputs = new Map();
  for (const cell of prose.querySelectorAll(".cell")) {
    outputs.set(Number(cell.dataset.block), cell.querySelector(".cell-output"));
  }

  // The server runs the block from the file, so unsaved edits go first.
  const runCell = async (block, button) => {
    button.disabled = true;
    button.textContent = "Running";
    try {
      await save();
      const response = await fetch(note.dataset.runUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ block }),
      });
      outputs.get(block).innerHTML = response.ok
        ? await response.text()
        : `<pre class="error">${response.status} ${response.statusText}</pre>`;
      view.requestMeasure();
    } finally {
      button.disabled = false;
      button.textContent = "Run";
    }
  };

  const view = new EditorView({
    parent: host,
    state: EditorState.create({
      doc: base,
      extensions: [
        history(),
        keymap.of([
          { key: "Escape", run: () => (view.contentDOM.blur(), true) },
          ...defaultKeymap,
          ...historyKeymap,
        ]),
        markdown,
        syntaxHighlighting(style),
        inlinePreview({ onLinkClick: (url) => location.assign(new URL(url, location.href)) }),
        cells(runCell, outputs),
        EditorView.lineWrapping,
        EditorView.contentAttributes.of({ "aria-label": "Note" }),
        EditorView.updateListener.of((update) => {
          if (!update.docChanged) return;
          clearTimeout(timer);
          deadline ??= Date.now() + 2000;
          timer = setTimeout(save, Math.min(500, deadline - Date.now()));
        }),
      ],
    }),
  });
  return {
    view,
    pull: () => run(pull),
    detach: () => save(),
  };
}
