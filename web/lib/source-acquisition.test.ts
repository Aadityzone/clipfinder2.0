import assert from "node:assert/strict";
import test from "node:test";
import { parseSupportedSourceUrl } from "./source-url";
import { storagePath } from "./storage";

test("source acquisition URL parser extracts video IDs and tags direct media", () => {
  const ytStandard = parseSupportedSourceUrl("https://www.youtube.com/watch?v=9bZkp7q19f0");
  assert.equal(ytStandard.type, "YOUTUBE");
  assert.equal(ytStandard.sourceId, "9bZkp7q19f0");

  const ytShorts = parseSupportedSourceUrl("https://www.youtube.com/shorts/abcdef12345");
  assert.equal(ytShorts.type, "YOUTUBE");
  assert.equal(ytShorts.sourceId, "abcdef12345");

  const youtuBe = parseSupportedSourceUrl("https://youtu.be/shortId1234");
  assert.equal(youtuBe.type, "YOUTUBE");
  assert.equal(youtuBe.sourceId, "shortId1234");

  const twitchVod = parseSupportedSourceUrl("https://www.twitch.tv/videos/123456789");
  assert.equal(twitchVod.type, "TWITCH");
  assert.equal(twitchVod.sourceId, "123456789");

  const twitchClip = parseSupportedSourceUrl("https://clips.twitch.tv/SlickClipName-XYZ");
  assert.equal(twitchClip.type, "TWITCH");
  assert.equal(twitchClip.sourceId, "SlickClipName-XYZ");

  const directMp4 = parseSupportedSourceUrl("https://media.org/videos/video_sample.mp4");
  assert.equal(directMp4.type, "URL");
  assert.equal(directMp4.isDirectUrl, true);

  const directWebm = parseSupportedSourceUrl("https://media.org/videos/video_sample.webm");
  assert.equal(directWebm.type, "URL");
  assert.equal(directWebm.isDirectUrl, true);
});

test("source acquisition rejects unauthorized schemes and SSRF attempts", () => {
  const forbiddenUrls = [
    "http://127.0.0.1/video.mp4",
    "http://localhost/video.mp4",
    "https://10.0.0.1/media.mp4",
    "https://192.168.0.1/media.mp4",
    "https://172.20.0.1/media.mp4",
    "file:///etc/shadow",
    "ftp://example.com/video.mp4",
    "data:video/mp4;base64,AAAA",
    "https://admin:secret@youtube.com/watch?v=123",
  ];
  for (const url of forbiddenUrls) {
    assert.throws(
      () => parseSupportedSourceUrl(url),
      /Video URLs|Unsupported source/,
      `Expected ${url} to be rejected`
    );
  }
});

test("storage path sanitization prevents directory traversal on media artifacts", () => {
  assert.throws(() => storagePath("../../../etc/passwd"));
  assert.throws(() => storagePath("..\\..\\windows\\system32"));
  assert.throws(() => storagePath("/absolute/path/file.mp4"));
  assert.throws(() => storagePath(""));
  assert.throws(() => storagePath("uploads/test\0file.mp4"));

  const validPath = storagePath("sources/test-user/video.mp4");
  assert.ok(validPath.includes("sources"));
  assert.ok(validPath.endsWith("video.mp4"));
});
