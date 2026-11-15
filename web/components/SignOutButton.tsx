"use client";
import { signOut } from "next-auth/react";

export default function SignOutButton({ label }: { label: string }) {
  return (
    <button type="button" className="link-button" onClick={() => signOut({ callbackUrl: "/login" })}>
      {label}
    </button>
  );
}
