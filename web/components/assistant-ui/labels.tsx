"use client";
// Labels the assistant-ui components show, so the Japanese chat page can replace the English ones.
import { createContext, useContext } from "react";

export type AuiLabels = {
  placeholder: string; newThread: string; untitled: string; search: string; rename: string; archive: string;
  archived: string; unarchive: string;
};

const ENGLISH: AuiLabels = {
  placeholder: "Send a message...",
  newThread: "New Thread",
  untitled: "New Chat",
  search: "Search threads",
  rename: "Rename",
  archive: "Archive",
  archived: "Archived",
  unarchive: "Restore",
};

export const AuiLabelsContext = createContext<AuiLabels>(ENGLISH);
export const useAuiLabels = () => useContext(AuiLabelsContext);
