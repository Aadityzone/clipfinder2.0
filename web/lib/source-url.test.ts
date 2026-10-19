import assert from "node:assert/strict";
import test from "node:test";
import { parseSupportedSourceUrl } from "./source-url";

test("source URL validation accepts supported providers and normalizes URLs", () => {
  assert.equal(parseSupportedSourceUrl("https://www.youtube.com/watch?v=abc").type, "YOUTUBE");
  assert.equal(parseSupportedSourceUrl("https://www.twitch.tv/videos/123").type, "TWITCH");
  assert.equal(parseSupportedSourceUrl("https://kick.com/channel").type, "KICK");
  assert.equal(parseSupportedSourceUrl("https://drive.google.com/file/d/abc/view").type, "GOOGLE_DRIVE");
});

test("source URL validation rejects internal hosts, lookalikes, credentials, and nonstandard ports", () => {
  for (const url of [
    "http://127.0.0.1/admin",
    "https://youtube.com.attacker.test/watch?v=abc",
    "https://attacker.youtube.com/watch?v=abc",
    "https://user:pass@youtube.com/watch?v=abc",
    "https://youtube.com:8080/watch?v=abc",
  ]) assert.throws(() => parseSupportedSourceUrl(url));
});
