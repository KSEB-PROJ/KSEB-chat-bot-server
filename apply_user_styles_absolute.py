# apply_user_styles_absolute.py
import os
from docx import Document

# 현재 작업 디렉터리를 기준으로 절대 경로 생성
base_dir = os.getcwd()
user_template_path = os.path.join(base_dir, "src", "templates", "docx", "reports", "user_custom_template.docx")
official_template_path = os.path.join(base_dir, "src", "templates", "docx", "reports", "professional_report_template.docx")

def copy_styles(from_doc_path, to_doc_path):
    """'from_doc'의 스타일을 'to_doc'으로 복사합니다."""
    try:
        if not os.path.exists(from_doc_path):
            print(f"오류: 소스 파일을 찾을 수 없습니다 - {from_doc_path}")
            return

        source_doc = Document(from_doc_path)
        target_doc = Document() # 새 문서를 만들어 스타일을 먼저 복사

        for style in source_doc.styles:
            try:
                target_style = target_doc.styles.add_style(style.name, style.type)
                # 속성 복사
                target_style.font.name = style.font.name
                target_style.font.size = style.font.size
                target_style.font.bold = style.font.bold
                target_style.font.italic = style.font.italic
                target_style.font.underline = style.font.underline
                if style.font.color and style.font.color.rgb:
                    target_style.font.color.rgb = style.font.color.rgb
                target_style.paragraph_format.line_spacing = style.paragraph_format.line_spacing
            except Exception:
                # 이미 존재하는 스타일일 경우 무시하고 계속
                pass

        target_doc.save(to_doc_path)
        print(f"성공: '{os.path.basename(from_doc_path)}'의 스타일을 '{os.path.basename(to_doc_path)}'에 적용했습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")

copy_styles(user_template_path, official_template_path)
