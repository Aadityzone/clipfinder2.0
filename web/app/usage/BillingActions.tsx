"use client";

import { useState } from "react";

type BillingResponse = { url?: string; error?: string };

async function readResponse(response: Response): Promise<BillingResponse> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error("The billing service returned an unexpected response.");
  }

  try {
    return (await response.json()) as BillingResponse;
  } catch {
    throw new Error("The billing service returned an empty response.");
  }
}

export default function BillingActions({ hasCustomer }: { hasCustomer: boolean }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function openBilling(endpoint: string) {
    if (busy) return;
    setBusy(true);
    setError("");

    try {
      const response = await fetch(endpoint, { method: "POST" });
      const data = await readResponse(response);
      if (!response.ok) throw new Error(data.error || "Billing request failed.");
      if (!data.url) throw new Error("The billing service did not return a secure destination.");
      window.location.assign(data.url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Billing is unavailable. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-6">
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={busy}
          aria-busy={busy}
          onClick={() => void openBilling("/api/billing/checkout")}
          className="cf-button cf-button-primary disabled:cursor-wait disabled:opacity-55"
        >
          {busy ? "Opening secure checkout…" : "Upgrade to Pro"}
        </button>
        {hasCustomer && (
          <button
            type="button"
            disabled={busy}
            aria-busy={busy}
            onClick={() => void openBilling("/api/billing/portal")}
            className="cf-button cf-button-secondary disabled:cursor-wait disabled:opacity-55"
          >
            Manage subscription
          </button>
        )}
      </div>
      {error && (
        <p role="alert" aria-live="assertive" className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/[.07] p-3 text-xs leading-5 text-rose-300">
          {error}
        </p>
      )}
    </div>
  );
}
