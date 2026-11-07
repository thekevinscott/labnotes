const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

function cell(index) {
  const button = {
    disabled: false,
    textContent: "Run",
    addEventListener(_event, handler) {
      this.click = handler;
    },
  };
  const output = { innerHTML: "" };
  return {
    dataset: { block: String(index) },
    button,
    output,
    querySelector(selector) {
      return selector === ".run" ? button : output;
    },
  };
}

function setup(fetch) {
  const cells = [cell(0), cell(1)];
  const note = {
    dataset: { runUrl: "/run" },
    querySelectorAll() {
      return cells;
    },
  };
  const document = {
    querySelectorAll(selector) {
      return selector === ".note[data-run-url]" ? [note] : [];
    },
  };
  vm.runInNewContext(readFileSync(join(__dirname, "run-cell.js"), "utf8"), {
    document,
    fetch,
  });
  return cells;
}

test("cells from one note send requests in click order", async () => {
  const calls = [];
  let releaseFirst;
  const firstResponse = new Promise((resolve) => {
    releaseFirst = resolve;
  });
  const cells = setup(async (_url, options) => {
    const block = JSON.parse(options.body).block;
    calls.push(block);
    return block === 0
      ? firstResponse
      : { ok: true, text: async () => "second" };
  });

  const first = cells[0].button.click();
  const second = cells[1].button.click();
  await new Promise(setImmediate);
  assert.deepEqual(calls, [0]);
  assert.equal(cells[1].button.textContent, "Queued");
  releaseFirst({ ok: true, text: async () => "first" });
  await Promise.all([first, second]);
  assert.deepEqual(calls, [0, 1]);
  assert.equal(cells[0].output.innerHTML, "first");
  assert.equal(cells[1].output.innerHTML, "second");
  assert.equal(cells[1].button.textContent, "Run");
});

test("a failed request does not block the next queued cell", async () => {
  const calls = [];
  const cells = setup(async (_url, options) => {
    const block = JSON.parse(options.body).block;
    calls.push(block);
    if (block === 0) throw new Error("network error");
    return { ok: true, text: async () => "second" };
  });

  const first = cells[0].button.click();
  const second = cells[1].button.click();
  await assert.rejects(first, /network error/);
  await second;
  assert.deepEqual(calls, [0, 1]);
  assert.equal(cells[1].output.innerHTML, "second");
});
