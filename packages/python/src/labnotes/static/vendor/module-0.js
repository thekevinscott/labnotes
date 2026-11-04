import {
  ensureSyntaxTree,
  syntaxTree
} from "./chunk-GEEUUUG4.js";
import "./chunk-WY7M62LG.js";
import "./chunk-YCKCXZK7.js";
import "./chunk-QWPOAZ6R.js";
import {
  Decoration,
  EditorView,
  ViewPlugin,
  WidgetType,
  keymap
} from "./chunk-IZLH2FXZ.js";
import "./chunk-Q4XXUJJK.js";
import "./chunk-5VWU6OLT.js";
import "./chunk-3IHNMG2F.js";
import {
  EditorSelection,
  Facet,
  Prec,
  StateEffect,
  StateField
} from "./chunk-UJ3XWCZW.js";
import "./chunk-CDEKZD6V.js";
import "./chunk-JSBRDJBE.js";

// node_modules/@atomic-editor/editor/dist/tree-progress.js
var treeGrowthEffect = StateEffect.define();
var GROWTH_THRESHOLD = 8192;
var TICK_BUDGET_MS = 30;
function scheduleIdle(cb) {
  if (typeof window.requestIdleCallback === "function") {
    return { kind: "idle", id: window.requestIdleCallback(() => cb()) };
  }
  return { kind: "raf", id: window.requestAnimationFrame(() => cb()) };
}
function cancelIdle(handle) {
  if (handle.kind === "idle" && typeof window.cancelIdleCallback === "function") {
    window.cancelIdleCallback(handle.id);
  } else if (handle.kind === "raf") {
    window.cancelAnimationFrame(handle.id);
  }
}
var treeProgressPlugin = ViewPlugin.fromClass(class {
  constructor(view) {
    Object.defineProperty(this, "view", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: void 0
    });
    Object.defineProperty(this, "_lastTreeLen", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: void 0
    });
    Object.defineProperty(this, "_idleHandle", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: null
    });
    Object.defineProperty(this, "_destroyed", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: false
    });
    this.view = view;
    this._lastTreeLen = syntaxTree(view.state).length;
    this._schedule();
  }
  update(update) {
    if (update.docChanged) {
      this._lastTreeLen = syntaxTree(update.state).length;
      this._schedule();
    }
  }
  destroy() {
    this._destroyed = true;
    if (this._idleHandle !== null) {
      cancelIdle(this._idleHandle);
      this._idleHandle = null;
    }
  }
  _schedule() {
    if (this._idleHandle !== null)
      return;
    this._idleHandle = scheduleIdle(() => {
      this._idleHandle = null;
      if (!this._destroyed)
        this._tick();
    });
  }
  _tick() {
    const state = this.view.state;
    const docLen = state.doc.length;
    if (this._lastTreeLen >= docLen)
      return;
    const ensured = ensureSyntaxTree(state, docLen, TICK_BUDGET_MS);
    const newLen = (ensured ?? syntaxTree(state)).length;
    if (newLen >= this._lastTreeLen + GROWTH_THRESHOLD || newLen >= docLen) {
      const previous = this._lastTreeLen;
      this._lastTreeLen = newLen;
      try {
        this.view.dispatch({ effects: treeGrowthEffect.of(null) });
      } catch {
        this._lastTreeLen = previous;
        return;
      }
    }
    if (newLen < docLen)
      this._schedule();
  }
});

// node_modules/@atomic-editor/editor/dist/read-only.js
var readOnlyFacet = Facet.define({
  combine: (values) => values.length ? values[values.length - 1] : false
});

