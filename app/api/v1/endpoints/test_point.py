from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.schemas.test_point import (
    TestPointAnalyzeRequest,
    TestPointExtractRequest,
    TestPointResponse,
    TestPointUpdate  # ✅ 新增：更新模型
)
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.crud.test_point import (
    get_test_points_by_project_and_user,
    get_test_points_count,
    batch_create_test_points
)
from app.services.ai_analysis_service import aio_analysis_service, extract_test_points_from_content
from app.services.file_content_extractor import FileContentExtractor
from fastapi.responses import StreamingResponse
import json
from loguru import logger
from app.models.project import Project, ProjectFile
import os

router = APIRouter(prefix="/test-point", tags=["测试点管理"])


@router.post("/analyze")
async def analyze_project(
    request: TestPointAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    分析项目需求并提取测试点
    
    Args:
        request: 分析请求
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        流式返回分析进度
    """
    try:
        # 生成分析进度的流式响应
        async def generate_progress():
            async for progress in aio_analysis_service.analyze_project(
                db=db,
                project_id=request.project_id,
                user_id=current_user.id
            ):
                yield f"data: {json.dumps(progress)}\n\n"
        
        return StreamingResponse(
            generate_progress(),
            media_type="text/event-stream"
        )
    except Exception as e:
        logger.error(f"分析项目失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"分析项目失败: {str(e)}"
        )


@router.get("/list/{project_id}")
async def get_test_points(
    project_id: int,
    module: Optional[str] = Query(None, description="模块名称"),
    priority: Optional[int] = Query(None, ge=1, le=3, description="优先级"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    查询指定项目的测试点列表
    
    Args:
        project_id: 项目ID
        module: 模块名称（可选）
        priority: 优先级（可选）
        page: 页码
        page_size: 每页数量
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        测试点列表
    """
    try:
        # 计算偏移量
        skip = (page - 1) * page_size
        
        # 获取测试点列表
        test_points = get_test_points_by_project_and_user(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            module=module,
            priority=priority,
            skip=skip,
            limit=page_size
        )
        
        # 获取总数量
        total = get_test_points_count(
            db=db,
            project_id=project_id,
            user_id=current_user.id,
            module=module,
            priority=priority
        )
        
        # 转换为响应模型
        items = []
        for point in test_points:
            items.append(TestPointResponse(
                id=point.id,
                project_id=point.project_id,
                module=point.module,
                function=point.function,
                point=point.point,
                priority=point.priority,
                ai_prompt=point.ai_prompt,
                create_time=point.create_time
            ))
        
        return {
            "code": 200,
            "message": "获取成功",
            "data": {
                "total": total,
                "items": items,
                "page": page,
                "page_size": page_size
            }
        }
    except Exception as e:
        logger.error(f"获取测试点列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测试点列表失败: {str(e)}"
        )


@router.get("/detail/{test_point_id}", response_model=TestPointResponse)
async def get_test_point_detail(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取测试点详情
    """
    try:
        # 检查项目权限
        from app.models.project import Project
        project = db.query(Project).filter(
            Project.id == project_id,
            Project.user_id == current_user.id
        ).first()
        
        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )
        
        # 获取测试点
        from app.crud.test_point import get_test_point_by_id
        test_point = get_test_point_by_id(db, test_point_id, project_id)
        
        if not test_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试点不存在"
            )
        
        return TestPointResponse(
            id=test_point.id,
            project_id=test_point.project_id,
            module=test_point.module,
            function=test_point.function,
            point=test_point.point,
            priority=test_point.priority,
            ai_prompt=test_point.ai_prompt,
            create_time=test_point.create_time
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取测试点详情失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取测试点详情失败: {str(e)}"
        )


@router.post("/extract")
async def extract_test_points(
    request: TestPointExtractRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据上传的需求文件提取测试点
    """
    try:
        if not request.file_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供 file_id",
            )

        file = db.query(ProjectFile).filter(
            ProjectFile.id == request.file_id,
            ProjectFile.is_active == True
        ).first()

        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="文件不存在",
            )

        project = db.query(Project).filter(
            Project.id == file.project_id,
            Project.user_id == current_user.id,
        ).first()

        if not project:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无权限操作此项目"
            )

        # 使用 FileContentExtractor 提取文件内容（支持 PDF/Word/Excel 等多格式）
        extractor = FileContentExtractor(db)
        result = await extractor.extract_file_content(file, force_refresh=False)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "无法读取文件内容"),
            )

        file_content = result.get("content", "")

        logger.info(f"文件内容提取成功, 长度: {len(file_content)}")

        if not file_content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件内容为空或无法提取",
            )

        test_points = await extract_test_points_from_content(
            content=file_content,
            project_id=file.project_id,
            user_id=current_user.id,
        )

        logger.info(f"AI提取完成, 测试点数量: {len(test_points)}")

        return {
            "code": 200,
            "message": "测试点提取成功",
            "data": {
                "items": test_points,
                "total": len(test_points),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提取测试点失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"提取测试点失败: {str(e)}",
        )


@router.post("/batch-save")
async def batch_save_test_points(
    project_id: int = Query(..., description="项目ID"),
    test_points: List[Dict[str, Any]] = Body(..., description="测试点列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量保存测试点到数据库
    """
    MAX_BATCH_SIZE = 200

    # P0: 校验项目归属权限
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == current_user.id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )

    try:
        if not test_points or not isinstance(test_points, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="测试点列表不能为空"
            )
        
        # P1修复: 数量限制防止内存溢出
        if len(test_points) > MAX_BATCH_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次保存数量不能超过{MAX_BATCH_SIZE}个"
            )
        
        # P1修复: 数据验证 - 过滤无效数据
        valid_points = []
        for i, item in enumerate(test_points):
            if not isinstance(item, dict):
                logger.warning(f"跳过无效数据项[{i}]: 非字典类型")
                continue
            
            module = str(item.get('module', '')).strip()
            func = str(item.get('function', '')).strip()
            point = str(item.get('point', '')).strip()
            
            # 必填字段检查
            if not module or not point:
                logger.warning(f"跳过数据项[{i}]: 缺少必填字段(module/point)")
                continue
            
            # 字段长度限制（与数据库字段对齐）
            if len(module) > 100 or len(func) > 200 or len(point) > 500:
                logger.warning(f"跳过数据项[{i}]: 字段超长")
                continue
            
            try:
                priority = int(item.get('priority', 2))
                if priority < 1 or priority > 3:
                    priority = 2
            except (ValueError, TypeError):
                priority = 2
            
            valid_points.append({
                'module': module,
                'function': func,
                'point': point,
                'priority': priority,
                'ai_prompt': item.get('ai_prompt')
            })
        
        if not valid_points:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有有效的测试点数据可保存"
            )
        
        saved_test_points = batch_create_test_points(
            db=db,
            project_id=project_id,
            test_points_data=valid_points
        )
        
        logger.info(f"批量保存测试点成功: {len(saved_test_points)}/{len(valid_points)} 个 (用户: {current_user.username})")
        
        return {
            "code": 200,
            "message": f"成功保存 {len(saved_test_points)} 个测试点",
            "data": {
                "saved_count": len(saved_test_points),
                "total_submitted": len(valid_points),
                "items": [
                    {
                        "id": tp.id,
                        "module": tp.module,
                        "function": tp.function,
                        "point": tp.point,
                        "priority": tp.priority
                    }
                    for tp in saved_test_points
                ]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量保存测试点失败: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"保存失败: {str(e)}"
        )


# ==================== 新增：编辑/删除/批量删除接口 ====================

# ✅ 修复m-01：提取公共的权限检查函数
def check_project_permission(db: Session, project_id: int, user_id: int) -> Project:
    """检查项目归属权限（DRY原则）"""
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.user_id == user_id
    ).first()

    if not project:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权限操作此项目"
        )
    return project


@router.put("/{test_point_id}")
async def update_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    # ✅ 修复C-01：使用Pydantic模型替代多个Body参数
    update_data: TestPointUpdate = Body(..., description="更新数据"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    更新测试点信息（符合RESTful规范）
    """
    try:
        # ✅ 使用公共权限检查函数
        project = check_project_permission(db, project_id, current_user.id)

        # 获取测试点
        from app.crud.test_point import get_test_point_by_id
        test_point = get_test_point_by_id(db, test_point_id, project_id)

        if not test_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="测试点不存在"
            )

        # 只更新提供的字段（部分更新）
        if update_data.module is not None:
            test_point.module = update_data.module
        if update_data.function is not None:
            test_point.function = update_data.function
        if update_data.point is not None:
            test_point.point = update_data.point
        if update_data.priority is not None:
            test_point.priority = update_data.priority
        if update_data.ai_prompt is not None:
            test_point.ai_prompt = update_data.ai_prompt

        db.commit()
        db.refresh(test_point)

        logger.info(f"用户 {current_user.username} 更新了测试点 {test_point_id}")

        return {
            "code": 200,
            "message": "更新成功",
            "data": TestPointResponse(
                id=test_point.id,
                project_id=test_point.project_id,
                module=test_point.module,
                function=test_point.function,
                point=test_point.point,
                priority=test_point.priority,
                ai_prompt=test_point.ai_prompt,
                create_time=test_point.create_time
            )
        }
    except HTTPException:
        raise
    except Exception as e:
        # ✅ 修复M-02：日志记录详细信息，但返回通用错误消息
        logger.error(f"更新测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


@router.delete("/batch")
async def batch_delete_test_points(
    project_id: int = Query(..., description="项目ID"),
    ids: List[int] = Body(..., description="要删除的测试点ID列表"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    批量删除测试点
    """
    MAX_BATCH_DELETE = 100

    try:
        # ✅ 使用公共权限检查函数
        project = check_project_permission(db, project_id, current_user.id)

        # ✅ 修复C-02：完善输入验证
        if not ids or not isinstance(ids, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供有效的ID列表"
            )

        # 去重并过滤无效ID（只保留正整数）
        unique_ids = list(set(filter(lambda x: isinstance(x, int) and x > 0, ids)))

        if len(unique_ids) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="没有有效的测试点ID"
            )

        if len(unique_ids) > MAX_BATCH_DELETE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"单次删除数量不能超过{MAX_BATCH_DELETE}个（当前{len(unique_ids)}个）"
            )

        # 查询属于该项目的测试点并删除
        from app.models.test_point import TestPoint as TestPointModel
        deleted_count = db.query(TestPointModel).filter(
            TestPointModel.id.in_(unique_ids),
            TestPointModel.project_id == project_id
        ).delete(synchronize_session=False)

        db.commit()

        logger.info(f"用户 {current_user.username} 批量删除了 {deleted_count} 个测试点")

        return {
            "code": 200,
            "message": f"成功删除 {deleted_count} 个测试点",
            "data": {
                "deleted_count": deleted_count,
                "requested_count": len(unique_ids)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )


@router.delete("/{test_point_id}")
async def delete_test_point(
    test_point_id: int,
    project_id: int = Query(..., description="项目ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    删除单个测试点（幂等操作）
    """
    try:
        project = check_project_permission(db, project_id, current_user.id)

        from app.crud.test_point import get_test_point_by_id
        test_point = get_test_point_by_id(db, test_point_id, project_id)

        if not test_point:
            return {
                "code": 200,
                "message": "删除成功",
                "data": {"id": test_point_id}
            }

        db.delete(test_point)
        db.commit()

        logger.info(f"用户 {current_user.username} 删除了测试点 {test_point_id}")

        return {
            "code": 200,
            "message": "删除成功",
            "data": {"id": test_point_id}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除测试点失败: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )

