from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bs4 import BeautifulSoup

from scripts.save_translate_page import (
    collect_translation_keys,
    extract_crawl_links,
    is_image_reference,
    is_crawlable_page_url,
    local_html_path_for_url,
    normalize_page_url,
    parse_srcset,
    random_delay_seconds,
    remove_remote_active_content,
    replace_text_preserving_space,
    reset_assets_dir,
    rewrite_page_links,
    should_translate_value,
)


class SaveTranslatePageTests(unittest.TestCase):
    def test_parse_srcset_resolves_urls_and_preserves_descriptors(self):
        items = parse_srcset(
            "/img/a.jpg 1x, //cdn.example.com/b.webp 2x, https://x.test/c.png 640w",
            "https://example.com/articles/page.html",
        )

        self.assertEqual(
            items,
            [
                ("https://example.com/img/a.jpg", "1x"),
                ("https://cdn.example.com/b.webp", "2x"),
                ("https://x.test/c.png", "640w"),
            ],
        )

    def test_replace_text_preserving_space_keeps_surrounding_whitespace(self):
        replaced = replace_text_preserving_space("\n  毎日が発見  ", "每日发现")

        self.assertEqual(replaced, "\n  每日发现  ")

    def test_collect_translation_keys_skips_script_and_machine_values(self):
        soup = BeautifulSoup(
            """
            <html>
              <head><meta name="description" content="暮らしを楽しむ"></head>
              <body>
                <script>const label = "翻訳しない";</script>
                <img alt="健康のヒント" src="/a.jpg">
                <a title="記事を読む">続きを読む</a>
                <p>毎日が発見</p>
                <p>12345</p>
              </body>
            </html>
            """,
            "html.parser",
        )

        keys = collect_translation_keys(soup)

        self.assertIn("暮らしを楽しむ", keys)
        self.assertIn("健康のヒント", keys)
        self.assertIn("記事を読む", keys)
        self.assertIn("続きを読む", keys)
        self.assertIn("毎日が発見", keys)
        self.assertNotIn("翻訳しない", keys)
        self.assertNotIn("12345", keys)

    def test_should_translate_value_rejects_urls_numbers_and_tokens(self):
        self.assertFalse(should_translate_value("https://example.com/a.jpg"))
        self.assertFalse(should_translate_value("12345"))
        self.assertFalse(should_translate_value("header_nav"))
        self.assertTrue(should_translate_value("暮らしを楽しむ"))

    def test_is_image_reference_excludes_scripts_and_includes_icons(self):
        soup = BeautifulSoup(
            """
            <html>
              <script src="https://example.com/app.js"></script>
              <link rel="icon" href="https://example.com/favicon.png">
              <meta property="og:image" content="https://example.com/og.jpg">
              <img src="https://example.com/a.jpg">
            </html>
            """,
            "html.parser",
        )

        self.assertFalse(is_image_reference(soup.script, "src"))
        self.assertTrue(is_image_reference(soup.link, "href"))
        self.assertTrue(is_image_reference(soup.meta, "content"))
        self.assertTrue(is_image_reference(soup.img, "src"))

    def test_remove_remote_active_content_removes_tracking_scripts_and_iframes(self):
        soup = BeautifulSoup(
            """
            <html><body>
              <script src="https://example.com/tracker.js"></script>
              <script>window.keep = true;</script>
              <iframe src="https://example.com/embed"></iframe>
            </body></html>
            """,
            "html.parser",
        )

        remove_remote_active_content(soup)

        self.assertIsNone(soup.find("iframe"))
        self.assertIsNone(soup.find("script", src=True))
        self.assertIsNotNone(soup.find("script"))

    def test_reset_assets_dir_removes_stale_files(self):
        with TemporaryDirectory() as tmpdir:
            assets_dir = Path(tmpdir) / "assets"
            assets_dir.mkdir()
            stale = assets_dir / "stale.js"
            stale.write_text("old", encoding="utf-8")

            reset_assets_dir(assets_dir)

            self.assertTrue(assets_dir.exists())
            self.assertFalse(stale.exists())

    def test_normalize_page_url_removes_tracking_query_and_fragment(self):
        normalized = normalize_page_url(
            "https://mainichigahakken.net/a/?utm_source=x&b=2#top"
        )

        self.assertEqual(normalized, "https://mainichigahakken.net/a/?b=2")

    def test_is_crawlable_page_url_filters_scope_and_assets(self):
        start_netloc = "mainichigahakken.net"

        self.assertTrue(
            is_crawlable_page_url("https://mainichigahakken.net/health/article/a.php", start_netloc)
        )
        self.assertFalse(is_crawlable_page_url("https://example.com/a", start_netloc))
        self.assertFalse(is_crawlable_page_url("mailto:test@example.com", start_netloc))
        self.assertFalse(is_crawlable_page_url("javascript:void(0)", start_netloc))
        self.assertFalse(is_crawlable_page_url("https://mainichigahakken.net/a.jpg", start_netloc))

    def test_local_html_path_for_url_maps_home_and_articles(self):
        start_url = "https://mainichigahakken.net/"

        self.assertEqual(local_html_path_for_url(start_url, start_url), Path("index.html"))
        self.assertEqual(
            local_html_path_for_url(
                "https://mainichigahakken.net/health/article/a.php", start_url
            ),
            Path("pages/health/article/a.php/index.html"),
        )

    def test_extract_crawl_links_returns_normalized_same_domain_links(self):
        soup = BeautifulSoup(
            """
            <a href="/health/article/a.php#comments">A</a>
            <a href="https://example.com/out">Out</a>
            <a href="/image.jpg">Image</a>
            <a href="javascript:void(0)">JS</a>
            """,
            "html.parser",
        )

        links = extract_crawl_links(
            soup,
            "https://mainichigahakken.net/",
            "mainichigahakken.net",
        )

        self.assertEqual(links, ["https://mainichigahakken.net/health/article/a.php"])

    def test_rewrite_page_links_uses_relative_local_paths(self):
        soup = BeautifulSoup(
            """
            <a href="/health/article/a.php">A</a>
            <a href="https://example.com/out">Out</a>
            """,
            "html.parser",
        )
        url_to_output_path = {
            "https://mainichigahakken.net/": Path("index.html"),
            "https://mainichigahakken.net/health/article/a.php": Path(
                "pages/health/article/a.php/index.html"
            ),
        }

        rewrite_page_links(
            soup,
            "https://mainichigahakken.net/",
            url_to_output_path,
            Path("index.html"),
        )

        links = [tag["href"] for tag in soup.find_all("a")]
        self.assertEqual(links, ["pages/health/article/a.php/index.html", "https://example.com/out"])

    def test_random_delay_seconds_stays_within_bounds(self):
        for _ in range(20):
            delay = random_delay_seconds(1.0, 10.0)
            self.assertGreaterEqual(delay, 1.0)
            self.assertLessEqual(delay, 10.0)

        self.assertEqual(random_delay_seconds(3.0, 3.0), 3.0)
        with self.assertRaises(ValueError):
            random_delay_seconds(10.0, 1.0)


if __name__ == "__main__":
    unittest.main()
