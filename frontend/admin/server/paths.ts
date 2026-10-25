import { fileURLToPath } from "node:url";
import path from "node:path";

// This file lives at <repo>/frontend/admin/server/paths.ts, so the repo
// root is three levels up. Resolved from import.meta.url rather than
// process.cwd() so `npm run dev` works the same regardless of which
// directory it's invoked from.
const thisDir = path.dirname(fileURLToPath(import.meta.url));
export const repoRoot = path.resolve(thisDir, "../../..");

export function fromRepoRoot(...segments: string[]): string {
  return path.resolve(repoRoot, ...segments);
}
