import type { Plugin, ViteDevServer } from "vite";
import type { IncomingMessage, ServerResponse } from "node:http";
import { ContextCache } from "./contextCache.ts";
import { GoldenStore } from "./goldenStore.ts";
import { createPdfHandler } from "./pdfRoute.ts";
import type { DecisionRequest } from "../shared/types.ts";

function readJsonBody(req: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      try {
        resolve(body ? JSON.parse(body) : {});
      } catch (err) {
        reject(err);
      }
    });
    req.on("error", reject);
  });
}

function sendJson(res: ServerResponse, status: number, data: unknown): void {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(JSON.stringify(data));
}

/** Vite dev-server plugin: serves the golden-set review API and PDFs on the
 * same port as the React app, so `npm run dev` is the only command needed.
 * See decisions.md's entry on this tool for why (no second process to
 * remember to start). */
export function goldenReviewServer(): Plugin {
  const cache = new ContextCache();
  const store = new GoldenStore();

  return {
    name: "golden-review-server",
    configureServer(server: ViteDevServer) {
      // Loaded once at startup; corpus/.cache/page_catalog.jsonl is ~7.8MB
      // and must not be reloaded per-request.
      const ready = cache.load().then(() => store.load());

      server.middlewares.use("/pdfs", createPdfHandler());

      server.middlewares.use("/api/status", async (_req, res) => {
        await ready;
        sendJson(res, 200, { ...cache.status(), candidates: store.count() });
      });

      server.middlewares.use("/api/candidates", async (req, res) => {
        if (req.method !== "GET") {
          sendJson(res, 405, { error: "GET only" });
          return;
        }
        await ready;
        const status = cache.status();
        if (!status.loaded) {
          sendJson(res, 503, { error: status.error ?? "context cache not ready yet" });
          return;
        }
        const all = store.listCandidates().map((_, idx) => store.withContext(idx, cache));
        sendJson(res, 200, all);
      });

      server.middlewares.use("/api/decision", async (req, res) => {
        if (req.method !== "POST") {
          sendJson(res, 405, { error: "POST only" });
          return;
        }
        await ready;
        try {
          const body = (await readJsonBody(req)) as DecisionRequest;
          if (typeof body.idx !== "number" || !body.action) {
            sendJson(res, 400, { error: "expected { idx: number, action: string, ... }" });
            return;
          }
          store.applyDecision(body);
          const withContext = store.withContext(body.idx, cache);
          sendJson(res, 200, { ok: true, candidate: withContext });
        } catch (err) {
          sendJson(res, 400, { error: err instanceof Error ? err.message : String(err) });
        }
      });
    },
  };
}
