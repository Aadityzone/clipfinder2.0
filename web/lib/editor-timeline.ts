export function clampSourceTime(time: number, mediaOffsetSeconds: number, mediaDurationSeconds: number) {
  const end = mediaOffsetSeconds + Math.max(0, mediaDurationSeconds);
  return Math.max(mediaOffsetSeconds, Math.min(end || time, time));
}

export function sourceToMediaTime(sourceTime: number, mediaOffsetSeconds: number) {
  return Math.max(0, sourceTime - mediaOffsetSeconds);
}

export function mediaToSourceTime(mediaTime: number, mediaOffsetSeconds: number) {
  return Math.max(0, mediaTime) + mediaOffsetSeconds;
}

export function snapSourceTimeToFrame(sourceTime: number, fps: number | null | undefined) {
  const frameRate = fps && Number.isFinite(fps) && fps > 0 ? fps : 30;
  return Math.round(sourceTime * frameRate) / frameRate;
}

export function snapSourceTimeToMarkers(sourceTime: number, markers: number[], toleranceSeconds = 0.12) {
  return markers.find(marker => Math.abs(marker - sourceTime) <= toleranceSeconds) ?? sourceTime;
}
