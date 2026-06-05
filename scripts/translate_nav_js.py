import os
import re

TARGET_DIR = 'output/mainichigahakken-recursive'

REPLACEMENTS = {
    r'>健康<': '>健康<',
    r'>ライフプラン<': '>人生规划<',
    r'>暮らし<': '>生活<',
    r'>趣味<': '>爱好<',
    r'>体験記<': '>体验记<',
    r'>お悩み<': '>烦恼<',
    r'>特集<': '>特辑<',
    r'>連載<': '>连载<',
    r'>発見隊<': '>发现队<',
    r'>毎日が発見ネット<': '>每天发现网<',
    r'>人生のちょっと先のことがわかる！<': '>了解一点人生未来的事！<',
    r'placeholder=\\"検索...\\"': r'placeholder=\"搜索...\"',
    r'>お問い合わせ<': '>联系我们<',
    r'>プライバシーポリシー<': '>隐私政策<',
    r'>利用規約<': '>使用条款<',
    r'>会社概要<': '>公司概要<',
    r'>このサイトについて<': '>关于本站<'
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in REPLACEMENTS.items():
        new_content = re.sub(old, new, new_content)
        
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

print(f"Updated {count} HTML files.")
