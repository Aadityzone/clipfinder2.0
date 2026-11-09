"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

/**
 * Adaptive background refresher for list views (like Dashboard).
 * Pauses when the tab is hidden and throttles requests to avoid unnecessary database load.
 */
export default function RefreshWhenProcessing({
  active,
  intervalMs = 6000,
}: {
  active: boolean;
  intervalMs?: number;
}) {
  const router = useRouter();
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!active) return;

    let disposed = false;

    const schedule = () => {
      if (disposed) return;
      const isHidden = typeof document !== "undefined" && document.visibilityState === "hidden";
      const delay = isHidden ? Math.max(15000, intervalMs * 2) : Math.max(4000, intervalMs);

      timerRef.current = setTimeout(() => {
        if (!disposed && !isHidden) {
          router.refresh();
        }
        schedule();
      }, delay);
    };

    schedule();

    const handleVisibility = () => {
      if (document.visibilityState === "visible" && !disposed) {
        router.refresh();
      }
    };
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      disposed = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [active, intervalMs, router]);

  return null;
}
