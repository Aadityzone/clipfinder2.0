export type SupportedSourceType = "YOUTUBE" | "TWITCH" | "KICK" | "GOOGLE_DRIVE" | "URL";

export interface ParsedSourceUrl {
  url: string;
  type: SupportedSourceType;
  sourceId?: string;
  isDirectUrl?: boolean;
}

const DIRECT_VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov", ".mkv", ".m4v"];

function isPrivateOrLoopbackHost(host: string): boolean {
  if (["localhost", "127.0.0.1", "0.0.0.0", "::1"].includes(host)) return true;
  // Check IPv4 private ranges: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 169.254.0.0/16
  const parts = host.split(".").map(Number);
  if (parts.length === 4 && parts.every((p) => !isNaN(p) && p >= 0 && p <= 255)) {
    if (parts[0] === 10) return true;
    if (parts[0] === 127) return true;
    if (parts[0] === 169 && parts[1] === 254) return true;
    if (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) return true;
    if (parts[0] === 192 && parts[1] === 168) return true;
    if (parts[0] === 0) return true;
  }
  return false;
}

export function parseSupportedSourceUrl(value: unknown): ParsedSourceUrl {
  if (typeof value !== "string" || value.length > 2048) {
    throw new Error("Enter a valid video URL.");
  }
  let parsed: URL;
  try {
    parsed = new URL(value.trim());
  } catch {
    throw new Error("Enter a valid video URL.");
  }

  if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password) {
    throw new Error("Video URLs must use HTTP or HTTPS and must not contain embedded credentials.");
  }

  const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
  if (isPrivateOrLoopbackHost(host)) {
    throw new Error("Video URLs pointing to local or private networks are forbidden.");
  }

  if (![undefined, "", "80", "443"].includes(parsed.port)) {
    throw new Error("Video URLs must use the provider's standard web port.");
  }

  // YouTube
  if (["youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"].includes(host)) {
    let sourceId: string | undefined;
    if (host.includes("youtu.be")) {
      sourceId = parsed.pathname.slice(1).split("/")[0] || undefined;
    } else if (parsed.pathname.startsWith("/shorts/")) {
      sourceId = parsed.pathname.split("/")[2] || undefined;
    } else {
      sourceId = parsed.searchParams.get("v") || undefined;
    }
    return { url: parsed.toString(), type: "YOUTUBE", sourceId };
  }

  // Twitch
  if (["twitch.tv", "www.twitch.tv", "m.twitch.tv", "clips.twitch.tv"].includes(host)) {
    let sourceId: string | undefined;
    const segments = parsed.pathname.split("/").filter(Boolean);
    if (segments[0] === "videos" && segments[1]) {
      sourceId = segments[1];
    } else if (host === "clips.twitch.tv" && segments[0]) {
      sourceId = segments[0];
    }
    return { url: parsed.toString(), type: "TWITCH", sourceId };
  }

  // Kick
  if (["kick.com", "www.kick.com"].includes(host)) {
    const segments = parsed.pathname.split("/").filter(Boolean);
    const sourceId = segments[0] || undefined;
    return { url: parsed.toString(), type: "KICK", sourceId };
  }

  // Google Drive
  if (["drive.google.com"].includes(host)) {
    const match = parsed.pathname.match(/\/file\/d\/([A-Za-z0-9_-]+)/) || parsed.search.match(/[?&]id=([A-Za-z0-9_-]+)/);
    const sourceId = match ? match[1] : undefined;
    return { url: parsed.toString(), type: "GOOGLE_DRIVE", sourceId };
  }

  // Direct public media URLs
  const pathnameLower = parsed.pathname.toLowerCase();
  if (DIRECT_VIDEO_EXTENSIONS.some((ext) => pathnameLower.endsWith(ext))) {
    return { url: parsed.toString(), type: "URL", isDirectUrl: true };
  }

  throw new Error("Unsupported source. Use a YouTube, Twitch, Kick, Google Drive, or direct public video URL.");
}
