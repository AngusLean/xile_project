import os
import re

TARGET_DIR = 'output/mainichigahakken-recursive'

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    def replace_in_header(m):
        header_str = m.group(0)
        
        def rep_href(hm):
            url = hm.group(2)
            # if it's already /pages/..., let's fix it
            if url.startswith('/pages/'):
                url = url.replace('/pages/', '/')
                url = url.replace('/index.html', '')
            
            if url == '/' or url == '' or url == '/index.html':
                return r'href="/index.html"'
            elif url.startswith('http'):
                return hm.group(0) # Keep external links
            else:
                url = url.lstrip('/')
                if url.endswith('/'):
                    url = url[:-1]
                return f'href="/pages/{url}/index.html"'
                
        new_header = re.sub(r'href=(\\"|")([^\\"]+)\1', rep_href, header_str)
        return new_header

    new_content = re.sub(r"headerContents\s*=\s*'([^']+)'", replace_in_header, content)
    
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False

count = 0
for root, dirs, files in os.walk(TARGET_DIR):
    for file in files:
        if file.endswith('.html'):
            if process_file(os.path.join(root, file)):
                count += 1

print(f"Updated {count} HTML files for JS nav URLs.")
