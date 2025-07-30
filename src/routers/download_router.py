
import os
import tempfile
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/v1/download", tags=["Download"])

@router.get("/{filename}")
async def download_file(filename: str):
    """생성된 파일을 임시 디렉터리에서 찾아 다운로드합니다."""
    # 보안을 위해 파일 이름에 경로 조작 문자가 있는지 확인
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="잘못된 파일 이름입니다.")

    temp_dir = tempfile.gettempdir()
    file_path = os.path.join(temp_dir, filename)

    print(f"⬇️ Download request for: {file_path}")

    if os.path.exists(file_path):
        print("   -> File found. Sending response.")
        return FileResponse(
            path=file_path,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            filename=filename
        )
    
    print("   -> ❌ File NOT FOUND.")
    raise HTTPException(status_code=404, detail="파일을 찾을 수 없거나 만료되었습니다.")

