"use client";

import { useSyncExternalStore } from "react";
import { isBackendWaking, subscribeBackendWaking } from "@/lib/api";

export function LoadingNotice() {
  const waking = useSyncExternalStore(subscribeBackendWaking, isBackendWaking, () => false);

  if (!waking) return <p className="text-sm text-muted">Loading…</p>;

  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3 text-sm">
      <p className="font-medium text-foreground">Waking up the server…</p>
      <p className="mt-0.5 text-muted">
        The data server sleeps when idle on the free hosting tier. This can take up to a minute, then the dashboard
        loads on its own.
      </p>
    </div>
  );
}
