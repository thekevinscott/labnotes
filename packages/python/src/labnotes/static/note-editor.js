import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { pythonLanguage } from "@codemirror/lang-python";
import {
  HighlightStyle,
  Language,
  defineLanguageFacet,
  languageDataProp,
  syntaxHighlighting,
  syntaxTree,
} from "@codemirror/language";
import { EditorState, RangeSetBuilder } from "@codemirror/state";
import { Decoration, EditorView, ViewPlugin, keymap } from "@codemirror/view";
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
  { tag: tags.heading1, class: "md-h1" },
  { tag: tags.heading2, class: "md-h2" },
  { tag: tags.heading3, class: "md-h3" },
  { tag: [tags.heading4, tags.heading5, tags.heading6], class: "md-h4" },
  { tag: tags.strong, class: "md-strong" },
  { tag: tags.emphasis, class: "md-em" },
  { tag: tags.strikethrough, class: "md-strike" },
  { tag: [tags.link, tags.url], class: "md-link" },
  { tag: tags.monospace, class: "md-code" },
  { tag: tags.quote, class: "md-quote" },
  { tag: [tags.processingInstruction, tags.contentSeparator], class: "md-mark" },
  { tag: [tags.keyword, tags.operatorKeyword, tags.bool, tags.null], class: "py-keyword" },
  { tag: [tags.string, tags.special(tags.string)], class: "py-string" },
  { tag: tags.comment, class: "py-comment" },
  { tag: tags.number, class: "py-number" },
  { tag: [tags.function(tags.variableName), tags.definition(tags.variableName)], class: "py-name" },
]);

// Markup is hidden except on the lines the cursor is on, as in Obsidian.
const HIDDEN = new Set(["HeaderMark", "EmphasisMark", "CodeMark", "StrikethroughMark"]);
const hide = Decoration.replace({});
const codeLine = Decoration.line({ class: "md-code-line" });

function decorate(view) {
  const builder = new RangeSetBuilder();
  const { state } = view;
  const active = new Set();
  for (const range of state.selection.ranges) {
    for (let n = state.doc.lineAt(range.from).number; n <= state.doc.lineAt(range.to).number; n++) active.add(n);
  }
  for (const { from, to } of view.visibleRanges) {
    syntaxTree(state).iterate({
      from,
      to,
      enter(node) {
        if (node.name === "FencedCode") {
          for (let at = node.from; at <= node.to; ) {
            const line = state.doc.lineAt(at);
            builder.add(line.from, line.from, codeLine);
            at = line.to + 1;
          }
          return false;
        }
        if (!HIDDEN.has(node.name) || active.has(state.doc.lineAt(node.from).number)) return;
        let end = node.to;
        if (node.name === "HeaderMark" && state.doc.sliceString(end, end + 1) === " ") end += 1;
        builder.add(node.from, end, hide);
      },
    });
  }
  return builder.finish();
}

const livePreview = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = decorate(view);
    }
    update(update) {
      if (update.docChanged || update.selectionSet || update.viewportChanged) {
        this.decorations = decorate(update.view);
      }
    }
  },
  { decorations: (plugin) => plugin.decorations },
);

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

  const close = async () => {
    await save();
    document.removeEventListener("mousedown", outside);
    location.reload();
  };
  const outside = (event) => {
    if (!note.contains(event.target)) close();
  };
  document.addEventListener("mousedown", outside);

  const view = new EditorView({
    parent: host,
    state: EditorState.create({
      doc: base,
      extensions: [
        history(),
        keymap.of([{ key: "Escape", run: () => (close(), true) }, ...defaultKeymap, ...historyKeymap]),
        markdown,
        syntaxHighlighting(style),
        livePreview,
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
  view.focus();
  return { pull: () => run(pull) };
}
