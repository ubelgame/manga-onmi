"use client";
import { useState, useEffect, useRef } from "react";
import { MangaPage, OCRBlock } from "@/types";
import { getImageUrl, overrideTranslation, reprocessPage } from "@/lib/api";
import StatusBadge from "@/components/ui/StatusBadge";

interface Props {
  page: MangaPage;
  onRefresh: () => void;
}

export default function PageViewer({ page, onRefresh }: Props) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [rawUrl, setRawUrl] = useState<string | null>(null);
  const [stage, setStage] = useState<"raw" | "final">("final");
  const [selectedBlock, setSelectedBlock] = useState<OCRBlock | null>(null);
  const [editText, setEditText] = useState("");
  const [saving, setSaving] = useState(false);
  const [imgSize, setImgSize] = useState({ w: 1, h: 1, natural_w: 1, natural_h: 1 });
  const imgRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadUrls();
  }, [page.id, page.status]);

  async function loadUrls() {
    const [fin, raw] = await Promise.all([
      getImageUrl(page.id, "final"),
      getImageUrl(page.id, "raw"),
    ]);
    setImageUrl(fin);
    setRawUrl(raw);
  }

  function onImgLoad() {
    if (!imgRef.current) return;
    setImgSize({
      w: imgRef.current.clientWidth,
      h: imgRef.current.clientHeight,
      natural_w: imgRef.current.naturalWidth,
      natural_h: imgRef.current.naturalHeight,
    });
  }

  // Scale bounding box from natural image coords to display coords
  function scaleBox(bb: { x: number; y: number; w: number; h: number }) {
    const sx = imgSize.w / imgSize.natural_w;
    const sy = imgSize.h / imgSize.natural_h;
    return {
      left: bb.x * sx,
      top: bb.y * sy,
      width: bb.w * sx,
      height: bb.h * sy,
    };
  }

  function selectBlock(block: OCRBlock) {
    setSelectedBlock(block);
    setEditText(block.final_english_text || "");
  }

  async function saveTranslation() {
    if (!selectedBlock) return;
    setSaving(true);
    try {
      await overrideTranslation(selectedBlock.id, editText);
      onRefresh();
    } finally {
      setSaving(false);
    }
  }

  async function handleReprocess() {
    await reprocessPage(page.id);
    onRefresh();
  }

  const displayUrl = stage === "final" ? (imageUrl || rawUrl) : rawUrl;

  return (
    <div className="space-y-4">
      {/* Header bar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-3">
          <span className="font-bold text-sm">Page {page.page_number + 1}</span>
          <StatusBadge status={page.status} size="md" />
        </div>
        <div className="flex items-center gap-2">
          {/* Stage toggle */}
          <div className="flex border-2 border-ink-900 rounded overflow-hidden text-xs font-bold">
            {(["raw", "final"] as const).map(s => (
              <button
                key={s}
                onClick={() => setStage(s)}
                className={`px-3 py-1.5 transition-colors ${stage === s ? "bg-ink-900 text-white" : "bg-white text-ink-900 hover:bg-ink-50"}`}
              >
                {s === "raw" ? "Original" : "Translated"}
              </button>
            ))}
          </div>
          <button
            onClick={handleReprocess}
            className="px-3 py-1.5 text-xs font-bold border-2 border-ink-900 rounded hover:bg-ink-900 hover:text-white transition-colors"
          >
            ↺ Reprocess
          </button>
        </div>
      </div>

      {page.error_message && (
        <div className="bg-red-50 border-2 border-red-300 rounded p-3 text-sm text-red-700">
          <strong>Error:</strong> {page.error_message}
        </div>
      )}

      <div className="flex gap-4 items-start flex-wrap lg:flex-nowrap">
        {/* Image + overlay */}
        <div className="flex-1 min-w-0">
          <div ref={containerRef} className="manga-panel rounded relative bg-ink-900 overflow-hidden">
            {displayUrl ? (
              <>
                <img
                  ref={imgRef}
                  src={displayUrl}
                  alt={`Page ${page.page_number}`}
                  className="w-full h-auto block"
                  onLoad={onImgLoad}
                />
                {/* OCR block overlays (only on raw view so user can see what was detected) */}
                {stage === "raw" && imgSize.natural_w > 1 && page.ocr_blocks.map(block => {
                  const s = scaleBox(block.bounding_box);
                  const isSelected = selectedBlock?.id === block.id;
                  return (
                    <div
                      key={block.id}
                      onClick={() => selectBlock(block)}
                      style={{
                        position: "absolute",
                        left: s.left,
                        top: s.top,
                        width: s.width,
                        height: s.height,
                      }}
                      className={`cursor-pointer border-2 transition-all ${
                        isSelected
                          ? "border-red-500 bg-red-500/20"
                          : "border-blue-400/60 bg-blue-400/10 hover:bg-blue-400/20"
                      }`}
                      title={block.raw_jp_text}
                    />
                  );
                })}
              </>
            ) : (
              <div className="aspect-[3/4] flex items-center justify-center bg-ink-800">
                <div className="text-ink-400 text-center">
                  <div className="text-3xl mb-2 animate-spin-slow">◈</div>
                  <p className="text-xs">{page.status === "done" ? "Loading…" : "Processing…"}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Side panel: block editor */}
        <div className="w-full lg:w-72 shrink-0 space-y-3">
          {selectedBlock ? (
            <div className="manga-panel bg-white rounded p-4 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-sm">Text Block Editor</h3>
                <button
                  onClick={() => setSelectedBlock(null)}
                  className="text-ink-400 hover:text-ink-900 text-lg leading-none"
                >×</button>
              </div>
              <div>
                <label className="block text-xs text-ink-400 mb-1 uppercase tracking-wide">Japanese (OCR)</label>
                <p className="text-sm bg-ink-50 rounded p-2 font-mono border border-ink-200">
                  {selectedBlock.raw_jp_text}
                </p>
              </div>
              <div>
                <label className="block text-xs text-ink-400 mb-1 uppercase tracking-wide">English Translation</label>
                <textarea
                  value={editText}
                  onChange={e => setEditText(e.target.value)}
                  rows={4}
                  className="w-full border-2 border-ink-200 rounded px-3 py-2 text-sm focus:border-ink-900 outline-none resize-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-ink-500">
                <div><span className="font-semibold">Shape:</span> {selectedBlock.bubble_shape || "—"}</div>
                <div><span className="font-semibold">Tone:</span> {selectedBlock.tone_label || "—"}</div>
                <div><span className="font-semibold">Font:</span> {selectedBlock.font_family || "—"}</div>
                <div><span className="font-semibold">SFX:</span> {selectedBlock.is_sfx ? "Yes" : "No"}</div>
              </div>
              {selectedBlock.tl_note && (
                <div className="bg-yellow-50 border border-yellow-200 rounded p-2 text-xs text-yellow-800">
                  <span className="font-bold">TL Note:</span> {selectedBlock.tl_note}
                </div>
              )}
              <button
                onClick={saveTranslation}
                disabled={saving}
                className="w-full manga-panel-sm bg-ink-900 text-white text-xs font-bold py-2 rounded hover:bg-ink-700 transition-colors disabled:opacity-50"
              >
                {saving ? "Saving…" : "SAVE OVERRIDE ▶"}
              </button>
            </div>
          ) : (
            <div className="manga-panel bg-white rounded p-4">
              <h3 className="font-bold text-sm mb-3">
                Detected Blocks ({page.ocr_blocks.length})
              </h3>
              {page.ocr_blocks.length === 0 ? (
                <p className="text-xs text-ink-400">No text blocks detected yet.</p>
              ) : (
                <div className="space-y-1.5 max-h-96 overflow-y-auto">
                  {page.ocr_blocks.map((block, i) => (
                    <button
                      key={block.id}
                      onClick={() => selectBlock(block)}
                      className="w-full text-left manga-panel-sm rounded p-2 hover:bg-ink-50 transition-colors"
                    >
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-xs font-bold text-ink-400">#{i + 1}</span>
                        {block.is_sfx && (
                          <span className="text-xs bg-orange-100 text-orange-700 px-1 rounded">SFX</span>
                        )}
                        {block.bubble_shape && (
                          <span className="text-xs bg-blue-50 text-blue-600 px-1 rounded">{block.bubble_shape}</span>
                        )}
                      </div>
                      <p className="text-xs text-ink-600 truncate">{block.raw_jp_text}</p>
                      {block.final_english_text && (
                        <p className="text-xs text-ink-400 truncate mt-0.5">→ {block.final_english_text}</p>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Pipeline progress */}
          <div className="manga-panel bg-white rounded p-4">
            <h3 className="font-bold text-sm mb-3">Pipeline Progress</h3>
            <div className="space-y-2">
              {(["scraping","ocr","translating","inpainting","typesetting","done"] as const).map(s => {
                const statuses = ["queued","scraping","ocr","translating","inpainting","typesetting","done","failed"];
                const currentIdx = statuses.indexOf(page.status);
                const stepIdx = statuses.indexOf(s);
                const done = currentIdx > stepIdx || page.status === "done";
                const active = page.status === s;
                const failed = page.status === "failed" && currentIdx <= stepIdx;
                return (
                  <div key={s} className="flex items-center gap-2 text-xs">
                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-xs font-bold border ${
                      done ? "bg-green-500 border-green-500 text-white" :
                      active ? "bg-blue-500 border-blue-500 text-white animate-pulse" :
                      failed ? "bg-red-100 border-red-300 text-red-400" :
                      "bg-ink-100 border-ink-200 text-ink-300"
                    }`}>
                      {done ? "✓" : active ? "…" : "○"}
                    </span>
                    <span className={done ? "text-ink-700 font-medium" : active ? "text-blue-600 font-medium" : "text-ink-300"}>
                      {s.charAt(0).toUpperCase() + s.slice(1)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
