#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

START_URL="${START_URL:-https://mainichigahakken.net/}"
OUTPUT_DIR="${OUTPUT_DIR:-output/mainichigahakken-recursive}"
TITLE="${TITLE:-毎日が発見}"
MAX_PAGES="${MAX_PAGES:-200}"
MIN_DELAY="${MIN_DELAY:-1}"
MAX_DELAY="${MAX_DELAY:-10}"

# Optional switches:
# CLEAN_OUTPUT=1   remove the existing output directory before crawling
# RUN_CRAWL=0      skip crawling and only post-process existing output
# RUN_TRANSLATE=0  skip translation API calls and only run local post-processors
CLEAN_OUTPUT="${CLEAN_OUTPUT:-0}"
RUN_CRAWL="${RUN_CRAWL:-1}"
RUN_TRANSLATE="${RUN_TRANSLATE:-1}"

run_step() {
  echo
  echo "==> $*"
  "$@"
}

check_python_deps() {
  python3 - <<'PY'
import importlib.util
import os
import sys

modules = {
    "requests": "requests",
    "bs4": "beautifulsoup4",
}
if os.environ.get("RUN_TRANSLATE", "1") != "0":
    modules["deep_translator"] = "deep-translator"

missing = [pkg for module, pkg in modules.items() if importlib.util.find_spec(module) is None]
if missing:
    print("Missing Python dependencies: " + ", ".join(missing), file=sys.stderr)
    print("Install them with: python3 -m pip install -r requirements.txt", file=sys.stderr)
    sys.exit(1)
PY
}

check_python_deps

if [[ "$CLEAN_OUTPUT" == "1" ]]; then
  echo "==> Removing existing output directory: $OUTPUT_DIR"
  rm -rf "$OUTPUT_DIR"
fi

if [[ "$RUN_CRAWL" != "0" ]]; then
  run_step python3 scripts/save_translate_page.py \
    --url "$START_URL" \
    --output "$OUTPUT_DIR" \
    --title "$TITLE" \
    --recursive \
    --max-pages "$MAX_PAGES" \
    --min-delay "$MIN_DELAY" \
    --max-delay "$MAX_DELAY"

  run_step python3 scripts/fetch_missing.py
else
  echo "==> Skipping crawl because RUN_CRAWL=0"
fi

if [[ "$RUN_TRANSLATE" != "0" ]]; then
  run_step python3 scripts/batch_translate.py
  run_step python3 scripts/apply_translations.py
  run_step python3 scripts/translate_right_sidebar.py
else
  echo "==> Skipping translation API calls because RUN_TRANSLATE=0"
fi

run_step python3 scripts/download_styles.py
run_step python3 scripts/translate_nav_js.py
run_step python3 scripts/fix_nav_urls.py
run_step python3 scripts/remove_ads.py

echo
echo "Build complete: $OUTPUT_DIR"
