export type SupportedSourceType = "YOUTUBE" | "TWITCH" | "KICK" | "GOOGLE_DRIVE";
export function parseSupportedSourceUrl(value: unknown): { url: string; type: SupportedSourceType } {
  if (typeof value !== "string" || value.length > 2048) throw new Error("Enter a valid video URL.");
  let parsed: URL;
  try { parsed = new URL(value.trim()); } catch { throw new Error("Enter a valid video URL."); }
  if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
    throw new Error("Video URLs must use HTTP or HTTPS and must not contain embedded credentials.");
  }
  const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  if (![undefined, "", "80", "443"].includes(parsed.port)) throw new Error("Video URLs must use the provider's standard web port.");
  if (["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"].includes(host)) return { url: parsed.toString(), type: "YOUTUBE" };
  if (["twitch.tv", "www.twitch.tv", "m.twitch.tv"].includes(host)) return { url: parsed.toString(), type: "TWITCH" };
  if (["kick.com", "www.kick.com"].includes(host)) return { url: parsed.toString(), type: "KICK" };
  if (["drive.google.com"].includes(host)) return { url: parsed.toString(), type: "GOOGLE_DRIVE" };
  throw new Error("Unsupported source. Use a YouTube, Twitch, Kick, or Google Drive URL.");
}
