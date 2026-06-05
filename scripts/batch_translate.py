#!/usr/bin/env python3
import json
import time
import sys
from pathlib import Path
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor, as_completed

def translate_batch():
    json_path = Path('output/mainichigahakken-recursive/translations.json')
    if not json_path.exists():
        print("Error: translations.json not found")
        sys.exit(1)
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # 筛选需要翻译的文本
    to_translate = []
    for k, v in data.items():
        # 如果还没翻译，或者是长串且包含广告代码（简单清理）
        if not str(v).strip():
            # 过滤掉明显的脚本或广告字符串
            if "<script" in k or "window.ad" in k or "googletag" in k:
                data[k] = "" # 留空不翻译，作为过滤
            else:
                to_translate.append(k)
                
    print(f"Total keys: {len(data)}")
    print(f"To translate: {len(to_translate)}")
    
    if not to_translate:
        print("Nothing to translate.")
        return
        
    translator = GoogleTranslator(source='ja', target='zh-CN')
    
    # 备份原始文件
    backup_path = json_path.with_suffix('.json.bak')
    if not backup_path.exists():
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    # 定义翻译工作函数
    def translate_item(key, retries=3):
        for attempt in range(retries):
            try:
                # 截断过长的异常文本
                text_to_translate = key[:4999] if len(key) > 5000 else key
                res = translator.translate(text_to_translate)
                return key, res
            except Exception as e:
                if attempt == retries - 1:
                    return key, f"[翻译失败] {e}"
                time.sleep(1 + attempt)
                
    # 增量保存函数
    def save_progress():
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
    # 并发翻译（限制并发数防封）
    completed_count = 0
    batch_size = 50
    
    # 为了避免被限流，这里并发度设为 5
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(translate_item, k): k for k in to_translate}
        for future in as_completed(futures):
            key, result = future.result()
            data[key] = result
            completed_count += 1
            
            if completed_count % batch_size == 0:
                print(f"Progress: {completed_count}/{len(to_translate)}")
                save_progress()
                time.sleep(0.5) # 批次间额外停顿
                
    # 最终保存
    save_progress()
    print(f"Done! Translated {completed_count} items.")

if __name__ == "__main__":
    translate_batch()
