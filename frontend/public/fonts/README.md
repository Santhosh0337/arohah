# Fonts

`fonts.css` declares Noto Sans for Latin, Tamil and Devanagari. The binaries are
**not committed yet**. These six files must exist in this folder:

| File | Family | Weight |
|---|---|---|
| `NotoSans-Latin-400.woff2` | Noto Sans | 400 |
| `NotoSans-Latin-600.woff2` | Noto Sans | 600 |
| `NotoSansTamil-400.woff2` | Noto Sans Tamil | 400 |
| `NotoSansTamil-600.woff2` | Noto Sans Tamil | 600 |
| `NotoSansDevanagari-400.woff2` | Noto Sans Devanagari | 400 |
| `NotoSansDevanagari-600.woff2` | Noto Sans Devanagari | 600 |

## Get them

From `frontend/`, with internet access:

```bash
npm run fonts
```

The script downloads the Fontsource builds of Noto Sans (SIL Open Font License)
through the jsDelivr CDN and checks that every response is a real WOFF2 file.
It stops with a clear message if a download fails. Commit the six files
afterwards; once they are committed the app needs no network for fonts.

If the script cannot reach the CDN, download the same families from
https://fonts.google.com/noto (Noto Sans, Noto Sans Tamil, Noto Sans
Devanagari), convert the Regular (400) and SemiBold (600) weights to WOFF2, and
save them under the names above.

Add Telugu or Malayalam later by adding a row to `scripts/fetch-fonts.mjs` and a
matching `@font-face` block in `fonts.css`.
