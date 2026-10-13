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


test("local storage writes a stream and resolves the persisted object", async () => {
  const { mkdtemp, readFile, rm } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { Readable } = await import("node:stream");
  const { ensureLocalStorage, headStorage, saveStream } = await import("./storage");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-test-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "local";

  try {
    const key = "projects/project-1/source.bin";
    const expected = Buffer.from("clipfinder-local-storage-roundtrip");
    const savedPath = await saveStream(key, Readable.from([expected]));

    assert.equal(savedPath, path.resolve(root, key));
    assert.deepEqual(await readFile(savedPath), expected);
    assert.equal(await ensureLocalStorage(key), savedPath);
    assert.deepEqual(await headStorage(key), { size: expected.length, contentType: undefined });
  } finally {
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    await rm(root, { recursive: true, force: true });
  }
});

test("local storage reports missing objects instead of pretending they exist", async () => {
  const { mkdtemp, rm } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { ensureLocalStorage } = await import("./storage");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-missing-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "local";

  try {
    await assert.rejects(ensureLocalStorage("projects/missing/source.mp4"), /Storage file not found/);
  } finally {
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    await rm(root, { recursive: true, force: true });
  }
});


test("failed stream uploads never publish partial files or leave temporary artifacts", async () => {
  const { mkdtemp, readdir, rm, stat } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { Readable } = await import("node:stream");
  const { saveStream } = await import("./storage");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-partial-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "local";

  try {
    async function* brokenUpload() {
      yield Buffer.from("partial-data");
      throw new Error("simulated interrupted upload");
    }

    await assert.rejects(
      saveStream("projects/project-1/interrupted.mp4", Readable.from(brokenUpload())),
      /simulated interrupted upload/,
    );
    await assert.rejects(stat(path.join(root, "projects/project-1/interrupted.mp4")));
    assert.deepEqual(await readdir(path.join(root, "projects/project-1")), []);
  } finally {
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    await rm(root, { recursive: true, force: true });
  }
});


test("deleteStorage removes local files and tolerates already-missing files", async () => {
  const { mkdtemp, readFile, rm, stat } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { Readable } = await import("node:stream");
  const { deleteStorage, saveStream } = await import("./storage");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-delete-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "local";

  try {
    const key = "projects/project-1/deletable.mp4";
    const saved = await saveStream(key, Readable.from([Buffer.from("delete-me")]));
    assert.equal((await readFile(saved)).toString(), "delete-me");
    await deleteStorage(key);
    await assert.rejects(stat(saved));
    await assert.doesNotReject(deleteStorage(key));
  } finally {
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    await rm(root, { recursive: true, force: true });
  }
});

test("failed remote-cache download leaves no partial local object", async () => {
  const { mkdtemp, readdir, rm, stat } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { ensureLocalStorage } = await import("./storage");
  const { S3Client } = await import("@aws-sdk/client-s3");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-download-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  const previousBucket = process.env.S3_BUCKET;
  const originalSend = S3Client.prototype.send;
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "s3";
  process.env.S3_BUCKET = "unit-test-bucket";
  S3Client.prototype.send = async () => { throw new Error("simulated object missing"); };

  try {
    await assert.rejects(ensureLocalStorage("projects/project-1/source.mp4"), /simulated object missing/);
    await assert.rejects(stat(path.join(root, "projects/project-1/source.mp4")));
    assert.deepEqual(await readdir(path.join(root, "projects/project-1")), []);
  } finally {
    S3Client.prototype.send = originalSend;
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    if (previousBucket === undefined) delete process.env.S3_BUCKET;
    else process.env.S3_BUCKET = previousBucket;
    await rm(root, { recursive: true, force: true });
  }
});


test("storagePath rejects Windows drive-qualified absolute keys", () => {
  assert.throws(() => storagePath("C:\\outside.mp4"), /stay within MEDIA_STORAGE_ROOT/);
  assert.throws(() => storagePath("\\\\server\\share\\outside.mp4"), /stay within MEDIA_STORAGE_ROOT/);
});


