// Downloads the self-hosted font files listed in public/fonts/README.md.
// Usage (from frontend/): npm run fonts
//
// Source: Fontsource builds of Noto Sans via the jsDelivr CDN. The URL pattern
//   https://cdn.jsdelivr.net/fontsource/fonts/<font-id>@latest/<subset>-<weight>-normal.woff2
// follows Fontsource's documented layout but was NOT reachable from the
// sandbox this script was written in, so run it once and check the output.
// Every download is verified to start with the WOFF2 signature ("wOF2");
// anything else is rejected and nothing is written for that file.

import { mkdir, writeFile, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "public", "fonts");

const FONTS = [
  { id: "noto-sans", subset: "latin", file: "NotoSans-Latin" },
  { id: "noto-sans-tamil", subset: "tamil", file: "NotoSansTamil" },
  { id: "noto-sans-devanagari", subset: "devanagari", file: "NotoSansDevanagari" },
];
const WEIGHTS = [400, 600];

const force = process.argv.includes("--force");
const exists = (p) => access(p).then(() => true, () => false);
let failed = 0;

await mkdir(OUT, { recursive: true });

for (const f of FONTS) {
  for (const w of WEIGHTS) {
    const target = path.join(OUT, `${f.file}-${w}.woff2`);
    const name = path.basename(target);
    if (!force && (await exists(target))) {
      console.log(`skip   ${name} (already there; use --force to replace)`);
      continue;
    }
    const url = `https://cdn.jsdelivr.net/fontsource/fonts/${f.id}@latest/${f.subset}-${w}-normal.woff2`;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const bytes = new Uint8Array(await res.arrayBuffer());
      const sig = String.fromCharCode(...bytes.slice(0, 4));
      if (sig !== "wOF2") throw new Error("response is not a WOFF2 file");
      await writeFile(target, bytes);
      console.log(`ok     ${name} (${(bytes.length / 1024).toFixed(1)} KB)`);
    } catch (e) {
      failed++;
      console.error(`FAILED ${name}: ${e.message}\n       ${url}`);
    }
  }
}

if (failed) {
  console.error(`\n${failed} file(s) failed. See public/fonts/README.md for the manual route.`);
  process.exit(1);
}
console.log("\nAll fonts are in public/fonts/. Commit them.");
