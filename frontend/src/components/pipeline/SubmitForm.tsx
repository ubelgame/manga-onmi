"use client";
import { useState } from "react";
import { submitChapter } from "@/lib/api";

interface Props {
  onSubmitted: () => void;
}

export default function SubmitForm({ onSubmitted }: Props) {
  const [url, setUrl] = useState("");
  const [series, setSeries] = useState("");
  const [chapterNum, setChapterNum] = useState("1");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit() {
    if (!url.trim()) { setError("Please enter a chapter URL"); return; }
    setLoading(true);
    setError("");
    try {
      await submitChapter({
        source_url: url.trim(),
        series_name: series.trim() || "Unknown Series",
        chapter_number: chapterNum.trim() || "1",
      });
      setUrl(""); setSeries(""); setChapterNum("1");
      onSubmitted();
    } catch (e: any) {
      setError(e.message || "Submission failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="manga-panel bg-white p-6 rounded">
      <h2 className="text-lg font-bold mb-4 flex items-center gap-2">
        <span className="text-red-600">▶</span>
        New Chapter
      </h2>
      <div className="space-y-3">
        <div>
          <label className="block text-xs font-semibold text-ink-500 mb-1 uppercase tracking-wide">
            Chapter URL *
          </label>
          <input
            className="w-full border-2 border-ink-200 rounded px-3 py-2 text-sm focus:border-ink-900 outline-none transition-colors"
            placeholder="https://mangadex.org/chapter/..."
            value={url}
            onChange={e => setUrl(e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-semibold text-ink-500 mb-1 uppercase tracking-wide">
              Series Name
            </label>
            <input
              className="w-full border-2 border-ink-200 rounded px-3 py-2 text-sm focus:border-ink-900 outline-none transition-colors"
              placeholder="My Hero Academia"
              value={series}
              onChange={e => setSeries(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-ink-500 mb-1 uppercase tracking-wide">
              Chapter #
            </label>
            <input
              className="w-full border-2 border-ink-200 rounded px-3 py-2 text-sm focus:border-ink-900 outline-none transition-colors"
              placeholder="42"
              value={chapterNum}
              onChange={e => setChapterNum(e.target.value)}
            />
          </div>
        </div>
        {error && (
          <p className="text-red-600 text-sm bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
        )}
        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full manga-panel-sm bg-ink-900 text-white font-bold py-2.5 rounded hover:bg-ink-700 transition-colors disabled:opacity-50 text-sm tracking-wide"
        >
          {loading ? "Queuing…" : "START TRANSLATION PIPELINE ▶"}
        </button>
      </div>
    </div>
  );
}