test("object storage cache download cleans up partial data after a stream error", async () => {
  const { mkdtemp, readFile, readdir, rm, stat } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { Readable } = await import("node:stream");
  const { ensureLocalStorage } = await import("./storage");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-stream-error-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  const previousBucket = process.env.S3_BUCKET;
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "s3";
  process.env.S3_BUCKET = "unit-test-bucket";
  const { S3Client, GetObjectCommand } = await import("@aws-sdk/client-s3");
  const send = S3Client.prototype.send;
  S3Client.prototype.send = async function(command: any) {
    if (command instanceof GetObjectCommand) {
      async function* brokenBody() {
        yield Buffer.from("partial-remote-data");
        throw new Error("simulated S3 stream interruption");
      }
      return { Body: Readable.from(brokenBody()) } as any;
    }
    throw new Error("Unexpected S3 command");
  } as any;

  try {
    const target = path.join(root, "projects/project-1/source.mp4");
    await assert.rejects(ensureLocalStorage("projects/project-1/source.mp4"), /simulated S3 stream interruption/);
    await assert.rejects(stat(target));
    assert.deepEqual(await readdir(path.dirname(target)), []);
  } finally {
    S3Client.prototype.send = send;
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    if (previousBucket === undefined) delete process.env.S3_BUCKET;
    else process.env.S3_BUCKET = previousBucket;
    await rm(root, { recursive: true, force: true });
  }
});


test("local ranged reads return requested bytes and preserve total size metadata", async () => {
  const { mkdtemp, rm } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { Readable } = await import("node:stream");
  const { getStorageRange, saveStream } = await import("./storage");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-range-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "local";

  try {
    const bytes = Buffer.from("0123456789");
    await saveStream("projects/project-1/range.bin", Readable.from([bytes]));
    const result = await getStorageRange("projects/project-1/range.bin", 3, 6);
    const chunks: Buffer[] = [];
    for await (const chunk of Readable.fromWeb(result.body)) chunks.push(Buffer.from(chunk));
    assert.equal(Buffer.concat(chunks).toString(), "3456");
    assert.equal(result.size, 10);
  } finally {
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    await rm(root, { recursive: true, force: true });
  }
});


test("object-store deletion removes the remote key and local cache", async () => {
  const { mkdtemp, readFile, rm, writeFile } = await import("node:fs/promises");
  const { tmpdir } = await import("node:os");
  const { DeleteObjectCommand, S3Client } = await import("@aws-sdk/client-s3");
  const { deleteStorage } = await import("./storage");
  const root = await mkdtemp(path.join(tmpdir(), "clipfinder-storage-s3-delete-"));
  const previousRoot = process.env.MEDIA_STORAGE_ROOT;
  const previousProvider = process.env.STORAGE_PROVIDER;
  const previousBucket = process.env.S3_BUCKET;
  const originalSend = S3Client.prototype.send;
  const commands: unknown[] = [];
  process.env.MEDIA_STORAGE_ROOT = root;
  process.env.STORAGE_PROVIDER = "s3";
  process.env.S3_BUCKET = "unit-test-bucket";
  S3Client.prototype.send = async function(command: any) {
    commands.push(command);
    return {} as any;
  } as any;

  try {
    const key = "projects/project-1/delete-me.mp4";
    const localFile = path.join(root, key);
    await import("node:fs/promises").then(({ mkdir }) => mkdir(path.dirname(localFile), { recursive: true }));
    await writeFile(localFile, "cached");
    await deleteStorage(key);
    assert.equal(commands.length, 1);
    assert.ok(commands[0] instanceof DeleteObjectCommand);
    assert.equal((commands[0] as any).input.Bucket, "unit-test-bucket");
    assert.equal((commands[0] as any).input.Key, key);
    await assert.rejects(readFile(localFile));
  } finally {
    S3Client.prototype.send = originalSend;
    if (previousRoot === undefined) delete process.env.MEDIA_STORAGE_ROOT;
    else process.env.MEDIA_STORAGE_ROOT = previousRoot;
    if (previousProvider === undefined) delete process.env.STORAGE_PROVIDER;
    else process.env.STORAGE_PROVIDER = previousProvider;
    if (previousBucket === undefined) delete process.env.S3_BUCKET;
    else process.env.S3_BUCKET = previousBucket;
    await rm(root, { recursive: true, force: true });
  }
});
