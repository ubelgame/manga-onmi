export type ProcessingStatus =
  | "queued"
  | "scraping"
  | "ocr"
  | "translating"
  | "inpainting"
  | "typesetting"
  | "done"
  | "failed";

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface OCRBlock {
  id: string;
  raw_jp_text: string;
  bounding_box: BoundingBox;
  confidence: number;
  reading_order_index: number;
  is_sfx: boolean;
  bubble_shape: string | null;
  final_english_text: string | null;
  tone_label: string | null;
  tl_note: string | null;
  font_family: string | null;
  font_size_pt: number | null;
}

export interface MangaPage {
  id: string;
  chapter_id: string;
  page_number: number;
  status: ProcessingStatus;
  raw_image_s3_key: string | null;
  inpainted_s3_key: string | null;
  final_s3_key: string | null;
  error_message: string | null;
  ocr_blocks: OCRBlock[];
  created_at: string;
  updated_at: string;
}

export interface Chapter {
  id: string;
  series_name: string;
  chapter_number: string;
  source_url: string;
  status: ProcessingStatus;
  created_at: string;
  page_count: number;
}

export interface GlossaryTerm {
  id: string;
  japanese_term: string;
  english_term: string;
  term_type: string;
}
