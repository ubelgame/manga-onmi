"use client";
import { Chapter } from "@/types";
import StatusBadge from "@/components/ui/StatusBadge";
import Link from "next/link";

interface Props {
  chapters: Chapter[];
  loading: boolean;
}

export default function ChapterList({ chapters, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-16 bg-ink-100 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (chapters.length === 0) {
    return (
      <div className="manga-panel bg-white rounded p-8 text-center text-ink-400">
        <div className="text-4xl mb-2">📖</div>
        <p className="text-sm">No chapters yet. Submit a URL above to begin.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {chapters.map(ch => (
        <Link key={ch.id} href={`/chapters/${ch.id}`}>
          <div className="manga-panel-sm bg-white rounded p-4 hover:bg-ink-50 transition-colors cursor-pointer">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="font-bold text-sm truncate">{ch.series_name}</p>
                <p className="text-xs text-ink-400">
                  Ch. {ch.chapter_number} · {ch.page_count} page{ch.page_count !== 1 ? "s" : ""}
                </p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <StatusBadge status={ch.status} />
              </div>
            </div>
            <p className="text-xs text-ink-300 mt-1 truncate">{ch.source_url}</p>
          </div>
        </Link>
      ))}
    </div>
  );
}
