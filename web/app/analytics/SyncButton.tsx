"use client";

import { useState } from "react";

type SyncResponse = { synced?: number; error?: string };

export default function SyncButton() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function sync() {
    if (busy) return;
    setBusy(true);
    setMessage("");
    setError("");

    try {
      const response = await fetch("/api/analytics/sync", { method: "POST" });
      const contentType = response.headers.get("content-type") ?? "";
      if (!contentType.includes("application/json")) {
        throw new Error("The analytics service returned an unexpected response.");
      }
      let data: SyncResponse;
      try {
        data = (await response.json()) as SyncResponse;
      } catch {
        throw new Error("The analytics service returned an empty or invalid response.");
      }
      if (!response.ok) throw new Error(data.error || "Analytics sync failed. Please try again.");

      const count = Number(data.synced);
      if (!Number.isSafeInteger(count) || count < 0) {
        throw new Error("The analytics service returned an invalid sync count.");
      }
      setMessage(`Synced ${count} YouTube ${count === 1 ? "video" : "videos"}. Refresh to view the latest data.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analytics sync failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex max-w-full flex-col items-end gap-2 sm:flex-row sm:items-center">
      <button
        type="button"
        onClick={() => void sync()}
        disabled={busy}
        aria-busy={busy}
        className="cf-button cf-button-secondary min-h-10 whitespace-nowrap text-xs disabled:cursor-wait disabled:opacity-50"
      >
        {busy ? "Syncing YouTube…" : "Sync analytics"}
      </button>
      {(message || error) && (
        <p
          role={error ? "alert" : "status"}
          aria-live={error ? "assertive" : "polite"}
          className={`max-w-64 text-right text-[10px] leading-4 sm:text-left ${error ? "text-rose-300" : "text-[#9ca6b4]"}`}
        >
          {error || message}
        </p>
      )}
    </div>
  );
}
