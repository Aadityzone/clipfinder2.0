import assert from "node:assert/strict";
import test from "node:test";
import { parseSupportedSourceUrl } from "./source-url";

test("source URL validation accepts supported providers and normalizes URLs", () => {
  const yt = parseSupportedSourceUrl("https://www.youtube.com/watch?v=abc123xyz");
  assert.equal(yt.type, "YOUTUBE");
  assert.equal(yt.sourceId, "abc123xyz");

  const ytShorts = parseSupportedSourceUrl("https://youtube.com/shorts/shortId123");
  assert.equal(ytShorts.type, "YOUTUBE");
  assert.equal(ytShorts.sourceId, "shortId123");

  const youtuBe = parseSupportedSourceUrl("https://youtu.be/shortYt123");
  assert.equal(youtuBe.type, "YOUTUBE");
  assert.equal(youtuBe.sourceId, "shortYt123");

  const twitchVod = parseSupportedSourceUrl("https://www.twitch.tv/videos/987654321");
  assert.equal(twitchVod.type, "TWITCH");
  assert.equal(twitchVod.sourceId, "987654321");

  const twitchClip = parseSupportedSourceUrl("https://clips.twitch.tv/BraveClipName-abc");
  assert.equal(twitchClip.type, "TWITCH");
  assert.equal(twitchClip.sourceId, "BraveClipName-abc");

  const kick = parseSupportedSourceUrl("https://kick.com/streamer_name");
  assert.equal(kick.type, "KICK");
  assert.equal(kick.sourceId, "streamer_name");

  const drive = parseSupportedSourceUrl("https://drive.google.com/file/d/driveFileId123/view");
  assert.equal(drive.type, "GOOGLE_DRIVE");
  assert.equal(drive.sourceId, "driveFileId123");

  const directMp4 = parseSupportedSourceUrl("https://cdn.example.com/videos/sample.mp4");
  assert.equal(directMp4.type, "URL");
  assert.equal(directMp4.isDirectUrl, true);

  const directWebm = parseSupportedSourceUrl("https://media.sample.org/archive.webm");
  assert.equal(directWebm.type, "URL");
  assert.equal(directWebm.isDirectUrl, true);
});

test("source URL validation rejects internal hosts, SSRF targets, lookalikes, credentials, and nonstandard ports", () => {
  for (const url of [
    "http://127.0.0.1/admin",
    "http://localhost:80/stream.mp4",
    "https://10.0.0.1/video.mp4",
    "https://192.168.1.1/video.mp4",
    "https://172.16.0.1/video.mp4",
    "https://169.254.169.254/latest/meta-data/",
    "https://youtube.com.attacker.test/watch?v=abc",
    "https://attacker.youtube.com/watch?v=abc",
    "https://user:pass@youtube.com/watch?v=abc",
    "https://youtube.com:8080/watch?v=abc",
    "javascript:alert(1)",
    "file:///etc/passwd",
    "not-a-valid-url",
  ]) {
    assert.throws(() => parseSupportedSourceUrl(url));
  }
});
