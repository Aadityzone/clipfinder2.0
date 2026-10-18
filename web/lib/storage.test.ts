import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { mkdir, rm, unlink, writeFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { headStorage, putFile, storagePath, storageRoot } from "./storage";

test("storagePath keeps valid relative keys inside the configured root", () => {
  assert.equal(
    storagePath("clips/user-123/clip.mp4"),
    path.resolve(storageRoot(), "clips", "user-123", "clip.mp4"),
  );
});

test("storagePath rejects parent-directory traversal", () => {
  assert.throws(() => storagePath("../outside.mp4"), /stay within MEDIA_STORAGE_ROOT/);
  assert.throws(() => storagePath("clips/../../outside.mp4"), /stay within MEDIA_STORAGE_ROOT/);
});

test("storagePath rejects absolute paths", () => {
  assert.throws(
    () => storagePath(path.resolve(process.cwd(), "outside.mp4")),
    /stay within MEDIA_STORAGE_ROOT/,
  );
});

test("storagePath rejects empty and null-byte keys", () => {
  assert.throws(() => storagePath(""), /non-empty relative path/);
  assert.throws(() => storagePath("clips/\0outside.mp4"), /non-empty relative path/);
});

test("local putFile confirms a nonempty artifact exists at its storage key", async () => {
  const priorRoot = process.env.MEDIA_STORAGE_ROOT;
  const root = path.join(process.cwd(), `.tmp-storage-${randomUUID()}`);
  process.env.MEDIA_STORAGE_ROOT = root;
  const key = "renders/verified.mp4";
  const file = storagePath(key);
  await mkdir(path.dirname(file), { recursive: true });
  try {
    await writeFile(file, "rendered-video");
    await putFile(key, file, "video/mp4");
    assert.equal((await headStorage(key)).size, 14);
    await writeFile(file, "");
    await assert.rejects(() => putFile(key, file, "video/mp4"), /empty media artifact/);
  } finally {
    await unlink(file).catch(() => {});
    await rm(root, { recursive: true, force: true });
    if (priorRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = priorRoot;
  }
});
