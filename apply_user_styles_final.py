# apply_user_styles_final.py
import os
from docx import Document

# 경로 설정
user_template_path = "src/templates/docx/reports/user_custom_template.docx"
official_template_path = "src/templates/docx/reports/professional_report_template.docx"

def copy_styles(from_doc_path, to_doc_path):
    """'from_doc'의 스타일을 'to_doc'으로 복사합니다."""
    try:
        source_doc = Document(from_doc_path)
        # 공식 템플릿을 열어 여기에 스타일을 덮어씁니다.
        target_doc = Document(to_doc_path)

        # 기존 스타일을 초기화하지 않고, 소스 문서의 스타일을 기반으로 업데이트/추가합니다.
        for style in source_doc.styles:
            if style.name not in [s.name for s in target_doc.styles]:
                target_style = target_doc.styles.add_style(style.name, style.type)
            else:
                target_style = target_doc.styles[style.name]

            # 폰트 속성 복사
            target_style.font.name = style.font.name
            target_style.font.size = style.font.size
            target_style.font.bold = style.font.bold
            target_style.font.italic = style.font.italic
            target_style.font.underline = style.font.underline
            if style.font.color and style.font.color.rgb:
                target_style.font.color.rgb = style.font.color.rgb
            
            # 문단 속성 복사
            target_style.paragraph_format.alignment = style.paragraph_format.alignment
            target_style.paragraph_format.first_line_indent = style.paragraph_format.first_line_indent
            target_style.paragraph_format.left_indent = style.paragraph_format.left_indent
            target_style.paragraph_format.right_indent = style.paragraph_format.right_indent
            target_style.paragraph_format.space_before = style.paragraph_format.space_before
            target_style.paragraph_format.space_after = style.paragraph_format.space_after
            target_style.paragraph_format.line_spacing = style.paragraph_format.line_spacing

        target_doc.save(to_doc_path)
        print(f"성공: '{os.path.basename(from_doc_path)}'의 스타일을 '{os.path.basename(to_doc_path)}'에 성공적으로 적용했습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")

copy_styles(user_template_path, official_template_path)
