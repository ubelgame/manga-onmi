"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { Chapter, MangaPage } from "@/types";
import { fetchChapters, fetchPages } from "@/lib/api";
import PageViewer from "@/components/pipeline/PageViewer";
import GlossaryManager from "@/components/pipeline/GlossaryManager";
import StatusBadge from "@/components/ui/StatusBadge";

export default function ChapterPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [chapter, setChapter] = useState<Chapter | null>(null);
  const [pages, setPages] = useState<MangaPage[]>([]);
  const [selectedPage, setSelectedPage] = useState<MangaPage | null>(null);
  const [loading, setLoading] = useState(true);
  const wsRefs = useRef<Map<string, WebSocket>>(new Map());

  const loadData = useCallback(async () => {
    try {
      const [allChapters, pageData] = await Promise.all([
        fetchChapters(),
        fetchPages(id),
      ]);
      const ch = allChapters.find((c: Chapter) => c.id === id);
      setChapter(ch || null);
      setPages(pageData);
      // Select first page by default
      if (pageData.length > 0 && !selectedPage) {
        setSelectedPage(pageData[0]);
      } else if (selectedPage) {
        // Refresh selected page data
        const refreshed = pageData.find((p: MangaPage) => p.id === selectedPage.id);
        if (refreshed) setSelectedPage(refreshed);
      }
    } finally {
      setLoading(false);
    }
  }, [id, selectedPage?.id]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [id]);

  const doneCount = pages.filter(p => p.status === "done").length;
  const failedCount = pages.filter(p => p.status === "failed").length;
  const processingCount = pages.filter(p =>
    !["done", "failed", "queued"].includes(p.status)
  ).length;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-ink-400 text-center">
          <div className="text-4xl animate-spin-slow mb-2">◈</div>
          <p className="text-sm">Loading chapter…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-ink-900 text-white sticky top-0 z-40 border-b-2 border-ink-700">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4">
          <Link href="/" className="text-ink-400 hover:text-white transition-colors text-sm">
            ← Back
          </Link>
          <div className="flex-1 min-w-0">
            <h1 className="font-black text-sm truncate" style={{ fontFamily: "'Bebas Neue', sans-serif", letterSpacing: "0.05em" }}>
              {chapter?.series_name || "Chapter"} — Ch. {chapter?.chapter_number}
            </h1>
          </div>
          <div className="flex items-center gap-3 text-xs text-ink-300 shrink-0">
            <span className="text-green-400 font-bold">{doneCount} done</span>
            {processingCount > 0 && <span className="text-blue-400 animate-pulse">{processingCount} processing</span>}
            {failedCount > 0 && <span className="text-red-400">{failedCount} failed</span>}
            <span>/ {pages.length} total</span>
          </div>
        </div>

        {/* Progress bar */}
        {pages.length > 0 && (
          <div className="h-1 bg-ink-700">
            <div
              className="h-full bg-green-500 transition-all duration-500"
              style={{ width: `${(doneCount / pages.length) * 100}%` }}
            />
          </div>
        )}
      </header>

      <div className="max-w-7xl mx-auto px-4 py-6 flex gap-6">
        {/* Page thumbnail strip */}
        <aside className="w-28 shrink-0">
          <div className="sticky top-20 space-y-2 max-h-[calc(100vh-6rem)] overflow-y-auto">
            <p className="text-xs font-bold uppercase tracking-wide text-ink-400 mb-2">Pages</p>
            {pages.length === 0 ? (
              <p className="text-xs text-ink-300">Scraping…</p>
            ) : pages.map(page => (
              <button
                key={page.id}
                onClick={() => setSelectedPage(page)}
                className={`w-full manga-panel-sm rounded p-2 text-left transition-all ${
                  selectedPage?.id === page.id
                    ? "bg-ink-900 text-white border-ink-900"
                    : "bg-white hover:bg-ink-50"
                }`}
              >
                <p className="text-xs font-bold">Pg {page.page_number + 1}</p>
                <StatusBadge status={page.status} />
              </button>
            ))}
          </div>
        </aside>

        {/* Main content */}
        <main className="flex-1 min-w-0 space-y-6">
          {selectedPage ? (
            <PageViewer
              page={selectedPage}
              onRefresh={loadData}
            />
          ) : (
            <div className="manga-panel bg-white rounded p-12 text-center text-ink-400">
              <p className="text-4xl mb-2">📄</p>
              <p className="text-sm">Select a page from the left panel</p>
            </div>
          )}
        </main>

        {/* Right sidebar: glossary */}
        <aside className="w-64 shrink-0 hidden xl:block">
          <div className="sticky top-20">
            <GlossaryManager chapterId={id} />
          </div>
        </aside>
      </div>
    </div>
  );
}
