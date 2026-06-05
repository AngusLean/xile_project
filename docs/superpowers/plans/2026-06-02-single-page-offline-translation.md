# Single Page Offline Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable script that saves one specified webpage as an offline Chinese HTML page with local image assets.

**Architecture:** A Python command-line script downloads one URL, parses the HTML, saves the original HTML, localizes image references, extracts visible text and user-facing attributes, applies a translation map while preserving surrounding whitespace, and writes the final offline HTML. The first version guarantees local image assets and reports any remaining remote resources; it does not recursively crawl the website. Because no external translation API key is available, the script exports `translations.json` and accepts a filled translation map; the assistant can generate that map for the first homepage run in this session.

**Tech Stack:** Python 3, `requests`, `beautifulsoup4`, standard library `argparse`, `json`, `pathlib`, `urllib.parse`, `hashlib`.

---

### File Structure

- Create: `requirements.txt`
  - Lists runtime dependencies.
- Create: `scripts/save_translate_page.py`
  - Implements one-page download, image localization, text extraction, translation-map loading, and HTML writing.
- Create during execution: `output/mainichigahakken/original.html`
  - Raw downloaded HTML backup.
- Create during execution: `output/mainichigahakken/translations.json`
  - Extracted Japanese text keys and Chinese values.
- Create during execution: `output/mainichigahakken/index.html`
  - Offline Chinese HTML result.
- Create during execution: `output/mainichigahakken/assets/`
  - Downloaded local image files.
- Create during execution: `output/mainichigahakken/report.json`
  - Asset download failures and remaining remote resource references.

### Task 1: Project Dependencies

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Add dependencies**

```text
requests>=2.31.0
beautifulsoup4>=4.12.0
```

- [ ] **Step 2: Install dependencies**

Run: `python3 -m pip install -r requirements.txt`
Expected: dependencies install successfully or are already satisfied.

### Task 2: Reusable Single-Page Script

**Files:**
- Create: `scripts/save_translate_page.py`

- [ ] **Step 1: Implement CLI arguments**

Support:

```bash
python3 scripts/save_translate_page.py \
  --url https://mainichigahakken.net/ \
  --output output/mainichigahakken \
  --title "毎日が発見"
```

- [ ] **Step 2: Implement HTML download**

Use `requests.Session` with a browser-like `User-Agent`. Save the original response body to `original.html`.

- [ ] **Step 3: Implement image localization**

Find image URLs in `img[src]`, `img[srcset]`, `source[srcset]`, and common lazy-load attributes such as `data-src`, `data-original`, `data-lazy-src`, and `data-srcset`. Resolve absolute, relative, and protocol-relative URLs with `urljoin`. Download each asset once, choose a stable hashed filename, infer the extension from URL path or `Content-Type`, and replace remote URLs with `assets/<filename>`. Preserve `srcset` descriptors such as `1x`, `2x`, and `640w`. Record failed downloads in `report.json` and continue.

- [ ] **Step 4: Implement visible text extraction**

Extract non-empty text nodes outside `script`, `style`, `noscript`, `svg`, `canvas`, and `template`. Use the stripped text as the translation key, but replace only the non-space middle part of the original text node so leading and trailing whitespace remain unchanged. Deduplicate text while preserving order.

- [ ] **Step 5: Implement user-facing attribute translation**

Extract and translate user-facing attributes: `alt`, `title`, `aria-label`, `placeholder`, `value`, and `content` on common meta tags such as `meta[name=description]`, `meta[property=og:title]`, and `meta[property=og:description]`. Skip empty values, URLs, numeric-only values, and machine-like tokens.

- [ ] **Step 6: Implement translation map support**

If `translations.json` does not exist, create it as:

```json
{
  "元の日本語": ""
}
```

If it exists, replace each exact text node with the non-empty Chinese value.

- [ ] **Step 7: Add offline study notice**

Insert a small top banner explaining that the file is an offline Chinese study version generated for personal Japanese learning.

- [ ] **Step 8: Write final HTML and report**

Write `index.html` using UTF-8. Write `report.json` with `downloaded_assets`, `failed_assets`, and `remaining_remote_references` discovered from `src`, `srcset`, `href`, inline `style`, and `content` attributes.

### Task 3: First Homepage Run

**Files:**
- Create/Modify: `output/mainichigahakken/*`

- [ ] **Step 1: Run extraction**

Run:

```bash
python3 scripts/save_translate_page.py \
  --url https://mainichigahakken.net/ \
  --output output/mainichigahakken \
  --title "毎日が発見"
```

Expected: `original.html`, `translations.json`, `index.html`, `report.json`, and `assets/` are generated.

- [ ] **Step 2: Translate visible homepage text**

Use the extracted `translations.json` keys and fill Chinese translations for visible homepage text only. Keep brand names and ambiguous UI labels readable rather than over-translating.

- [ ] **Step 3: Re-run HTML generation**

Run the same command again.
Expected: `index.html` uses Chinese translations where values exist.

### Task 4: Verification

**Files:**
- Inspect: `output/mainichigahakken/index.html`
- Inspect: `output/mainichigahakken/assets/`

- [ ] **Step 1: Check generated files**

Run:

```bash
test -f output/mainichigahakken/index.html
test -f output/mainichigahakken/original.html
test -f output/mainichigahakken/translations.json
test -f output/mainichigahakken/report.json
test -d output/mainichigahakken/assets
```

Expected: all commands exit successfully.

- [ ] **Step 2: Check local image references**

Run:

```bash
grep -E 'src="https?://|srcset="https?://' output/mainichigahakken/index.html || true
```

Expected: no remaining direct remote image references in image `src` or `srcset` where assets were downloadable; remaining stylesheet, script, tracking, or canonical links may be reported in `report.json` for transparency.

- [ ] **Step 3: Check translation coverage**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
data = json.loads(Path("output/mainichigahakken/translations.json").read_text(encoding="utf-8"))
filled = sum(1 for value in data.values() if value.strip())
print(f"filled_translations={filled}, total={len(data)}")
assert data
PY
```

Expected: translations file is non-empty; after assistant translation, `filled_translations` is greater than zero.

- [ ] **Step 4: Check remaining remote resource report**

Run:

```bash
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path("output/mainichigahakken/report.json").read_text(encoding="utf-8"))
print(json.dumps({
    "downloaded_assets": len(report.get("downloaded_assets", [])),
    "failed_assets": len(report.get("failed_assets", [])),
    "remaining_remote_references": len(report.get("remaining_remote_references", [])),
}, ensure_ascii=False, indent=2))
PY
```

Expected: counts print successfully; any remaining remote references are known and recorded.

- [ ] **Step 5: Check script syntax**

Run:

```bash
python3 -m py_compile scripts/save_translate_page.py
```

Expected: no syntax errors.

- [ ] **Step 6: Optional local preview**

Run:

```bash
python3 -m http.server 8000 -d output/mainichigahakken
```

Expected: open `http://localhost:8000/` to view the offline Chinese page.
