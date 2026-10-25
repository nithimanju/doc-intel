import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import type { IncomingMessage, ServerResponse } from "node:http";
import { fromRepoRoot } from "./paths.ts";

const MANIFEST_PATH = fromRepoRoot("corpus", "manifest.json");

interface ManifestDoc {
  doc_id: string;
  raw_path: string;
}

function loadDocIdToRawPath(): Map<string, string> {
  const map = new Map<string, string>();
  if (!existsSync(MANIFEST_PATH)) return map;
  const raw = readFileSync(MANIFEST_PATH, "utf-8").replace(/^﻿/, "");
  const data = JSON.parse(raw) as { documents: ManifestDoc[] };
  for (const doc of data.documents) map.set(doc.doc_id, doc.raw_path);
  return map;
}

/** GET /pdfs/:docId -> streams the PDF from manifest.json's raw_path.
 * Looking up by doc_id (never a raw path) means no path-traversal surface
 * reaches the URL at all. Mount this at exactly "/pdfs" in the Vite plugin
 * so req.url inside the handler is just "/<docId>". */
export function createPdfHandler() {
  const docIdToRawPath = loadDocIdToRawPath();

  return (req: IncomingMessage, res: ServerResponse) => {
    const docId = decodeURIComponent((req.url ?? "").replace(/^\//, "").split("?")[0]);
    const rawPath = docIdToRawPath.get(docId);
    if (!rawPath) {
      res.statusCode = 404;
      res.end(`Unknown doc_id: ${docId}`);
      return;
    }
    const absPath = fromRepoRoot(rawPath);
    if (!existsSync(absPath)) {
      res.statusCode = 404;
      res.end(`Manifest points at a missing file: ${rawPath}`);
      return;
    }
    res.setHeader("Content-Type", "application/pdf");
    res.setHeader("Content-Length", statSync(absPath).size);
    res.setHeader("Cache-Control", "no-cache");
    createReadStream(absPath).pipe(res);
  };
}
