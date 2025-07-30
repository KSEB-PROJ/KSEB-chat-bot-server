# apply_user_styles.py
import os
from docx import Document

# 경로 설정
original_user_template_path = "src/templates/docx/reports/REPORT 양식1.docx"
renamed_user_template_path = "src/templates/docx/reports/user_custom_template.docx"
official_template_path = "src/templates/docx/reports/professional_report_template.docx"

def copy_styles(from_doc_path, to_doc_path):
    """'from_doc'의 스타일을 'to_doc'으로 복사합니다."""
    try:
        source_doc = Document(from_doc_path)
        target_doc = Document()

        for style in source_doc.styles:
            target_style = target_doc.styles.add_style(style.name, style.type)
            # 폰트, 문단 등 속성 복사 (간략화된 예시)
            target_style.font.name = style.font.name
            target_style.font.size = style.font.size
            target_style.font.bold = style.font.bold
            target_style.font.italic = style.font.italic
            if style.font.color and style.font.color.rgb:
                target_style.font.color.rgb = style.font.color.rgb
            target_style.paragraph_format.line_spacing = style.paragraph_format.line_spacing

        target_doc.save(to_doc_path)
        print(f"성공: '{os.path.basename(from_doc_path)}'의 스타일을 '{os.path.basename(to_doc_path)}'에 적용했습니다.")
        return True
    except Exception as e:
        print(f"스타일 복사 중 오류 발생: {e}")
        return False

# --- 메인 로직 ---
# 1. 파일 이름 변경
try:
    if os.path.exists(original_user_template_path):
        os.rename(original_user_template_path, renamed_user_template_path)
        print(f"파일명 변경 성공: '{os.path.basename(original_user_template_path)}' -> '{os.path.basename(renamed_user_template_path)}'")
        # 2. 스타일 복사 실행
        copy_styles(renamed_user_template_path, official_template_path)
    elif os.path.exists(renamed_user_template_path):
        print("이미 파일명이 변경되었습니다. 스타일 복사를 바로 시작합니다.")
        copy_styles(renamed_user_template_path, official_template_path)
    else:
        print(f"오류: 원본 템플릿 파일 '{os.path.basename(original_user_template_path)}'을(를) 찾을 수 없습니다.")

except Exception as e:
    print(f"전체 프로세스 중 오류 발생: {e}")