"use client";
import { useState, useEffect, useCallback } from "react";
import { Chapter } from "@/types";
import { fetchChapters } from "@/lib/api";
import SubmitForm from "@/components/pipeline/SubmitForm";
import ChapterList from "@/components/pipeline/ChapterList";

export default function HomePage() {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchChapters();
      setChapters(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    // Poll for status updates every 4 seconds
    const interval = setInterval(load, 4000);
    return () => clearInterval(interval);
  }, [load]);

  return (
    <div className="min-h-screen">
      {/* Hero header */}
      <header className="bg-ink-900 text-white relative overflow-hidden">
        <div className="speed-lines absolute inset-0 opacity-10" />
        <div className="relative max-w-5xl mx-auto px-4 py-8">
          <div className="flex items-end gap-4">
            <div>
              <h1
                className="text-5xl font-black tracking-tight leading-none"
                style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: "0.05em" }}
              >
                MANGA OMNI-TRANSLATOR
              </h1>
              <p className="text-ink-300 mt-1 text-sm">
                Professional-grade OCR · Context-aware localization · High-fidelity typesetting
              </p>
            </div>
          </div>

          {/* Pipeline flow indicator */}
          <div className="mt-6 flex items-center gap-1 text-xs text-ink-400 overflow-x-auto pb-1 flex-nowrap">
            {["Scrape", "OCR", "Translate", "Inpaint", "Typeset", "Done"].map((step, i) => (
              <div key={step} className="flex items-center gap-1 shrink-0">
                {i > 0 && <span className="text-ink-600">→</span>}
                <span className="border border-ink-600 px-2 py-0.5 rounded text-ink-300">{step}</span>
              </div>
            ))}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: submit + info */}
          <div className="space-y-4">
            <SubmitForm onSubmitted={load} />

            <div className="manga-panel bg-white rounded p-4 text-xs text-ink-500 space-y-2">
              <p className="font-bold text-ink-700 uppercase tracking-wide">Supported sources</p>
              <ul className="space-y-1">
                <li>✓ MangaDex (via public API)</li>
                <li>✓ Generic sites (Playwright scraper)</li>
                <li>✓ Direct image upload (per page)</li>
              </ul>
              <p className="font-bold text-ink-700 uppercase tracking-wide pt-1">Pipeline</p>
              <ul className="space-y-1">
                <li>↓ manga-ocr + OpenCV bubble CV</li>
                <li>↓ Claude claude-opus-4-5 localization</li>
                <li>↓ LaMa inpainting (OpenCV fallback)</li>
                <li>↓ Shapely contour text wrapping</li>
              </ul>
            </div>

            <div className="manga-panel bg-yellow-50 border-yellow-300 rounded p-4 text-xs text-yellow-800">
              <p className="font-bold mb-1">Quick test (no scraper needed)</p>
              <p>Go into any chapter page and use "Upload Image" to process a single manga page directly.</p>
            </div>
          </div>

          {/* Right: chapter list */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-sm uppercase tracking-wide text-ink-500">
                Chapters ({chapters.length})
              </h2>
              <button
                onClick={load}
                className="text-xs text-ink-400 hover:text-ink-900 transition-colors"
              >
                ↺ Refresh
              </button>
            </div>
            <ChapterList chapters={chapters} loading={loading} />
          </div>
        </div>
      </main>
    </div>
  );
}
