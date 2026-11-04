// Refresh the browser modules and their license notices from the pinned packages.
// Run: node scripts/refresh-editor-vendor.mjs
import { readFile, writeFile, mkdir, mkdtemp, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const pins = JSON.parse(await readFile(join(root, "scripts/vendor-editor-pins.json"), "utf8"));
const packageRoot = join(root, "packages/python/src/labnotes");
const vendor = join(packageRoot, "static/vendor");
const work = await mkdtemp(join(tmpdir(), "labnotes-vendor-"));
const entryName = (name) => name.replace(/^@/, "").replaceAll("/", "-");

try {
  const versions = Object.values(pins).map((pin) => pin.slice(0, pin.lastIndexOf("@")) + "@" + pin.slice(pin.lastIndexOf("@") + 1).split("/")[0]);
  const dependencies = Object.fromEntries(versions.map((pin) => {
    const at = pin.lastIndexOf("@");
    return [pin.slice(0, at), pin.slice(at + 1)];
  }));
  await writeFile(join(work, "package.json"), JSON.stringify({ private: true, type: "module", dependencies, devDependencies: { esbuild: "0.25.12" } }));
  execFileSync("pnpm", ["install", "--ignore-scripts"], { cwd: work, stdio: "inherit" });
  const require = createRequire(join(work, "package.json"));
  const esbuild = require("esbuild");
  // diff-match-patch publishes CommonJS; expose the named exports the editor uses.
  await writeFile(join(work, "diff-match-patch-entry.js"),
    'import diff_match_patch from "diff-match-patch";\nexport { diff_match_patch };\nexport const DIFF_DELETE = -1;\nexport const DIFF_EQUAL = 0;\n');
  const entryPoints = Object.fromEntries(Object.keys(pins).map((name) => {
    const source = name === "@atomic-editor/editor/inline-preview"
      ? join(work, "node_modules/@atomic-editor/editor/dist/inline-preview.js")
      : name === "diff-match-patch" ? join(work, "diff-match-patch-entry.js") : name;
    return [entryName(name), source];
  }));
  await rm(vendor, { recursive: true, force: true });
  await mkdir(vendor, { recursive: true });
  const build = await esbuild.build({ entryPoints, absWorkingDir: work, outdir: vendor, bundle: true, splitting: true, format: "esm", platform: "browser", target: "es2022", minify: false, legalComments: "none", metafile: true });
  const imports = Object.fromEntries(Object.keys(pins).filter((name) => name !== "ansi_up").map((name) => [name, `/static/vendor/${entryName(name)}.js`]));
  const importMap = `{# Vendored modules share chunks so @codemirror/state loads exactly once. Refresh with node scripts/refresh-editor-vendor.mjs. #}\n<script type="importmap">\n${JSON.stringify({ imports }, null, 2)}\n</script>\n`;
  await writeFile(join(packageRoot, "templates/editor_imports.html"), importMap);
  const notices = [];
  const bundledPackages = new Map(Object.keys(build.metafile.inputs).flatMap((path) => {
    const at = path.lastIndexOf("node_modules/");
    if (at < 0) return [];
    const parts = path.slice(at + "node_modules/".length).split("/");
    const name = parts[0].startsWith("@") ? `${parts[0]}/${parts[1]}` : parts[0];
    return [[join(work, path.slice(0, at), "node_modules", name), name]];
  }));
  for (const [folder, name] of [...bundledPackages].sort((a, b) => a[0].localeCompare(b[0]))) {
    const { version } = JSON.parse(await readFile(join(folder, "package.json"), "utf8"));
    const names = await readdir(folder);
    const licenseName = names.find((file) => /^(license|licence)(\.|$)/i.test(file));
    if (!licenseName) throw new Error(`Missing license in ${name}@${version}`);
    notices.push(`${name}@${version}\n${"=".repeat(name.length + version.length + 1)}\n${await readFile(join(folder, licenseName), "utf8")}`);
  }
  await writeFile(join(vendor, "THIRD_PARTY_NOTICES"), notices.join("\n\n"));
} finally {
  await rm(work, { recursive: true, force: true });
}
