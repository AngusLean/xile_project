#!/usr/bin/env python3
import json
import sys
from pathlib import Path
from bs4 import BeautifulSoup

def apply_translations():
    base_dir = Path('output/mainichigahakken-recursive')
    json_path = base_dir / 'translations.json'
    
    if not json_path.exists():
        print("Error: translations.json not found")
        sys.exit(1)
        
    with open(json_path, 'r', encoding='utf-8') as f:
        translations = json.load(f)
        
    # 查找所有 html 文件
    html_files = list(base_dir.rglob('*.html'))
    # 排除备份文件
    html_files = [f for f in html_files if f.name != 'original.html']
    
    print(f"Found {len(html_files)} HTML files to process.")
    
    success_count = 0
    for html_file in html_files:
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 找到所有可能包含日文文本的节点并替换
            changed = False
            for text_node in soup.find_all(string=True):
                if text_node.parent.name in ['script', 'style', 'noscript']:
                    continue
                original_text = text_node.strip()
                if not original_text:
                    continue
                    
                # 从字典中查找翻译
                if original_text in translations:
                    translated = translations[original_text]
                    if translated and translated != "[翻译失败]":
                        text_node.replace_with(text_node.replace(original_text, translated))
                        changed = True
                        
            # 如果有替换，写回文件
            if changed:
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                success_count += 1
                
        except Exception as e:
            print(f"Error processing {html_file}: {e}")
            
    print(f"Done! Successfully updated {success_count} HTML files with translations.")

if __name__ == "__main__":
    apply_translations()
