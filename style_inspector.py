# style_inspector.py
import os
from docx import Document

TEMPLATE_PATH = os.path.abspath("src/templates/docx/reports/professional_report_template.docx")

try:
    doc = Document(TEMPLATE_PATH)
    styles = doc.styles
    
    print(f"'{os.path.basename(TEMPLATE_PATH)}' 파일에서 발견된 스타일 목록:")
    print("-" * 40)
    
    # 내장 스타일이 아닌, 사용자가 정의했거나 수정했을 가능성이 있는 스타일만 필터링
    user_styles = [s for s in styles if s.built_in is False]
    
    if not user_styles:
        print("사용자 정의 스타일을 찾을 수 없습니다. 기본 스타일 목록을 표시합니다.")
        user_styles = styles

    for style in user_styles:
        print(f"- 이름: '{style.name}', 타입: {style.type}")
        
    print("-" * 40)

except Exception as e:
    print(f"오류 발생: {e}")

