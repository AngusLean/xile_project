import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import save_translate_page
import requests

MISSING_URLS = [
    "https://mainichigahakken.net/future/new/article.php",
    "https://mainichigahakken.net/consultation/new/article.php",
    "https://mainichigahakken.net/special/",
    "https://mainichigahakken.net/serialization/comic/"
]

output_dir = Path("output/mainichigahakken-recursive")
assets_dir = output_dir / "assets"
translations_path = output_dir / "translations.json"
session = save_translate_page.build_session()
report = save_translate_page.make_report()
asset_cache = {}

start_url = "https://mainichigahakken.net/"

for url in MISSING_URLS:
    print(f"Fetching {url}...")
    page_output_path = save_translate_page.local_html_path_for_url(url, start_url)
    
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        html = resp.text
        
        soup = save_translate_page.process_page_html(
            html=html,
            page_url=url,
            output=output_dir,
            page_output_path=page_output_path,
            title="毎日が発見",
            session=session,
            assets_dir=assets_dir,
            translations_path=translations_path,
            report=report,
            asset_cache=asset_cache
        )
        print(f"Saved {url} to {page_output_path}")
    except Exception as e:
        print(f"Failed {url}: {e}")

print("Done fetching missing pages.")
