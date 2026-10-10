import assert from "node:assert/strict";
import path from "node:path";
import test from "node:test";
import { storagePath, storageRoot } from "./storage";

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
