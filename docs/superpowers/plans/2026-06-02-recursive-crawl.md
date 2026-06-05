# Recursive Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add controlled same-domain recursive crawling to the existing single-page offline translation script.

**Architecture:** Extend `scripts/save_translate_page.py` with a BFS crawl coordinator that reuses the existing per-page HTML processing, translation extraction, image localization, and report generation logic. Recursive mode is opt-in via `--recursive`, limited by `--max-pages` defaulting to `200`, constrained to the start URL domain, and waits a random `1-10` seconds between page requests.

**Tech Stack:** Python 3 standard library, `requests`, `beautifulsoup4`, existing `unittest` tests.

---

### File Structure

- Modify: `scripts/save_translate_page.py`
  - Add URL normalization, same-domain filtering, local HTML path mapping, anchor extraction, link rewriting, recursive crawl coordinator, and CLI flags.
- Modify: `tests/test_save_translate_page.py`
  - Add tests for URL filtering, local path mapping, anchor extraction, random delay bounds, and local link rewriting.

### Task 1: URL Helpers

**Files:**
- Modify: `tests/test_save_translate_page.py`
- Modify: `scripts/save_translate_page.py`

- [ ] **Step 1: Write failing tests**

Add tests for:
- `normalize_page_url("https://mainichigahakken.net/a/?utm_source=x#top")` returns `https://mainichigahakken.net/a/`.
- `is_crawlable_page_url()` allows same-domain HTTP(S) pages and rejects external, `mailto:`, `tel:`, `javascript:`, and static asset extensions.
- `local_html_path_for_url()` maps the start URL to `index.html` and article URLs to deterministic paths below `pages/`.

- [ ] **Step 2: Run tests and confirm failure**

Run: `.venv/bin/python -m unittest tests.test_save_translate_page -v`
Expected: import errors or failing assertions because helpers do not exist.

- [ ] **Step 3: Implement helpers**

Implement:
- `normalize_page_url(url: str) -> str`
- `is_crawlable_page_url(url: str, start_netloc: str) -> bool`
- `local_html_path_for_url(url: str, start_url: str) -> Path`

- [ ] **Step 4: Run tests and confirm pass**

Run: `.venv/bin/python -m unittest tests.test_save_translate_page -v`
Expected: all tests pass.

### Task 2: Link Extraction and Rewriting

**Files:**
- Modify: `tests/test_save_translate_page.py`
- Modify: `scripts/save_translate_page.py`

- [ ] **Step 1: Write failing tests**

Add tests for:
- `extract_crawl_links()` reads same-domain `<a href>` links, resolves relative URLs, normalizes them, and excludes non-crawlable links.
- `rewrite_page_links()` rewrites same-domain crawled links to relative local HTML paths and leaves external links unchanged.

- [ ] **Step 2: Run tests and confirm failure**

Run: `.venv/bin/python -m unittest tests.test_save_translate_page -v`
Expected: import errors or failing assertions.

- [ ] **Step 3: Implement extraction and rewriting**

Implement:
- `extract_crawl_links(soup, page_url, start_netloc) -> list[str]`
- `rewrite_page_links(soup, page_url, url_to_output_path, page_output_path) -> None`

- [ ] **Step 4: Run tests and confirm pass**

Run: `.venv/bin/python -m unittest tests.test_save_translate_page -v`
Expected: all tests pass.

### Task 3: Recursive Crawl Coordinator

**Files:**
- Modify: `scripts/save_translate_page.py`

- [ ] **Step 1: Add CLI flags**

Add:
- `--recursive`
- `--max-pages`, default `200`
- `--min-delay`, default `1.0`
- `--max-delay`, default `10.0`

- [ ] **Step 2: Refactor per-page processing**

Split existing `save_translated_page()` internals into a reusable `process_page_html()` that accepts a response HTML string, URL, output path, shared assets directory, shared translation path, shared asset cache, and report.

- [ ] **Step 3: Implement crawl loop**

Use BFS:
- Queue starts with normalized start URL.
- Skip visited URLs.
- Stop when `len(visited) == max_pages` or queue is empty.
- Fetch each page with `requests.Session`.
- Process only HTML responses.
- Extract new links from processed soup.
- Randomly sleep between `min_delay` and `max_delay` before next request.
- Write `sitemap.json` and `crawl_report.json`.

- [ ] **Step 4: Preserve single-page mode**

If `--recursive` is false, keep the current output files and behavior.

### Task 4: Verification

**Files:**
- Inspect: `scripts/save_translate_page.py`
- Inspect: `tests/test_save_translate_page.py`
- Inspect generated test output.

- [ ] **Step 1: Run unit tests**

Run: `.venv/bin/python -m unittest tests.test_save_translate_page -v`
Expected: all tests pass.

- [ ] **Step 2: Run syntax check**

Run: `.venv/bin/python -m py_compile scripts/save_translate_page.py`
Expected: no syntax errors.

- [ ] **Step 3: Run small recursive smoke test**

Run:

```bash
.venv/bin/python scripts/save_translate_page.py \
  --url https://mainichigahakken.net/ \
  --output output/mainichigahakken-recursive-smoke \
  --title '毎日が発見' \
  --recursive \
  --max-pages 2 \
  --min-delay 1 \
  --max-delay 1
```

Expected: `crawl_report.json`, `sitemap.json`, and at least one HTML file are generated. This verifies capability without running a full 200-page crawl.

- [ ] **Step 4: Inspect smoke report**

Run a Python snippet to confirm:
- `visited_pages <= 2`
- failed pages are recorded, not fatal
- generated HTML files exist for successful pages.
