# Xile Project

This repository contains a local mirrored and Chinese-translated study copy of
`https://mainichigahakken.net/`.

## One-Command Rebuild

Install dependencies first:

```bash
python3 -m pip install -r requirements.txt
```

Run the complete pipeline:

```bash
./scripts/build_all.sh
```

The pipeline performs these steps:

- Crawl same-domain pages with a 200-page default limit.
- Download images and page assets to local paths.
- Fetch known navigation pages that may be missed by the page limit.
- Translate extracted Japanese text into Chinese.
- Apply translations back into HTML files.
- Download and rewrite CSS, fonts, and nested CSS assets.
- Translate and repair JavaScript-generated navigation.
- Translate the right sidebar recommendation widget.
- Remove ad scripts, popups, and ad placeholder blocks.

## Useful Rebuild Options

Run a clean rebuild:

```bash
CLEAN_OUTPUT=1 ./scripts/build_all.sh
```

Only post-process existing downloaded pages:

```bash
RUN_CRAWL=0 ./scripts/build_all.sh
```

Skip translation API calls and only run local processors:

```bash
RUN_CRAWL=0 RUN_TRANSLATE=0 ./scripts/build_all.sh
```

Customize crawl limits:

```bash
MAX_PAGES=200 MIN_DELAY=1 MAX_DELAY=10 ./scripts/build_all.sh
```

## Deployment Directory

The generated static site is written to:

```text
output/mainichigahakken-recursive
```

For Nginx or NAS deployment, point the web root directly at this directory or
copy this directory's contents into the Nginx web root.
