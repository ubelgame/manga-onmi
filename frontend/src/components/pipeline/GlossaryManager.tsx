"use client";
import { useState, useEffect } from "react";
import { GlossaryTerm } from "@/types";
import { fetchGlossary, addGlossaryTerm } from "@/lib/api";

interface Props { chapterId: string; }

export default function GlossaryManager({ chapterId }: Props) {
  const [terms, setTerms] = useState<GlossaryTerm[]>([]);
  const [jp, setJp] = useState("");
  const [en, setEn] = useState("");
  const [type, setType] = useState("character");
  const [saving, setSaving] = useState(false);

  useEffect(() => { load(); }, [chapterId]);

  async function load() {
    try {
      const data = await fetchGlossary(chapterId);
      setTerms(data);
    } catch {}
  }

  async function handleAdd() {
    if (!jp.trim() || !en.trim()) return;
    setSaving(true);
    try {
      await addGlossaryTerm(chapterId, { japanese_term: jp, english_term: en, term_type: type });
      setJp(""); setEn("");
      await load();
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="manga-panel bg-white rounded p-4 space-y-4">
      <h3 className="font-bold text-sm flex items-center gap-2">
        <span className="text-red-600">言</span> Glossary
      </h3>

      {/* Add term */}
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <input
            className="border-2 border-ink-200 rounded px-2 py-1.5 text-sm focus:border-ink-900 outline-none"
            placeholder="Japanese (e.g. ルフィ)"
            value={jp}
            onChange={e => setJp(e.target.value)}
          />
          <input
            className="border-2 border-ink-200 rounded px-2 py-1.5 text-sm focus:border-ink-900 outline-none"
            placeholder="English (e.g. Luffy)"
            value={en}
            onChange={e => setEn(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <select
            className="flex-1 border-2 border-ink-200 rounded px-2 py-1.5 text-sm focus:border-ink-900 outline-none"
            value={type}
            onChange={e => setType(e.target.value)}
          >
            <option value="character">Character</option>
            <option value="location">Location</option>
            <option value="technique">Technique</option>
            <option value="general">General</option>
          </select>
          <button
            onClick={handleAdd}
            disabled={saving}
            className="manga-panel-sm px-3 py-1.5 bg-ink-900 text-white text-xs font-bold rounded hover:bg-ink-700 transition-colors disabled:opacity-50"
          >
            + Add
          </button>
        </div>
      </div>

      {/* Term list */}
      <div className="space-y-1.5 max-h-48 overflow-y-auto">
        {terms.length === 0 ? (
          <p className="text-xs text-ink-400">No glossary terms yet.</p>
        ) : terms.map(t => (
          <div key={t.id} className="flex items-center justify-between bg-ink-50 rounded px-2 py-1.5 text-xs">
            <span className="font-mono">{t.japanese_term}</span>
            <span className="text-ink-400 mx-1">→</span>
            <span className="font-semibold flex-1">{t.english_term}</span>
            <span className="ml-2 bg-ink-200 rounded px-1 text-ink-500">{t.term_type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
