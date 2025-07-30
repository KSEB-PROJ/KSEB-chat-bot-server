# style_inspector_v2.py
import os
from docx import Document

TEMPLATE_PATH = os.path.abspath("src/templates/docx/reports/professional_report_template.docx")

try:
    doc = Document(TEMPLATE_PATH)
    styles = doc.styles
    
    print(f"'{os.path.basename(TEMPLATE_PATH)}' 파일에서 발견된 전체 스타일 목록:")
    print("-" * 50)
    
    # 모든 스타일(문단, 글자, 표)의 이름을 출력
    for style in styles:
        try:
            print(f"- 이름: '{style.name}', 타입: {style.type}")
        except:
            pass # 일부 오래된 스타일 객체는 type 속성이 없을 수 있음

    print("-" * 50)

except Exception as e:
    print(f"오류 발생: {e}")
