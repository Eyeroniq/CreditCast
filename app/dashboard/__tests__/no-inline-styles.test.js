// Component library (6.3.5): visual rules live in CSS, not in style={{...}}.
// An inline style may only pass data-driven CSS variables (e.g. a marker's
// position as "--at"); the stylesheet decides how they are used.
import { readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = process.cwd();   // vitest runs from app/dashboard (vitest.config.mjs)

function jsxFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name);
    return e.isDirectory() ? jsxFiles(p) : /\.jsx?$/.test(e.name) ? [p] : [];
  });
}

/** The expression inside each style={...}, found by matching braces. */
function styleExpressions(src) {
  const out = [];
  for (let i = src.indexOf("style={"); i !== -1; i = src.indexOf("style={", i + 1)) {
    let depth = 0, j = i + 6;
    do { if (src[j] === "{") depth++; else if (src[j] === "}") depth--; j++; } while (depth > 0 && j < src.length);
    out.push(src.slice(i + 7, j - 1));
  }
  return out;
}

const objectKeys = (expr) => [...expr.matchAll(/[{,]\s*(["']?)([\w-]+)\1\s*:/g)].map((m) => m[2]);

describe("inline styles", () => {
  const files = ["app", "components"].flatMap((d) => jsxFiles(join(ROOT, d)));

  it("finds the source files", () => {
    expect(files.length).toBeGreaterThan(20);
  });

  it("only set CSS custom properties", () => {
    const offenders = files.flatMap((f) =>
      styleExpressions(readFileSync(f, "utf8")).flatMap((expr) =>
        objectKeys(expr).filter((k) => !k.startsWith("--")).map((k) => `${relative(ROOT, f)}: ${k}`)));
    expect(offenders).toEqual([]);
  });

  it("catches a plain style property", () => {
    expect(objectKeys(styleExpressions('<div style={{ marginTop: 16, "--at": x }} />')[0])).toEqual(["marginTop", "--at"]);
  });
});
