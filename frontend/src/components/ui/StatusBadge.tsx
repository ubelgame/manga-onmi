"use client";
import { ProcessingStatus } from "@/types";

const LABELS: Record<ProcessingStatus, string> = {
  queued: "Queued",
  scraping: "Scraping…",
  ocr: "OCR…",
  translating: "Translating…",
  inpainting: "Inpainting…",
  typesetting: "Typesetting…",
  done: "Done",
  failed: "Failed",
};

const ICONS: Record<ProcessingStatus, string> = {
  queued: "○",
  scraping: "⬇",
  ocr: "◈",
  translating: "言",
  inpainting: "✦",
  typesetting: "A",
  done: "✓",
  failed: "✕",
};

export default function StatusBadge({ status, size = "sm" }: { status: ProcessingStatus; size?: "sm" | "md" }) {
  const isAnimated = ["scraping", "ocr", "translating", "inpainting", "typesetting"].includes(status);
  const base = size === "md"
    ? "inline-flex items-center gap-2 px-3 py-1.5 rounded text-sm font-medium"
    : "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium";

  return (
    <span className={`${base} status-${status}`}>
      <span className={isAnimated ? "animate-pulse-slow" : ""}>{ICONS[status]}</span>
      {LABELS[status]}
    </span>
  );
}
