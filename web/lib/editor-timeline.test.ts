import test from "node:test";
import assert from "node:assert/strict";
import { clampSourceTime, mediaToSourceTime, snapSourceTimeToFrame, snapSourceTimeToMarkers, sourceToMediaTime } from "./editor-timeline";

test("source and downloaded-media timestamps stay aligned for ranged ingestion", () => {
  assert.equal(sourceToMediaTime(65.25, 60), 5.25);
  assert.equal(mediaToSourceTime(5.25, 60), 65.25);
  assert.equal(clampSourceTime(20, 60, 30), 60);
  assert.equal(clampSourceTime(120, 60, 30), 90);
});

test("frame snapping uses the source frame rate and falls back safely", () => {
  assert.equal(snapSourceTimeToFrame(1.04, 25), 1.04);
  assert.equal(snapSourceTimeToFrame(1.04, null), 1.0333333333333334);
});

test("timeline snapping uses nearby real clip and source boundaries", () => {
  assert.equal(snapSourceTimeToMarkers(10.08, [0, 10, 40]), 10);
  assert.equal(snapSourceTimeToMarkers(10.2, [0, 10, 40]), 10.2);
});
