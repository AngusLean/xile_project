#!/usr/bin/env python3
import os
import re
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
import concurrent.futures

def main():
    base_dir = Path('output/mainichigahakken-recursive')
    if not base_dir.exists():
        print(f"Directory {base_dir} does not exist.")
        return

    assets_dir = base_dir / 'assets'
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    html_files = list(base_dir.rglob('*.html'))
    html_files = [f for f in html_files if f.name != 'original.html']
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    })
    
    base_url = "https://mainichigahakken.net/"
    css_url_re = re.compile(r'''url\((['"]?)(.*?)\1\)''', re.IGNORECASE)
    
    cache = {} # url -> local_relative_path

    def download_asset(url):
        if url in cache:
            return cache[url]
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            
            content = resp.content
            content_type = resp.headers.get('Content-Type', '').lower()
            is_css = 'text/css' in content_type or urlparse(url).path.endswith('.css')
            
            ext = Path(urlparse(url).path).suffix
            if len(ext) > 10: ext = '.bin'
            if not ext and is_css: ext = '.css'
            
            digest = hashlib.sha256(url.encode()).hexdigest()[:16]
            filename = f"{digest}{ext}"
            
            # If it's CSS, we need to rewrite inner url()s before saving
            if is_css:
                text = resp.text
                def repl(match):
                    inner_url = match.group(2).strip()
                    if inner_url.startswith('data:'):
                        return match.group(0)
                    abs_inner_url = urljoin(url, inner_url)
                    local_inner = download_asset(abs_inner_url)
                    if local_inner:
                        # Since css will be in assets/, and inner asset will be in assets/, relative path is just filename
                        return f'url("{Path(local_inner).name}")'
                    return match.group(0)
                text = css_url_re.sub(repl, text)
                content = text.encode('utf-8')
            
            (assets_dir / filename).write_bytes(content)
            
            local_ref = f"assets/{filename}"
            cache[url] = local_ref
            return local_ref
        except Exception as e:
            print(f"Failed to download {url}: {e}")
            return None

    def relative_ref(from_html_path: Path, target_path: Path) -> str:
        return Path(os.path.relpath(target_path.as_posix(), start=from_html_path.parent.as_posix() or ".")).as_posix()

    success_count = 0
    for html_file in html_files:
        content = html_file.read_text(encoding='utf-8')
        soup = BeautifulSoup(content, 'html.parser')
        changed = False
        
        # 1. Stylesheets
        for link in soup.find_all('link'):
            rel_attr = link.get('rel')
            if not rel_attr: continue
            if isinstance(rel_attr, str):
                rel_attr = [rel_attr]
            if 'stylesheet' in [r.lower() for r in rel_attr]:
                href = link.get('href')
                if not href: continue
                abs_url = urljoin(base_url, href)
                local_ref = download_asset(abs_url)
                if local_ref:
                    link['href'] = relative_ref(html_file.relative_to(base_dir), Path(local_ref))
                    changed = True
                    
        # 2. Inline styles in head
        for style in soup.find_all('style'):
            if not style.string: continue
            text = style.string
            def repl(match):
                inner_url = match.group(2).strip()
                if inner_url.startswith('data:'): return match.group(0)
                abs_inner_url = urljoin(base_url, inner_url)
                local_inner = download_asset(abs_inner_url)
                if local_inner:
                    return f'url("{relative_ref(html_file.relative_to(base_dir), Path(local_inner))}")'
                return match.group(0)
            new_text = css_url_re.sub(repl, text)
            if new_text != text:
                style.string = new_text
                changed = True

        # 3. style attributes
        for tag in soup.find_all(style=True):
            text = tag['style']
            def repl(match):
                inner_url = match.group(2).strip()
                if inner_url.startswith('data:'): return match.group(0)
                abs_inner_url = urljoin(base_url, inner_url)
                local_inner = download_asset(abs_inner_url)
                if local_inner:
                    return f'url("{relative_ref(html_file.relative_to(base_dir), Path(local_inner))}")'
                return match.group(0)
            new_text = css_url_re.sub(repl, text)
            if new_text != text:
                tag['style'] = new_text
                changed = True
        
        if changed:
            html_file.write_text(str(soup), encoding='utf-8')
            success_count += 1
            
    print(f"Updated styles for {success_count} HTML files. Assets downloaded: {len(cache)}")

if __name__ == "__main__":
    main()
