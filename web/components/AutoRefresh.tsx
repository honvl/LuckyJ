"use client";
// Asks the server for the page again every few seconds while it is open and in view. The waiting
// screen uses it: once the tutor is ready the page's own redirect opens the chat.
import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function AutoRefresh({ seconds }: { seconds: number }) {
  const router = useRouter();
  useEffect(() => {
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") router.refresh();
    }, seconds * 1000);
    return () => clearInterval(timer);
  }, [router, seconds]);
  return null;
}
