#!/usr/bin/env python3
"""Save one webpage as an offline Chinese study HTML page."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import random
import re
import shutil
import time
from collections import OrderedDict
from collections import deque
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup, NavigableString


SKIP_TEXT_TAGS = {"script", "style", "noscript", "svg", "canvas", "template"}
IMAGE_URL_ATTRS = ("src", "data-src", "data-original", "data-lazy-src")
SRCSET_ATTRS = ("srcset", "data-srcset")
TRANSLATABLE_ATTRS = ("alt", "title", "aria-label", "placeholder", "value")
IMAGE_META_KEYS = {"og:image", "twitter:image", "twitter:image:src"}
META_TRANSLATABLE_KEYS = {
    "description",
    "og:title",
    "og:description",
    "twitter:title",
    "twitter:description",
}
REMOTE_RE = re.compile(r"https?://", re.IGNORECASE)
JAPANESE_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
TRACKING_QUERY_PREFIXES = ("utm_",)
TRACKING_QUERY_KEYS = {"fbclid", "gclid", "yclid"}
STATIC_EXTENSIONS = {
    ".css",
    ".js",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".zip",
    ".mp4",
    ".mp3",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


def replace_text_preserving_space(original: str, replacement: str) -> str:
    """Replace the non-space middle of a text node and keep outer whitespace."""
    match = re.match(r"^(\s*)(.*?)(\s*)$", original, flags=re.DOTALL)
    if not match:
        return replacement
    return f"{match.group(1)}{replacement}{match.group(3)}"


def should_translate_value(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if re.match(r"^[a-z][a-z0-9+.-]*://", text, flags=re.IGNORECASE):
        return False
    if re.fullmatch(r"[\d\s,./:：+-]+", text):
        return False
    if re.fullmatch(r"[A-Za-z0-9_.:/#?&=%+-]+", text):
        return False
    return bool(JAPANESE_RE.search(text))


def parse_srcset(srcset: str, base_url: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for raw_part in srcset.split(","):
        part = raw_part.strip()
        if not part:
            continue
        pieces = part.split()
        url = urljoin(base_url, pieces[0])
        descriptor = " ".join(pieces[1:])
        items.append((url, descriptor))
    return items


def format_srcset(items: Iterable[tuple[str, str]]) -> str:
    formatted = []
    for url, descriptor in items:
        formatted.append(f"{url} {descriptor}".strip())
    return ", ".join(formatted)


def normalize_page_url(url: str) -> str:
    parsed = urlparse(url)
    query_items = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        lower_key = key.lower()
        if lower_key in TRACKING_QUERY_KEYS:
            continue
        if any(lower_key.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
        query_items.append((key, value))
    normalized_query = urlencode(query_items, doseq=True)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path or "/",
            "",
            normalized_query,
            "",
        )
    )


def is_crawlable_page_url(url: str, start_netloc: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.lower() != start_netloc.lower():
        return False
    suffix = Path(parsed.path).suffix.lower()
    return suffix not in STATIC_EXTENSIONS


def local_html_path_for_url(url: str, start_url: str) -> Path:
    normalized_url = normalize_page_url(url)
    normalized_start = normalize_page_url(start_url)
    if normalized_url == normalized_start:
        return Path("index.html")

    parsed = urlparse(normalized_url)
    safe_path = parsed.path.strip("/") or "index"
    if parsed.query:
        query_hash = hashlib.sha256(parsed.query.encode("utf-8")).hexdigest()[:8]
        safe_path = f"{safe_path}/query-{query_hash}"
    return Path("pages") / safe_path / "index.html"


def relative_ref(from_html_path: Path, target_path: Path) -> str:
    return Path(
        os.path.relpath(target_path.as_posix(), start=from_html_path.parent.as_posix() or ".")
    ).as_posix()


def extract_crawl_links(soup: BeautifulSoup, page_url: str, start_netloc: str) -> list[str]:
    links: OrderedDict[str, None] = OrderedDict()
    for tag in soup.find_all("a", href=True):
        href = tag.get("href")
        if not isinstance(href, str):
            continue
        absolute = normalize_page_url(urljoin(page_url, href.strip()))
        if is_crawlable_page_url(absolute, start_netloc):
            links.setdefault(absolute, None)
    return list(links.keys())


def rewrite_page_links(
    soup: BeautifulSoup,
    page_url: str,
    url_to_output_path: dict[str, Path],
    page_output_path: Path,
) -> None:
    for tag in soup.find_all("a", href=True):
        href = tag.get("href")
        if not isinstance(href, str):
            continue
        absolute = normalize_page_url(urljoin(page_url, href.strip()))
        target_path = url_to_output_path.get(absolute)
        if target_path:
            tag["href"] = relative_ref(page_output_path, target_path)


def is_image_reference(tag, attr: str) -> bool:
    if tag is None or not getattr(tag, "name", None):
        return False
    if tag.name == "img" and attr in {*IMAGE_URL_ATTRS, *SRCSET_ATTRS}:
        return True
    if tag.name == "source" and attr in SRCSET_ATTRS:
        return True
    if tag.name == "link" and attr == "href":
        rel_values = tag.get("rel") or []
        rel_text = " ".join(rel_values).lower() if isinstance(rel_values, list) else str(rel_values).lower()
        return "icon" in rel_text
    if tag.name == "meta" and attr == "content":
        meta_key = (tag.get("name") or tag.get("property") or "").strip().lower()
        return meta_key in IMAGE_META_KEYS
    return False


def collect_translation_keys(soup: BeautifulSoup) -> list[str]:
    keys: OrderedDict[str, None] = OrderedDict()

    for text_node in soup.find_all(string=True):
        parent = text_node.parent
        if parent and parent.name in SKIP_TEXT_TAGS:
            continue
        text = str(text_node).strip()
        if should_translate_value(text):
            keys.setdefault(text, None)

    for tag in soup.find_all(True):
        for attr in TRANSLATABLE_ATTRS:
            value = tag.get(attr)
            if isinstance(value, str) and should_translate_value(value):
                keys.setdefault(value.strip(), None)

        if tag.name == "meta":
            meta_key = (tag.get("name") or tag.get("property") or "").strip().lower()
            content = tag.get("content")
            if meta_key in META_TRANSLATABLE_KEYS and isinstance(content, str):
                if should_translate_value(content):
                    keys.setdefault(content.strip(), None)

    return list(keys.keys())


def load_or_create_translations(path: Path, keys: list[str]) -> dict[str, str]:
    existing: dict[str, str] = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))

    merged: OrderedDict[str, str] = OrderedDict()
    for key in keys:
        merged[key] = existing.get(key, "")
    for key, value in existing.items():
        if key not in merged:
            merged[key] = value

    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return dict(merged)


def apply_translations(soup: BeautifulSoup, translations: dict[str, str]) -> None:
    for text_node in list(soup.find_all(string=True)):
        parent = text_node.parent
        if parent and parent.name in SKIP_TEXT_TAGS:
            continue
        key = str(text_node).strip()
        replacement = translations.get(key, "").strip()
        if key and replacement:
            text_node.replace_with(replace_text_preserving_space(str(text_node), replacement))

    for tag in soup.find_all(True):
        for attr in TRANSLATABLE_ATTRS:
            value = tag.get(attr)
            if not isinstance(value, str):
                continue
            replacement = translations.get(value.strip(), "").strip()
            if replacement:
                tag[attr] = replacement

        if tag.name == "meta":
            meta_key = (tag.get("name") or tag.get("property") or "").strip().lower()
            content = tag.get("content")
            if meta_key in META_TRANSLATABLE_KEYS and isinstance(content, str):
                replacement = translations.get(content.strip(), "").strip()
                if replacement:
                    tag["content"] = replacement


def extension_for(url: str, content_type: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix
    if suffix and len(suffix) <= 8:
        return suffix.split("?")[0]
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    return ".bin"


def download_asset(
    session: requests.Session,
    url: str,
    assets_dir: Path,
    cache: dict[str, str],
    report: dict[str, list],
) -> str | None:
    if url in cache:
        return cache[url]

    try:
        response = session.get(url, timeout=20)
        response.raise_for_status()
        
        content = response.content
        content_type = response.headers.get("Content-Type", "").lower()
        is_css = "text/css" in content_type or urlparse(url).path.endswith(".css")
        
        ext = extension_for(url, response.headers.get("Content-Type"))
        if not ext and is_css:
            ext = ".css"
            
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        filename = f"{digest}{ext}"
        
        # If it's CSS, rewrite inner url()s recursively
        if is_css:
            text = response.text
            css_url_re = re.compile(r'''url\((['"]?)(.*?)\1\)''', re.IGNORECASE)
            
            def repl(match):
                inner_url = match.group(2).strip()
                if inner_url.startswith("data:"):
                    return match.group(0)
                abs_inner_url = urljoin(url, inner_url)
                local_inner = download_asset(session, abs_inner_url, assets_dir, cache, report)
                if local_inner:
                    return f'url("{Path(local_inner).name}")'
                return match.group(0)
                
            text = css_url_re.sub(repl, text)
            content = text.encode("utf-8")
            
    except requests.RequestException as exc:
        report["failed_assets"].append({"url": url, "error": str(exc)})
        return None

    target = assets_dir / filename
    target.write_bytes(content)
    root_ref = f"assets/{filename}"
    cache[url] = root_ref
    report["downloaded_assets"].append({"url": url, "path": root_ref})
    return root_ref


def reset_assets_dir(assets_dir: Path) -> None:
    if assets_dir.exists():
        shutil.rmtree(assets_dir)
    assets_dir.mkdir(parents=True, exist_ok=True)


def localize_images(
    soup: BeautifulSoup,
    base_url: str,
    session: requests.Session,
    assets_dir: Path,
    report: dict[str, list],
    page_output_path: Path = Path("index.html"),
    cache: dict[str, str] | None = None,
) -> None:
    if cache is None:
        cache = {}

    css_url_re = re.compile(r'''url\((['"]?)(.*?)\1\)''', re.IGNORECASE)

    for tag in soup.find_all(True):
        # 1. Image and general references
        for attr in IMAGE_URL_ATTRS:
            if not is_image_reference(tag, attr):
                continue
            value = tag.get(attr)
            if not isinstance(value, str) or not value.strip():
                continue
            remote_url = urljoin(base_url, value.strip())
            if not REMOTE_RE.match(remote_url):
                continue
            local_ref = download_asset(session, remote_url, assets_dir, cache, report)
            if local_ref:
                tag[attr] = relative_ref(page_output_path, Path(local_ref))

        for attr in SRCSET_ATTRS:
            if not is_image_reference(tag, attr):
                continue
            value = tag.get(attr)
            if not isinstance(value, str) or not value.strip():
                continue
            localized_items: list[tuple[str, str]] = []
            for remote_url, descriptor in parse_srcset(value, base_url):
                local_ref = download_asset(session, remote_url, assets_dir, cache, report)
                page_ref = relative_ref(page_output_path, Path(local_ref)) if local_ref else remote_url
                localized_items.append((page_ref, descriptor))
            tag[attr] = format_srcset(localized_items)

        for attr in ("href", "content"):
            if not is_image_reference(tag, attr):
                # Check if it's a stylesheet link we missed in is_image_reference
                if tag.name == "link" and attr == "href":
                    rel_vals = tag.get("rel") or []
                    if isinstance(rel_vals, str): rel_vals = [rel_vals]
                    if "stylesheet" not in [r.lower() for r in rel_vals]:
                        continue
                else:
                    continue
            value = tag.get(attr)
            if not isinstance(value, str) or not value.strip():
                continue
            remote_url = urljoin(base_url, value.strip())
            if not REMOTE_RE.match(remote_url):
                continue
            local_ref = download_asset(session, remote_url, assets_dir, cache, report)
            if local_ref:
                tag[attr] = relative_ref(page_output_path, Path(local_ref))
                
        # 2. Inline style attributes
        if tag.get("style"):
            text = tag["style"]
            def repl(match):
                inner_url = match.group(2).strip()
                if inner_url.startswith("data:"): return match.group(0)
                abs_inner_url = urljoin(base_url, inner_url)
                local_inner = download_asset(session, abs_inner_url, assets_dir, cache, report)
                if local_inner:
                    return f'url("{relative_ref(page_output_path, Path(local_inner))}")'
                return match.group(0)
            new_text = css_url_re.sub(repl, text)
            if new_text != text:
                tag["style"] = new_text

    # 3. Inline style tags
    for style in soup.find_all("style"):
        if not style.string: continue
        text = style.string
        def repl(match):
            inner_url = match.group(2).strip()
            if inner_url.startswith("data:"): return match.group(0)
            abs_inner_url = urljoin(base_url, inner_url)
            local_inner = download_asset(session, abs_inner_url, assets_dir, cache, report)
            if local_inner:
                return f'url("{relative_ref(page_output_path, Path(local_inner))}")'
            return match.group(0)
        new_text = css_url_re.sub(repl, text)
        if new_text != text:
            style.string = new_text


def remove_remote_active_content(soup: BeautifulSoup) -> None:
    for tag in list(soup.find_all(["script", "iframe"])):
        src = tag.get("src")
        if isinstance(src, str) and REMOTE_RE.match(src.strip()):
            tag.decompose()


def add_study_notice(soup: BeautifulSoup, title: str) -> None:
    body = soup.body
    if body is None:
        body = soup.new_tag("body")
        if soup.html:
            soup.html.append(body)
        else:
            soup.append(body)

    notice = soup.new_tag("div")
    notice["style"] = (
        "background:#fff3cd;color:#5f4700;padding:12px 16px;"
        "font-size:14px;line-height:1.6;border-bottom:1px solid #f1d38a;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
    )
    notice.string = f"个人日语学习用离线中文版本：{title}。图片已尽量保存为本地路径；未本地化资源见 report.json。"
    body.insert(0, notice)


def find_remaining_remote_references(soup: BeautifulSoup) -> list[dict[str, str]]:
    remaining: list[dict[str, str]] = []
    attrs = ("src", "srcset", "href", "style", "content")
    for tag in soup.find_all(True):
        for attr in attrs:
            value = tag.get(attr)
            if isinstance(value, str) and REMOTE_RE.search(value):
                remaining.append({"tag": tag.name or "", "attr": attr, "value": value})
    return remaining


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            )
        }
    )
    return session


def make_report() -> dict[str, list]:
    return {
        "downloaded_assets": [],
        "failed_assets": [],
        "remaining_remote_references": [],
    }


def process_page_html(
    html: str,
    page_url: str,
    output: Path,
    page_output_path: Path,
    title: str,
    session: requests.Session,
    assets_dir: Path,
    translations_path: Path,
    report: dict[str, list],
    asset_cache: dict[str, str] | None = None,
) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    localize_images(soup, page_url, session, assets_dir, report, page_output_path, asset_cache)
    remove_remote_active_content(soup)
    keys = collect_translation_keys(soup)
    translations = load_or_create_translations(translations_path, keys)
    apply_translations(soup, translations)
    add_study_notice(soup, title)
    report["remaining_remote_references"].extend(find_remaining_remote_references(soup))

    target = output / page_output_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(soup), encoding="utf-8")
    return soup


def save_translated_page(url: str, output: Path, title: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    assets_dir = output / "assets"
    translations_path = output / "translations.json"
    report_path = output / "report.json"

    session = build_session()
    response = session.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = response.encoding or response.apparent_encoding
    html = response.text

    (output / "original.html").write_text(html, encoding="utf-8")
    report = make_report()
    reset_assets_dir(assets_dir)
    process_page_html(
        html=html,
        page_url=response.url,
        output=output,
        page_output_path=Path("index.html"),
        title=title,
        session=session,
        assets_dir=assets_dir,
        translations_path=translations_path,
        report=report,
        asset_cache={},
    )

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def random_delay_seconds(min_delay: float, max_delay: float) -> float:
    if min_delay < 0 or max_delay < 0:
        raise ValueError("Delay values must be non-negative")
    if min_delay > max_delay:
        raise ValueError("min-delay must be less than or equal to max-delay")
    return random.uniform(min_delay, max_delay)


def save_recursive_pages(
    url: str,
    output: Path,
    title: str,
    max_pages: int = 200,
    min_delay: float = 1.0,
    max_delay: float = 10.0,
) -> None:
    if max_pages < 1:
        raise ValueError("max-pages must be at least 1")
    output.mkdir(parents=True, exist_ok=True)
    assets_dir = output / "assets"
    translations_path = output / "translations.json"
    crawl_report_path = output / "crawl_report.json"
    sitemap_path = output / "sitemap.json"
    session = build_session()
    start_url = normalize_page_url(url)
    start_netloc = urlparse(start_url).netloc
    queue = deque([start_url])
    visited: set[str] = set()
    queued: set[str] = {start_url}
    failures: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    url_to_output_path: dict[str, Path] = {}
    page_records: list[dict[str, str]] = []
    page_soups: dict[str, BeautifulSoup] = {}
    asset_cache: dict[str, str] = {}
    report = make_report()

    reset_assets_dir(assets_dir)

    while queue and len(visited) < max_pages:
        current_url = queue.popleft()
        if current_url in visited:
            continue

        page_output_path = local_html_path_for_url(current_url, start_url)
        url_to_output_path[current_url] = page_output_path

        try:
            response = session.get(current_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as exc:
            failures.append({"url": current_url, "error": str(exc)})
            visited.add(current_url)
            continue

        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            skipped.append({"url": current_url, "reason": f"non-html: {content_type}"})
            visited.add(current_url)
            continue

        response.encoding = response.encoding or response.apparent_encoding
        html = response.text
        if current_url == start_url:
            (output / "original.html").write_text(html, encoding="utf-8")

        soup = process_page_html(
            html=html,
            page_url=response.url,
            output=output,
            page_output_path=page_output_path,
            title=title,
            session=session,
            assets_dir=assets_dir,
            translations_path=translations_path,
            report=report,
            asset_cache=asset_cache,
        )
        page_soups[current_url] = soup
        page_records.append({"url": current_url, "path": page_output_path.as_posix()})
        visited.add(current_url)

        for link in extract_crawl_links(soup, response.url, start_netloc):
            if link in visited or link in queued:
                continue
            if len(visited) + len(queue) >= max_pages:
                break
            queue.append(link)
            queued.add(link)

        if queue and len(visited) < max_pages:
            time.sleep(random_delay_seconds(min_delay, max_delay))

    for page_url, soup in page_soups.items():
        page_output_path = url_to_output_path[page_url]
        rewrite_page_links(soup, page_url, url_to_output_path, page_output_path)
        (output / page_output_path).write_text(str(soup), encoding="utf-8")

    crawl_report = {
        "start_url": start_url,
        "max_pages": max_pages,
        "visited_pages": len(visited),
        "successful_pages": page_records,
        "failed_pages": failures,
        "skipped_pages": skipped,
        "asset_report": report,
    }
    crawl_report_path.write_text(
        json.dumps(crawl_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    sitemap_path.write_text(
        json.dumps(
            {url: path.as_posix() for url, path in sorted(url_to_output_path.items())},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Single webpage URL to save")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--title", default="网页", help="Display title for study notice")
    parser.add_argument("--recursive", action="store_true", help="Crawl same-domain pages")
    parser.add_argument("--max-pages", type=int, default=200, help="Maximum pages in recursive mode")
    parser.add_argument("--min-delay", type=float, default=1.0, help="Minimum crawl delay in seconds")
    parser.add_argument("--max-delay", type=float, default=10.0, help="Maximum crawl delay in seconds")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.recursive:
        save_recursive_pages(
            args.url,
            args.output,
            args.title,
            max_pages=args.max_pages,
            min_delay=args.min_delay,
            max_delay=args.max_delay,
        )
    else:
        save_translated_page(args.url, args.output, args.title)


if __name__ == "__main__":
    main()
