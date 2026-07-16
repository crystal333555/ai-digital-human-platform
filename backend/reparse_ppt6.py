"""重新解析PPT并更新数据库"""
import sqlite3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.ppt_parser import parse_ppt

ppt_path = r'D:\AI_Avatar_Data\ppt\c93b043a064040ba8c761726c59a0d0d.pptx'
out_dir = r'D:\AI_Avatar_Data\ppt\c93b043a064040ba8c761726c59a0d0d_slides'
os.makedirs(out_dir, exist_ok=True)

# 解析PPT
slides = parse_ppt(ppt_path, out_dir)
print(f"Parsed {len(slides)} slides")

# 更新数据库
conn = sqlite3.connect('app.db')
c = conn.cursor()

for slide in slides:
    idx = slide['index']
    text = slide['text']
    img_path = slide['image_path']
    
    # 更新讲稿文字和图片路径
    c.execute(
        "UPDATE ppt_slides SET narration_text=?, slide_image_path=? WHERE project_id=6 AND slide_index=?",
        (text, img_path, idx)
    )
    print(f"Slide {idx}: updated text ({len(text)} chars), img={os.path.basename(img_path)}")

conn.commit()
conn.close()
print("Done!")
