"""
文件内容提取服务 - 从上传的文件中提取文本内容
支持 PDF、Word (docx)、Excel、文本文件、图片和压缩包
"""
import os
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from loguru import logger

from app.models.project import ProjectFile
from app.crud import file as file_crud
from app.utils.file_utils import ARCHIVE_EXTENSIONS
from app.services.file_extractor.extractors import (
    extract_text_file, extract_docx, extract_pdf, extract_excel, clean_text
)

TEXT_EXTENSIONS = {'txt', 'md', 'json', 'yaml', 'yml', 'csv', 'log'}
DOCX_EXTENSIONS = {'docx'}
PDF_EXTENSIONS = {'pdf'}
EXCEL_EXTENSIONS = {'xlsx', 'xls'}
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


class FileContentExtractor:
    """文件内容提取器"""

    def __init__(self, db: Session):
        self.db = db

    async def extract_file_content(self, file: ProjectFile, force_refresh: bool = False) -> Dict[str, Any]:
        """提取单个文件的内容"""
        if file.content and file.extract_status == 'completed' and not force_refresh:
            return {"success": True, "content": file.content, "from_cache": True}

        file_crud.update_file_content(self.db, file.id, None, 'processing')

        try:
            content = await self._extract_by_type(file)
            if content:
                file_crud.update_file_content(self.db, file.id, content, 'completed')
                return {"success": True, "content": content, "from_cache": False}
            else:
                file_crud.update_file_content(
                    self.db, file.id, None, 'failed',
                    extract_error="未能提取到有效内容"
                )
                return {"success": False, "error": "未能提取到有效内容"}
        except Exception as e:
            error_msg = f"提取失败: {str(e)}"
            logger.error(f"提取文件内容失败: {file.id} - {error_msg}")
            file_crud.update_file_content(
                self.db, file.id, None, 'failed',
                extract_error=error_msg
            )
            return {"success": False, "error": error_msg}

    async def _extract_by_type(self, file: ProjectFile) -> Optional[str]:
        """根据文件类型选择提取方法"""
        file_type = file.file_type.lower()

        if file_type in TEXT_EXTENSIONS:
            return await extract_text_file(file)
        elif file_type in DOCX_EXTENSIONS:
            return await extract_docx(file)
        elif file_type in PDF_EXTENSIONS:
            return await extract_pdf(file)
        elif file_type in EXCEL_EXTENSIONS:
            return await extract_excel(file)
        elif file_type in IMAGE_EXTENSIONS:
            return await self._extract_image(file)
        elif file_type in ARCHIVE_EXTENSIONS:
            return await self._extract_archive(file)
        return None

    async def _extract_image(self, file: ProjectFile) -> Optional[str]:
        """提取图片中的文字（OCR 或 AI 视觉分析）"""
        return f"【图片文件】{file.file_name} - 图片内容需要通过 AI 视觉分析提取"

    async def _extract_archive(self, file: ProjectFile) -> Optional[str]:
        """提取压缩包文件内容（列出文件清单）"""
        if not os.path.exists(file.file_url):
            logger.warning(f"文件不存在: {file.file_url}")
            return None

        try:
            import zipfile
            file_list = []

            if file.file_type.lower() == 'zip':
                with zipfile.ZipFile(file.file_url, 'r') as zf:
                    for info in zf.infolist():
                        if not info.is_dir():
                            file_list.append(info.filename)
            elif file.file_type.lower() == 'rar':
                try:
                    import rarfile
                except ImportError:
                    return f"【压缩包文件】{file.file_name} - 请安装 rarfile 库以解析 RAR 文件"
                with rarfile.RarFile(file.file_url, 'r') as rf:
                    for info in rf.infolist():
                        if not info.is_dir():
                            file_list.append(info.filename)

            if file_list:
                content = f"【压缩包文件】{file.file_name} - 包含 {len(file_list)} 个文件:\n"
                content += '\n'.join(f"  - {f}" for f in file_list[:100])
                if len(file_list) > 100:
                    content += f"\n  ... 还有 {len(file_list) - 100} 个文件未显示"
                return clean_text(content)
            return None
        except Exception as e:
            logger.error(f"解析压缩包文件失败: {e}")
            return None


async def extract_file_background(file_id: int, db: Session, force_refresh: bool = False) -> None:
    """后台提取文件内容"""
    file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not file:
        return
    extractor = FileContentExtractor(db)
    await extractor.extract_file_content(file, force_refresh)


async def batch_extract_files(file_ids: List[int], db: Session, force_refresh: bool = False) -> Dict[str, Any]:
    """批量提取文件内容"""
    results = {"total": len(file_ids), "success": 0, "failed": 0, "skipped": 0, "details": []}
    extractor = FileContentExtractor(db)

    for file_id in file_ids:
        file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
        if not file:
            results["failed"] += 1
            results["details"].append({"file_id": file_id, "status": "not_found"})
            continue

        if file.content and file.extract_status == 'completed' and not force_refresh:
            results["skipped"] += 1
            results["details"].append({"file_id": file_id, "status": "skipped", "reason": "already_extracted"})
            continue

        result = await extractor.extract_file_content(file, force_refresh)
        if result.get("success"):
            results["success"] += 1
            results["details"].append({"file_id": file_id, "status": "success"})
        else:
            results["failed"] += 1
            results["details"].append({"file_id": file_id, "status": "failed", "error": result.get("error")})

    return results


def get_file_content(file: ProjectFile) -> Optional[str]:
    """获取文件已提取的内容（如果存在）"""
    if file.content and file.extract_status == 'completed':
        return file.content
    return None


def has_extracted_content(file: ProjectFile) -> bool:
    """检查文件是否有已提取的内容"""
    return bool(file.content and file.extract_status == 'completed')
