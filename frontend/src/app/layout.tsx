import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Manga Omni-Translator",
  description: "Professional-grade manga OCR, translation, and typesetting pipeline",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-ink-50">
        {children}
      </body>
    </html>
  );
}
