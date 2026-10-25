import { createReadStream, existsSync, statSync } from "node:fs";
import readline from "node:readline";
import { fromRepoRoot } from "./paths.ts";

const CATALOG_PATH = fromRepoRoot("corpus", ".cache", "page_catalog.jsonl");

interface PageRow {
  doc_id: string;
  page_num: number;
  text: string;
}

function key(docId: string, page: number): string {
  return `${docId}:${page}`;
}

export class ContextCache {
  private pageText = new Map<string, string>();
  private loaded = false;
  private loadError: string | null = null;

  async load(): Promise<void> {
    if (!existsSync(CATALOG_PATH)) {
      this.loadError =
        `corpus/.cache/page_catalog.jsonl not found. Run ` +
        `"python src/eval/golden_pages.py" from the repo root first.`;
      return;
    }
    const rl = readline.createInterface({
      input: createReadStream(CATALOG_PATH, { encoding: "utf-8" }),
      crlfDelay: Infinity,
    });
    for await (const line of rl) {
      if (!line.trim()) continue;
      const row = JSON.parse(line) as PageRow;
      this.pageText.set(key(row.doc_id, row.page_num), row.text);
    }
    this.loaded = true;
  }

  status(): { loaded: boolean; error: string | null; pages: number } {
    return { loaded: this.loaded, error: this.loadError, pages: this.pageText.size };
  }

  /** Mirrors src/eval/golden_export_review.py's page_excerpt(): ±300 chars
   * around the evidence quote if found, else a leading 800-char slice. */
  excerpt(docId: string, page: number, around: string): string {
    const text = this.pageText.get(key(docId, page));
    if (!text) return "";
    if (!around || !text.includes(around)) return text.slice(0, 800);
    const idx = text.indexOf(around);
    const start = Math.max(0, idx - 300);
    const end = Math.min(text.length, idx + around.length + 300);
    return text.slice(start, end);
  }
}

export function catalogSizeBytes(): number {
  return existsSync(CATALOG_PATH) ? statSync(CATALOG_PATH).size : 0;
}
