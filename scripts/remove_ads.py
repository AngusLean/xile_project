import os
import re
from bs4 import BeautifulSoup

TARGET_DIR = 'output/mainichigahakken-recursive'

# Domains and keywords associated with ads/popups
ad_domains = [
    'doubleclick.net', 'rubiconproject.com', 'amazon-adsystem.com', 
    'i-mobile.co.jp', 'relaido.jp', 'googletagmanager.com', 'c.amazon-adsystem.com'
]
ad_keywords = ['googletag', 'dataElementADs', 'apstag', 'smarttag', 'pbjs', 'headerBiddingSlots', 'gptAdSlots']

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    # We use regex for div ad-blocks first because it's safer for these specific classes
    # Some ad divs are injected by JS strings, we should also try to clean them if they appear in strings
    # But first, let's remove standard HTML ad blocks
    soup = BeautifulSoup(html, 'html.parser')
    
    changed = False

    # 1. Remove script tags matching ad criteria
    for script in soup.find_all('script'):
        src = script.get('src', '')
        if any(domain in src for domain in ad_domains):
            script.decompose()
            changed = True
            continue
        
        content = script.string or ''
        if any(keyword in content for keyword in ad_keywords):
            script.decompose()
            changed = True
            continue

    # 2. Remove div blocks that contain ads
    # Typical classes: ad-block, ad-sp_block, etc.
    # Typical ids: mhn_all_bb_gam, mhn-s_all_mb_gam, etc.
    for div in soup.find_all('div'):
        classes = div.get('class', [])
        div_id = div.get('id', '')
        
        # Check if it's an ad block by class
        if any('ad-block' in c or 'ad_sp' in c for c in classes):
            div.decompose()
            changed = True
            continue
            
        # Check if it's an ad block by ID
        if '_gam' in div_id or '_aps' in div_id or 'smarttag-adx' in div_id:
            div.decompose()
            changed = True
            continue

    # 3. There is also a Google Tag Manager noscript block
    for noscript in soup.find_all('noscript'):
        # Usually GTM noscript is empty or contains an iframe to googletagmanager
        content = str(noscript)
        if 'googletagmanager' in content or noscript.string is None:
            noscript.decompose()
            changed = True

    if not changed:
        return False

    # Convert soup back to HTML
    new_html = str(soup)

    # 4. Clean up JS string literals that inject ads
    # The header JS injects ad divs like: <div id="smarttag-adx-inst"></div>
    # and <div class="mb-20"><!-- /11970315/mhn_all_bb_gam -->...
    # We can use regex to clean up these specific string parts without breaking the JS syntax
    
    # Remove smarttag-adx-inst injection
    new_html = re.sub(r'\\<div id=\\"smarttag-adx-inst\\"\\>\\<\\/div\\>', '', new_html)
    
    # Remove mb-20 ad injections inside JS string
    new_html = re.sub(r'\\<div class=\\"mb-20\\"\\>.*?\\<\\/div\\>\\<\\/div\\>', '', new_html)
    new_html = re.sub(r'\\<div class=\\"mt-20 ranking-block.*?\\<\\/div\\>\\<\\/div\\>', '', new_html)

    # Write back if changed
    if html != new_html:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_html)
        return True
    
    return False

def main():
    count = 0
    for root, dirs, files in os.walk(TARGET_DIR):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                if process_file(filepath):
                    count += 1
                    
    print(f"Removed ads and popups from {count} HTML files.")

if __name__ == '__main__':
    main()