// node_modules/@atomic-editor/editor/dist/inline-preview.js
function defaultOnLinkClick(url) {
  try {
    window.open(url, "_blank", "noopener,noreferrer");
  } catch {
  }
}
var FREEZE_TAIL_MS = 100;
var setFrozen = StateEffect.define();
var previewFrozenField = StateField.define({
  create: () => false,
  update(prev, tr) {
    for (const effect of tr.effects) {
      if (effect.is(setFrozen))
        return effect.value;
    }
    return prev;
  }
});
function linkIconHitTarget(event, root) {
  const target = event.target;
  if (!(target instanceof Element))
    return null;
  const linkEl = target.closest(".cm-atomic-link");
  if (!linkEl || root && !root.contains(linkEl))
    return null;
  const rects = Array.from(linkEl.getClientRects());
  if (rects.length === 0)
    return null;
  const lastRect = rects[rects.length - 1];
  const emSize = parseFloat(window.getComputedStyle(linkEl).fontSize);
  const iconZone = emSize * 1.25;
  const onIcon = event.clientX >= lastRect.right - iconZone && event.clientX <= lastRect.right && event.clientY >= lastRect.top && event.clientY <= lastRect.bottom;
  return onIcon ? linkEl : null;
}
function linkElementFromEvent(event, root) {
  const target = event.target;
  if (!(target instanceof Element))
    return null;
  const linkEl = target.closest(".cm-atomic-link");
  if (!linkEl || root && !root.contains(linkEl))
    return null;
  return linkEl;
}
var freezeMousePlugin = ViewPlugin.fromClass(class {
  constructor(view) {
    Object.defineProperty(this, "view", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: view
    });
    Object.defineProperty(this, "down", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: false
    });
    Object.defineProperty(this, "releaseTimer", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: null
    });
    Object.defineProperty(this, "onDown", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: (event) => {
        if (event.button !== 0)
          return;
        if (this.view.state.facet(readOnlyFacet))
          return;
        const target = event.target;
        if (!(target instanceof Node) || !this.view.contentDOM.contains(target)) {
          return;
        }
        if (linkIconHitTarget(event, this.view.contentDOM)) {
          event.preventDefault();
          event.stopImmediatePropagation();
          return;
        }
        this.down = true;
        if (this.releaseTimer != null) {
          window.clearTimeout(this.releaseTimer);
          this.releaseTimer = null;
        }
        if (!this.view.state.field(previewFrozenField)) {
          this.view.dispatch({ effects: setFrozen.of(true) });
        }
      }
    });
    Object.defineProperty(this, "onUp", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: () => {
        if (!this.down)
          return;
        this.down = false;
        if (this.releaseTimer != null)
          window.clearTimeout(this.releaseTimer);
        this.releaseTimer = window.setTimeout(() => {
          this.releaseTimer = null;
          if (!this.view.state.field(previewFrozenField))
            return;
          try {
            this.view.dispatch({ effects: setFrozen.of(false) });
          } catch {
          }
        }, FREEZE_TAIL_MS);
      }
    });
    view.dom.addEventListener("pointerdown", this.onDown, true);
    window.addEventListener("pointerup", this.onUp);
    window.addEventListener("pointercancel", this.onUp);
  }
  update(_) {
  }
  destroy() {
    this.view.dom.removeEventListener("pointerdown", this.onDown, true);
    window.removeEventListener("pointerup", this.onUp);
    window.removeEventListener("pointercancel", this.onUp);
    if (this.releaseTimer != null)
      window.clearTimeout(this.releaseTimer);
  }
});
var LINE_CLASS_BY_BLOCK = {
  ATXHeading1: "cm-atomic-h1",
  ATXHeading2: "cm-atomic-h2",
  ATXHeading3: "cm-atomic-h3",
  ATXHeading4: "cm-atomic-h4",
  ATXHeading5: "cm-atomic-h5",
  ATXHeading6: "cm-atomic-h6",
  SetextHeading1: "cm-atomic-h1",
  SetextHeading2: "cm-atomic-h2",
  Blockquote: "cm-atomic-blockquote",
  FencedCode: "cm-atomic-fenced-code"
};
var HIDEABLE_SYNTAX = /* @__PURE__ */ new Set([
  "HeaderMark",
  "EmphasisMark",
  "CodeMark",
  "CodeInfo",
  "LinkMark",
  "LinkTitle",
  "StrikethroughMark",
  "HighlightMark",
  "QuoteMark"
]);
var LINK_CHILD_SYNTAX = /* @__PURE__ */ new Set(["LinkMark", "URL", "LinkTitle"]);
var INLINE_MARK_CLASS = {
  StrongEmphasis: "cm-atomic-strong",
  Emphasis: "cm-atomic-em",
  InlineCode: "cm-atomic-inline-code",
  Strikethrough: "cm-atomic-strike",
  Highlight: "cm-atomic-highlight",
  Link: "cm-atomic-link"
};
function linkDestinationUrl(link, doc) {
  const labelClose = link.getChildren("LinkMark").find((mark) => doc.sliceString(mark.from, mark.to) === "]");
  if (!labelClose)
    return null;
  return link.getChildren("URL").find((url) => url.from >= labelClose.to) ?? null;
}
var BulletWidget = class extends WidgetType {
  eq() {
    return true;
  }
  toDOM() {
    const span = document.createElement("span");
    span.className = "cm-atomic-list-marker cm-atomic-bullet";
    span.textContent = "\u2022";
    return span;
  }
  ignoreEvent() {
    return false;
  }
};
var BULLET_WIDGET = new BulletWidget();
var TaskCheckboxWidget = class extends WidgetType {
  constructor(checked) {
    super();
    Object.defineProperty(this, "checked", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: checked
    });
  }
  eq(other) {
    return other.checked === this.checked;
  }
  toDOM(view) {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = this.checked;
    input.className = "cm-atomic-list-marker cm-atomic-task-checkbox";
    input.setAttribute("contenteditable", "false");
    input.addEventListener("mousedown", (e) => {
      e.preventDefault();
      e.stopPropagation();
    });
    input.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const pos = view.posAtDOM(input);
      if (pos < 0)
        return;
      const current = view.state.doc.sliceString(pos, pos + 3);
      const next = /\[x\]/i.test(current) ? "[ ]" : "[x]";
      if (current === next)
        return;
      view.dispatch({ changes: { from: pos, to: pos + 3, insert: next } });
    });
    return input;
  }
  ignoreEvent(event) {
    return event.type === "mousedown" || event.type === "click";
  }
};
function pushReplace(ranges, doc, from, to, spec = {}) {
  if (from >= to)
    return;
  const startLine = doc.lineAt(from);
  if (to <= startLine.to) {
    ranges.push(Decoration.replace(spec).range(from, to));
    return;
  }
  let cursor = from;
  let firstSegment = true;
  while (cursor < to) {
    const line = doc.lineAt(cursor);
    const segEnd = Math.min(to, line.to);
    if (segEnd > cursor) {
      ranges.push(Decoration.replace(firstSegment ? spec : {}).range(cursor, segEnd));
      firstSegment = false;
    }
    cursor = line.to + 1;
  }
}
var LIST_BASE_EM = 0.8;
var LIST_ALCOVE_EM = 1.2;
var LIST_LEVEL_EM = 0.6;
function nearestListItem(node) {
  for (let current = node; current; current = current.parent) {
    if (current.name === "ListItem")
      return current;
  }
  return null;
}
function listItemDepth(item) {
  let depth = 0;
  for (let parent = item.parent; parent; parent = parent.parent) {
    if (parent.name === "ListItem")
      depth++;
  }
  return depth;
}
function sameListItem(a, b) {
  return a?.name === "ListItem" && a.from === b.from && a.to === b.to;
}
function buildInlineDecorations(view) {
  const { state } = view;
  const { doc } = state;
  const ranges = [];
  const readOnly = state.facet(readOnlyFacet);
  const activeLines = /* @__PURE__ */ new Set();
  if (view.hasFocus && !readOnly) {
    for (const r of state.selection.ranges) {
      const firstLine = doc.lineAt(r.from).number;
      const lastLine = doc.lineAt(r.to).number;
      for (let n = firstLine; n <= lastLine; n++)
        activeLines.add(n);
    }
  }
  const tree = ensureSyntaxTree(state, state.doc.length, 200) ?? syntaxTree(state);
  const activeLinkStarts = /* @__PURE__ */ new Set();
  tree.iterate({
    enter: (node) => {
      if (node.name === "FencedCode") {
        const firstLine = doc.lineAt(node.from).number;
        const lastLine = doc.lineAt(node.to).number;
        let anyActive = false;
        for (let n = firstLine; n <= lastLine; n++) {
          if (activeLines.has(n)) {
            anyActive = true;
            break;
          }
        }
        if (anyActive) {
          for (let n = firstLine; n <= lastLine; n++)
            activeLines.add(n);
        }
      }
      if (node.name === "Link" && view.hasFocus) {
        for (const range of state.selection.ranges) {
          if (range.from <= node.to && range.to >= node.from) {
            activeLinkStarts.add(node.from);
            break;
          }
        }
      }
      const lineClass = LINE_CLASS_BY_BLOCK[node.name];
      if (lineClass) {
        const firstLine = doc.lineAt(node.from);
        const lastLine = doc.lineAt(node.to);
        for (let n = firstLine.number; n <= lastLine.number; n++) {
          const line = doc.line(n);
          ranges.push(Decoration.line({ class: lineClass }).range(line.from));
        }
      }
      const markClass = INLINE_MARK_CLASS[node.name];
      if (markClass && node.from < node.to) {
        ranges.push(Decoration.mark({ class: markClass }).range(node.from, node.to));
      }
      if (HIDEABLE_SYNTAX.has(node.name) && node.from < node.to) {
        const lineNum = doc.lineAt(node.from).number;
        let shouldHide;
        if (LINK_CHILD_SYNTAX.has(node.name)) {
          let parent = node.node.parent;
          while (parent && parent.name !== "Link" && parent.name !== "Image") {
            parent = parent.parent;
          }
          if (parent && parent.name === "Link") {
            shouldHide = !activeLinkStarts.has(parent.from);
          } else {
            shouldHide = !activeLines.has(lineNum);
          }
        } else {
          shouldHide = !activeLines.has(lineNum);
        }
        if (shouldHide) {
          let hideTo = node.to;
          if (node.name === "HeaderMark" || node.name === "QuoteMark") {
            while (hideTo < doc.length && doc.sliceString(hideTo, hideTo + 1) === " ") {
              hideTo++;
            }
          }
          pushReplace(ranges, doc, node.from, hideTo);
        }
      }
      if (node.name === "URL" && node.from < node.to) {
        const parent = node.node.parent;
        if (parent?.name === "Link") {
          const destination = linkDestinationUrl(parent, doc);
          if (destination?.from === node.from && !activeLinkStarts.has(parent.from)) {
            pushReplace(ranges, doc, node.from, node.to);
          }
        } else {
          ranges.push(Decoration.mark({ class: "cm-atomic-link" }).range(node.from, node.to));
        }
      }
      if (node.name === "Escape" && node.to - node.from >= 2) {
        const lineNum = doc.lineAt(node.from).number;
        if (!activeLines.has(lineNum)) {
          pushReplace(ranges, doc, node.from, node.from + 1);
        }
      }
      if (node.name === "ListMark" && node.from < node.to) {
        const line = doc.lineAt(node.from);
        const taskLead = line.text.match(/^(\s*[-*+]\s+)\[[ xX]\]/);
        const taskFrom = taskLead != null ? line.from + taskLead[1].length : void 0;
        const listItem = nearestListItem(node.node);
        if (listItem) {
          const depth = listItemDepth(listItem);
          const padding = LIST_BASE_EM + LIST_ALCOVE_EM + depth * LIST_LEVEL_EM;
          const firstLine = doc.lineAt(listItem.from);
          const lastLine = doc.lineAt(listItem.to);
          for (let number = firstLine.number; number <= lastLine.number; number++) {
            const ownedLine = doc.line(number);
            const contentOffset = ownedLine.text.search(/\S/);
            if (contentOffset < 0)
              continue;
            const contentFrom = ownedLine.from + contentOffset;
            const owner = nearestListItem(tree.resolve(contentFrom, 1));
            if (!sameListItem(owner, listItem))
              continue;
            const markerLine = ownedLine.number === line.number;
            ranges.push(Decoration.line({
              attributes: {
                style: `padding-left: ${padding}em; text-indent: ${markerLine ? `-${LIST_ALCOVE_EM}` : "0"}em`
              }
            }).range(ownedLine.from));
            if (contentFrom > ownedLine.from) {
              pushReplace(ranges, doc, ownedLine.from, contentFrom);
            }
          }
        }
        const hasTrailingSpace = doc.sliceString(node.to, node.to + 1) === " ";
        const markEnd = hasTrailingSpace ? node.to + 1 : node.to;
        if (taskFrom !== void 0) {
          pushReplace(ranges, doc, node.from, taskFrom);
        } else {
          const markText = doc.sliceString(node.from, node.to);
          if (markText === "-" || markText === "*" || markText === "+") {
            pushReplace(ranges, doc, node.from, markEnd, { widget: BULLET_WIDGET });
          } else {
            ranges.push(Decoration.mark({ class: "cm-atomic-list-marker" }).range(node.from, node.to));
            if (hasTrailingSpace) {
              pushReplace(ranges, doc, node.to, markEnd);
            }
          }
        }
      }
      if (node.name === "HorizontalRule") {
        const line = doc.lineAt(node.from);
        if (!activeLines.has(line.number)) {
          ranges.push(Decoration.line({ class: "cm-atomic-hr" }).range(line.from));
          pushReplace(ranges, doc, line.from, line.to);
        }
      }
      if (node.name === "Image" && node.from < node.to) {
        const imageLine = doc.lineAt(node.from);
        const lineNum = imageLine.number;
        if (!activeLines.has(lineNum)) {
          pushReplace(ranges, doc, node.from, node.to);
        }
      }
      if (node.name === "TaskMarker" && node.from < node.to) {
        const markText = doc.sliceString(node.from, node.to);
        const checked = /\[x\]/i.test(markText);
        const hasTrailingSpace = node.to < doc.length && doc.sliceString(node.to, node.to + 1) === " ";
        const replaceTo = hasTrailingSpace ? node.to + 1 : node.to;
        pushReplace(ranges, doc, node.from, replaceTo, {
          widget: new TaskCheckboxWidget(checked)
        });
        if (checked) {
          const lineNum = doc.lineAt(node.from).number;
          const line = doc.line(lineNum);
          ranges.push(Decoration.line({ class: "cm-atomic-task-done" }).range(line.from));
        }
      }
    }
  });
  if (view.hasFocus) {
    const head = state.selection.main.head;
    const line = doc.lineAt(head);
    if (activeLines.has(line.number)) {
      supplementMidTypingEmphasis(line.text, line.from, head - line.from, ranges);
    }
  }
  return Decoration.set(ranges, true);
}
var MID_TYPING_DELIMITERS = [
  { delim: "**", contentCls: "cm-atomic-strong", delimCls: "cm-atomic-strong-mark" },
  { delim: "__", contentCls: "cm-atomic-strong", delimCls: "cm-atomic-strong-mark" },
  { delim: "~~", contentCls: "cm-atomic-strike", delimCls: "cm-atomic-strike-mark" },
  { delim: "==", contentCls: "cm-atomic-highlight", delimCls: "cm-atomic-highlight-mark" },
  { delim: "*", contentCls: "cm-atomic-em", delimCls: "cm-atomic-em-mark" },
  { delim: "_", contentCls: "cm-atomic-em", delimCls: "cm-atomic-em-mark" }
];
function supplementMidTypingEmphasis(text, lineFrom, localCursor, out) {
  const consumed = new Uint8Array(text.length);
  for (const { delim, contentCls, delimCls } of MID_TYPING_DELIMITERS) {
    const dLen = delim.length;
    const isUnderscore = delim === "_" || delim === "__";
    let searchFrom = 0;
    while (searchFrom < text.length) {
      const open = indexOfUnconsumed(text, delim, searchFrom, consumed);
      if (open < 0)
        break;
      if (isUnderscore && open > 0 && /\w/.test(text[open - 1])) {
        searchFrom = open + dLen;
        continue;
      }
      const close = indexOfUnconsumed(text, delim, open + dLen, consumed);
      if (close < 0)
        break;
      for (let i = open; i < close + dLen; i++)
        consumed[i] = 1;
      const contentFrom = open + dLen;
      const contentTo = close;
      if (contentFrom < contentTo && localCursor > open && localCursor < close + dLen) {
        out.push(Decoration.mark({ class: contentCls }).range(lineFrom + contentFrom, lineFrom + contentTo));
        out.push(Decoration.mark({ class: delimCls }).range(lineFrom + open, lineFrom + contentFrom));
        out.push(Decoration.mark({ class: delimCls }).range(lineFrom + contentTo, lineFrom + close + dLen));
      }
      searchFrom = close + dLen;
    }
  }
}
function indexOfUnconsumed(text, needle, from, consumed) {
  let i = from;
  while (i <= text.length - needle.length) {
    const found = text.indexOf(needle, i);
    if (found < 0)
      return -1;
    let isConsumed = false;
    for (let k = found; k < found + needle.length; k++) {
      if (consumed[k]) {
        isConsumed = true;
        break;
      }
    }
    if (!isConsumed)
      return found;
    i = found + 1;
  }
  return -1;
}
var inlinePreviewPlugin = ViewPlugin.fromClass(class {
  constructor(view) {
    Object.defineProperty(this, "decorations", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: void 0
    });
    this.decorations = buildInlineDecorations(view);
  }
  update(update) {
    const prevFrozen = update.startState.field(previewFrozenField);
    const nextFrozen = update.state.field(previewFrozenField);
    const justUnfroze = prevFrozen && !nextFrozen;
    if (nextFrozen && !justUnfroze && !update.docChanged)
      return;
    let treeGrew = false;
    for (const tr of update.transactions) {
      for (const effect of tr.effects) {
        if (effect.is(treeGrowthEffect)) {
          treeGrew = true;
          break;
        }
      }
      if (treeGrew)
        break;
    }
    const readOnlyChanged = update.startState.facet(readOnlyFacet) !== update.state.facet(readOnlyFacet);
    if (justUnfroze || update.docChanged || update.selectionSet || update.focusChanged || treeGrew || readOnlyChanged) {
      this.decorations = buildInlineDecorations(update.view);
    }
  }
}, {
  decorations: (v) => v.decorations
});
function fencedCodeSelectionDecorations(view) {
  const selections = view.state.selection.ranges.filter((range) => !range.empty);
  if (selections.length === 0)
    return Decoration.none;
  const ranges = [];
  const tree = syntaxTree(view.state);
  for (const selection of selections) {
    tree.iterate({
      from: selection.from,
      to: selection.to,
      enter(node) {
        if (node.name !== "FencedCode")
          return;
        const from = Math.max(node.from, selection.from);
        const to = Math.min(node.to, selection.to);
        if (from < to) {
          ranges.push(Decoration.mark({ class: "cm-atomic-fenced-selection" }).range(from, to));
        }
        return false;
      }
    });
  }
  return Decoration.set(ranges, true);
}
var fencedCodeSelectionPlugin = ViewPlugin.fromClass(class {
  constructor(view) {
    Object.defineProperty(this, "decorations", {
      enumerable: true,
      configurable: true,
      writable: true,
      value: void 0
    });
    this.decorations = fencedCodeSelectionDecorations(view);
  }
  update(update) {
    if (update.docChanged || update.selectionSet) {
      this.decorations = fencedCodeSelectionDecorations(update.view);
    }
  }
}, {
  decorations: (plugin) => plugin.decorations
});
function insertTightListItem(view) {
  const { state } = view;
  const sel = state.selection.main;
  if (!sel.empty)
    return false;
  const from = sel.from;
  const line = state.doc.lineAt(from);
  const tree = syntaxTree(state);
  let cursor = tree.resolveInner(from, -1).cursor();
  let inBulletList = false;
  for (; ; ) {
    if (cursor.name === "BulletList") {
      inBulletList = true;
      break;
    }
    if (!cursor.parent())
      break;
  }
  if (!inBulletList)
    return false;
  const lineText = state.doc.sliceString(line.from, line.to);
  const prefix = lineText.match(/^(\s*)([-*+])(\s+)/);
  if (!prefix)
    return false;
  const [whole, indent, marker] = prefix;
  const rest = lineText.slice(whole.length);
  const taskMatch = rest.match(/^(\[[ xX]\])(\s*)/);
  const taskPrefixLen = taskMatch ? taskMatch[0].length : 0;
  const contentAfterPrefix = rest.slice(taskPrefixLen);
  if (!contentAfterPrefix.trim()) {
    const depth = Math.floor(indent.length / 2);
    if (depth >= 1) {
      const outerIndent = indent.slice(0, indent.length - 2);
      const continuation2 = taskMatch ? `${marker} [ ] ` : `${marker} `;
      const replacement = `${outerIndent}${continuation2}`;
      view.dispatch({
        changes: { from: line.from, to: line.to, insert: replacement },
        selection: EditorSelection.cursor(line.from + replacement.length)
      });
    } else {
      view.dispatch({
        changes: { from: line.from, to: line.to, insert: "" },
        selection: EditorSelection.cursor(line.from)
      });
    }
    return true;
  }
  const continuation = taskMatch ? `${marker} [ ] ` : `${marker} `;
  const insert = `
${indent}${continuation}`;
  view.dispatch({
    changes: { from, to: from, insert },
    selection: EditorSelection.cursor(from + insert.length)
  });
  return true;
}
function makeLinkClickHandler(onLinkClick) {
  return EditorView.domEventHandlers({
    click: (event, view) => {
      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
        return false;
      if (event.button !== 0)
        return false;
      const linkEl = view.state.facet(readOnlyFacet) ? linkElementFromEvent(event, view.contentDOM) : linkIconHitTarget(event, view.contentDOM);
      if (!linkEl)
        return false;
      const pos = view.posAtDOM(linkEl);
      if (pos < 0)
        return false;
      const tree = syntaxTree(view.state);
      let node = tree.resolveInner(pos, 1);
      let visibleUrl = null;
      while (node && node.name !== "Link") {
        if (node.name === "URL")
          visibleUrl = node;
        node = node.parent;
      }
      const urlNode = node ? linkDestinationUrl(node, view.state.doc) : visibleUrl;
      if (!urlNode)
        return false;
      const url = view.state.doc.sliceString(urlNode.from, urlNode.to);
      if (!url)
        return false;
      event.preventDefault();
      event.stopPropagation();
      onLinkClick(url);
      return true;
    }
  });
}
function inlinePreview(config = {}) {
  const { onLinkClick = defaultOnLinkClick } = config;
  return [
    previewFrozenField,
    inlinePreviewPlugin,
    fencedCodeSelectionPlugin,
    freezeMousePlugin,
    treeProgressPlugin,
    makeLinkClickHandler(onLinkClick),
    // Prec.highest to beat @codemirror/lang-markdown's own Enter
    // handler, which is registered internally by the `markdown()`
    // extension (not just via the exported markdownKeymap) and
    // otherwise wins precedence.
    Prec.highest(keymap.of([{ key: "Enter", run: insertTightListItem }]))
  ];
}
export {
  inlinePreview
};
