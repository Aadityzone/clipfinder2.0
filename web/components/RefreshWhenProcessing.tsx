"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Refresh server-rendered job state while at least one persisted job is active. */
export default function RefreshWhenProcessing({ active, intervalMs = 5000 }: { active: boolean; intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => router.refresh(), Math.max(3000, intervalMs));
    return () => clearInterval(timer);
  }, [active, intervalMs, router]);
  return null;
}
