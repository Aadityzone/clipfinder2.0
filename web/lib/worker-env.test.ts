import assert from "node:assert/strict";
import test from "node:test";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";

test("the worker entry loads Next-style .env.local before the database client", () => {
  const worker = readFileSync(path.join(process.cwd(), "worker.ts"), "utf8");
  const firstImports = worker.slice(0, worker.indexOf("from"));
  assert.ok(
    firstImports.includes("./lib/load-env"),
    "worker.ts must import ./lib/load-env before any module that reads process.env.DATABASE_URL",
  );
  assert.ok(
    existsSync(path.join(process.cwd(), "lib", "load-env.ts")),
    "lib/load-env.ts must exist to load .env.local for non-Next entrypoints",
  );
});
