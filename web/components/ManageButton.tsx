"use client";
import { useState } from "react";

export default function ManageButton({ label }: { label: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      className="link-button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        const res = await fetch("/api/billing/portal", { method: "POST" });
        const body = await res.json().catch(() => ({}));
        if (body.url) window.location.href = body.url;
        else setBusy(false);
      }}
    >
      {label}
    </button>
  );
}
