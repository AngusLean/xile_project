import os
import re
import time
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

TARGET_DIR = 'output/mainichigahakken-recursive'
RANKLET_JS_URL = "https://pro.ranklet4.com/widgets/nCoy0eKXP3bO0eXtl8uV.js"
LOCAL_RANKLET_JS = "assets/js/ranklet.js"

translator = GoogleTranslator(source='ja', target='zh-CN')

def translate_text(text):
    text = text.strip()
    if not text:
        return text
    try:
        return translator.translate(text)
    except Exception as e:
        print(f"Translation failed for {text}: {e}")
        return text

def fix_url(url):
    # Same logic as fix_nav_urls.py
    if url.startswith('/pages/'):
        url = url.replace('/pages/', '/')
        url = url.replace('/index.html', '')
    
    if url == '/' or url == '' or url == '/index.html':
        return r'/index.html'
    elif url.startswith('http'):
        # Only rewrite mainichigahakken.net links
        if 'mainichigahakken.net' in url:
            path = url.split('mainichigahakken.net')[1].split('?')[0].split('#')[0]
            if path == '/' or path == '':
                return '/index.html'
            path = path.lstrip('/')
            if path.endswith('/'):
                path = path[:-1]
            return f'/pages/{path}/index.html'
        return url
    else:
        url = url.lstrip('/')
        if url.endswith('/'):
            url = url[:-1]
        return f'/pages/{url}/index.html'

def process_ranklet_js():
    js_path = os.path.join(TARGET_DIR, LOCAL_RANKLET_JS)
    os.makedirs(os.path.dirname(js_path), exist_ok=True)
    
    resp = requests.get(RANKLET_JS_URL)
    content = resp.text
    
    # Extract innerHTML string
    m = re.search(r"innerHTML='(<ol class=\"ranklet\">.*?)';", content, re.DOTALL)
    if m:
        html_str = m.group(1)
        # Parse with BS4
        soup = BeautifulSoup(html_str, 'html.parser')
        
        # Translate text nodes
        for text_node in soup.find_all(string=True):
            s = text_node.string.strip()
            if s and len(s) > 1:
                translated = translate_text(s)
                text_node.string.replace_with(translated)
                time.sleep(0.5)
                
        # Fix hrefs
        for a in soup.find_all('a', href=True):
            a['href'] = fix_url(a['href'])
            
        # Reconstruct JS
        new_html_str = str(soup).replace("'", "\\'") # escape single quotes
        new_content = content[:m.start(1)] + new_html_str + content[m.end(1):]
        
        with open(js_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Ranklet JS downloaded and translated.")
    else:
        print("Could not find HTML in Ranklet JS.")

def update_html_files():
    count = 0
    for root, dirs, files in os.walk(TARGET_DIR):
        for file in files:
            if file.endswith('.html'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = content
                # Replace script URL
                new_content = new_content.replace(RANKLET_JS_URL, "/" + LOCAL_RANKLET_JS)
                
                # Translate aside_data fixed strings
                replacements = {
                    r'\>おすすめ情報【PR】\<': r'\>推荐信息【PR】\<',
                    r'\>編集部おすすめ\<': r'\>编辑部推荐\<',
                    r'\>ピックアップ\<': r'\>精选\<',
                }
                for k, v in replacements.items():
                    new_content = re.sub(k, v, new_content)
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    count += 1
    print(f"Updated {count} HTML files with translated aside_data.")

if __name__ == '__main__':
    process_ranklet_js()
    update_html_files()
