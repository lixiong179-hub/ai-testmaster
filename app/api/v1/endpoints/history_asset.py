import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.auth import get_current_user
from app.core.exception import create_response
from app.db.database import async_get_db
from app.models.history_asset import HistoryAsset
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.history_asset import (
    HistoryAssetDetailResponse,
    HistoryAssetUploadResponse,
    HistoryClassificationItem,
    HistoryClassificationResponse,
    HistoryClassificationSummary,
)
from app.services.xmind_parser import XmindParser, XmindParseError

router = APIRouter(tags=["历史资产"])

UPLOAD_DIR = "uploads/history_assets"

_ALLOWED_ASSET_TYPES = {"excel", "xmind", "system_cases"}
_ALLOWED_EXCEL_EXTS = {".xlsx", ".xls"}
_ALLOWED_XMIND_EXTS = {".xmind"}


def _title_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_lower, b_lower = a.strip().lower(), b.strip().lower()
    if a_lower == b_lower:
        return 1.0
    a_set = set(a_lower)
    b_set = set(b_lower)
    if not a_set or not b_set:
        return 0.0
    jaccard = len(a_set & b_set) / len(a_set | b_set)
    max_len = max(len(a_lower), len(b_lower))
    if max_len == 0:
        return 0.0
    common_prefix = 0
    for i in range(min(len(a_lower), len(b_lower))):
        if a_lower[i] == b_lower[i]:
            common_prefix += 1
        else:
            break
    prefix_ratio = common_prefix / max_len
    return 0.4 * jaccard + 0.6 * prefix_ratio


def _classify_history_cases(
    history_cases: list[dict[str, Any]],
    system_cases: list[dict[str, Any]],
    requirement_keywords: list[str],
) -> list[HistoryClassificationItem]:
    results: list[HistoryClassificationItem] = []

    for idx, h_case in enumerate(history_cases):
        h_title = h_case.get("title", "")
        best_match: dict[str, Any] | None = None
        best_score = 0.0

        for s_case in system_cases:
            s_title = s_case.get("title", "")
            score = _title_similarity(h_title, s_title)
            if score > best_score:
                best_score = score
                best_match = s_case

        if best_score >= 0.9 and best_match:
            h_steps = h_case.get("steps", [])
            s_steps = best_match.get("steps", [])
            h_er = h_case.get("expected_result", "")
            s_er = best_match.get("expected_result", "")
            steps_differ = (
                len(h_steps) != len(s_steps)
                or any(
                    str(hs.get("action", "")) != str(ss.get("action", ""))
                    for hs, ss in zip(h_steps, s_steps)
                )
            )
            er_differ = h_er.strip() != s_er.strip()

            if steps_differ or er_differ:
                diff_fields: dict[str, Any] = {}
                if steps_differ:
                    diff_fields["steps"] = {"old": s_steps, "new": h_steps}
                if er_differ:
                    diff_fields["expected_result"] = {"old": s_er, "new": h_er}
                results.append(HistoryClassificationItem(
                    client_id=f"ha_case_{idx}",
                    classification="UPDATE_CASE",
                    confidence=best_score,
                    history_case=h_case,
                    suggested_case=h_case,
                    diff_fields=diff_fields,
                    reason=f"与系统用例「{best_match.get('title', '')}」标题高度匹配但内容有差异",
                    matched_system_case_id=best_match.get("case_id"),
                ))
            else:
                results.append(HistoryClassificationItem(
                    client_id=f"ha_case_{idx}",
                    classification="REUSE_CASE",
                    confidence=best_score,
                    history_case=h_case,
                    suggested_case=None,
                    diff_fields=None,
                    reason=f"与系统用例「{best_match.get('title', '')}」完全匹配，可复用",
                    matched_system_case_id=best_match.get("case_id"),
                ))
        elif best_score >= 0.5 and best_match:
            results.append(HistoryClassificationItem(
                client_id=f"ha_case_{idx}",
                classification="UPDATE_CASE",
                confidence=best_score,
                history_case=h_case,
                suggested_case=h_case,
                diff_fields={"title": {"old": best_match.get("title", ""), "new": h_title}},
                reason=f"与系统用例「{best_match.get('title', '')}」标题部分匹配，建议更新",
                matched_system_case_id=best_match.get("case_id"),
            ))
        else:
            if requirement_keywords:
                title_lower = h_title.lower()
                matched_kw = [kw for kw in requirement_keywords if kw.lower() in title_lower]
                if matched_kw:
                    results.append(HistoryClassificationItem(
                        client_id=f"ha_case_{idx}",
                        classification="NEW_CASE",
                        confidence=0.7,
                        history_case=h_case,
                        suggested_case=h_case,
                        diff_fields=None,
                        reason=f"无匹配系统用例，但标题包含需求关键词「{'、'.join(matched_kw[:3])}」，建议新增",
                    ))
                else:
                    results.append(HistoryClassificationItem(
                        client_id=f"ha_case_{idx}",
                        classification="CONFIRM_REQUIRED",
                        confidence=0.4,
                        history_case=h_case,
                        suggested_case=None,
                        diff_fields=None,
                        reason="无匹配系统用例且标题不含需求关键词，需人工确认是否新增",
                    ))
            else:
                results.append(HistoryClassificationItem(
                    client_id=f"ha_case_{idx}",
                    classification="NEW_CASE",
                    confidence=0.6,
                    history_case=h_case,
                    suggested_case=h_case,
                    diff_fields=None,
                    reason="无匹配系统用例，建议新增",
                ))

    matched_system_ids: set[int] = set()
    for item in results:
        if item.matched_system_case_id:
            matched_system_ids.add(item.matched_system_case_id)

    for s_case in system_cases:
        s_id = s_case.get("case_id")
        if s_id and s_id not in matched_system_ids:
            results.append(HistoryClassificationItem(
                client_id=f"sys_case_{s_id}",
                classification="DEPRECATED_CASE",
                confidence=0.6,
                history_case=None,
                suggested_case=None,
                diff_fields=None,
                reason=f"系统用例「{s_case.get('title', '')}」在新资料中无匹配，可能废弃",
                matched_system_case_id=s_id,
            ))

    return results


def _asset_to_upload_response(asset: HistoryAsset) -> dict:
    return HistoryAssetUploadResponse(
        id=asset.id,
        project_id=asset.project_id,
        asset_type=asset.asset_type,
        original_filename=asset.original_filename,
        parse_status=asset.parse_status,
        case_count=asset.case_count,
        created_at=asset.created_at,
    ).model_dump()


def _asset_to_detail_response(asset: HistoryAsset) -> dict:
    return HistoryAssetDetailResponse(
        id=asset.id,
        project_id=asset.project_id,
        asset_type=asset.asset_type,
        original_filename=asset.original_filename,
        parse_status=asset.parse_status,
        parse_error=asset.parse_error,
        parsed_cases=asset.parsed_cases_json or [],
        case_count=asset.case_count,
        batch_id=asset.batch_id,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    ).model_dump()


def _validate_project_permission(project_id: int, user_id: int, db: Session) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id, Project.user_id == user_id
    ).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在或无权限"
        )
    return project


def _parse_excel_cases(file_path: str) -> list[dict[str, Any]]:
    import pandas as pd

    cases: list[dict[str, Any]] = []
    try:
        xls = pd.ExcelFile(file_path)
        if "用例信息" in xls.sheet_names and "测试步骤" in xls.sheet_names:
            case_info_df = pd.read_excel(file_path, sheet_name="用例信息")
            steps_df = pd.read_excel(file_path, sheet_name="测试步骤")
            for _, info_row in case_info_df.iterrows():
                case_data = {
                    "title": str(info_row.get("用例标题", "")),
                    "module": str(info_row.get("所属模块", "")),
                    "precondition": str(info_row.get("前置条件", "")),
                    "expected_result": str(info_row.get("预期结果", "")),
                    "priority": int(info_row.get("优先级", 2)),
                    "case_row_index": int(info_row.name) if not pd.isna(info_row.name) else 0,
                    "steps": [],
                }
                cases.append(case_data)
            if cases and not steps_df.empty:
                case_by_index = {c["case_row_index"]: c for c in cases}
                for _, step_row in steps_df.iterrows():
                    step_data = {
                        "step_number": int(step_row.get("步骤编号", 1)),
                        "action": str(step_row.get("操作步骤", "")),
                        "expected_result": str(step_row.get("预期结果", "")),
                    }
                    case_idx = int(step_row.get("用例序号", step_row.get("用例行号", 0)))
                    target_case = case_by_index.get(case_idx)
                    if target_case is None and cases:
                        target_case = cases[min(case_idx, len(cases) - 1)] if case_idx < len(cases) else cases[0]
                    if target_case:
                        target_case["steps"].append(step_data)
                for c in cases:
                    c.pop("case_row_index", None)
        else:
            df = pd.read_excel(file_path, sheet_name=0)
            current_module = ""
            for _, row in df.iterrows():
                raw_step = row.get("操作步骤", row.get("步骤描述", None))
                first_col = row.iloc[0] if len(row) > 0 else None
                if pd.isna(raw_step) or str(raw_step).strip() == "":
                    if first_col is not None and not pd.isna(first_col):
                        val = str(first_col).strip()
                        if val and not val.isdigit():
                            current_module = val
                    continue
                title = str(row.get("用例描述", row.get("标题", ""))).strip()
                if not title:
                    continue
                cases.append({
                    "title": title,
                    "module": current_module,
                    "precondition": str(row.get("前置条件", "")).strip(),
                    "expected_result": str(row.get("期望结果", row.get("预期结果", ""))).strip(),
                    "priority": 2,
                    "steps": [{
                        "action": str(row.get("操作步骤", row.get("步骤描述", ""))).strip(),
                        "expected_result": str(row.get("期望结果", row.get("预期结果", ""))).strip(),
                    }],
                })
    except Exception as e:
        logger.error(f"Excel 解析失败: {e}")
        raise ValueError(f"Excel 解析失败: {e}") from e
    return cases


def _parse_xmind_cases(file_path: str) -> list[dict[str, Any]]:
    parser = XmindParser()
    try:
        raw_points = parser.parse(file_path)
    except XmindParseError as e:
        logger.error(f"XMind 解析失败: {e}")
        raise ValueError(f"XMind 解析失败: {e}") from e
    cases: list[dict[str, Any]] = []
    for point in raw_points:
        cases.append({
            "title": point.get("name", ""),
            "module": point.get("module", ""),
            "precondition": "",
            "expected_result": point.get("expected", ""),
            "priority": 2,
            "steps": point.get("steps", []),
        })
    return cases


@router.post("/upload")
async def upload_history_asset(
    project_id: int = Form(...),
    asset_type: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _check_permission(sync_db: Session) -> Project:
        return _validate_project_permission(project_id, current_user.id, sync_db)

    await db.run_sync(_check_permission)

    if asset_type not in _ALLOWED_ASSET_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的资产类型: {asset_type}，允许: {', '.join(sorted(_ALLOWED_ASSET_TYPES))}",
        )

    filename = file.filename or "unknown"
    _, ext = os.path.splitext(filename)
    ext = ext.lower()

    if asset_type == "excel" and ext not in _ALLOWED_EXCEL_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Excel 资产仅支持: {', '.join(sorted(_ALLOWED_EXCEL_EXTS))}",
        )
    if asset_type == "xmind" and ext not in _ALLOWED_XMIND_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"XMind 资产仅支持: {', '.join(sorted(_ALLOWED_XMIND_EXTS))}",
        )

    upload_dir = os.path.join(UPLOAD_DIR, str(project_id))
    os.makedirs(upload_dir, exist_ok=True)
    unique_name = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, unique_name)

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    parsed_cases: list[dict[str, Any]] = []
    parse_error = None
    parse_status = "completed"

    try:
        if asset_type == "excel":
            parsed_cases = _parse_excel_cases(file_path)
        elif asset_type == "xmind":
            parsed_cases = _parse_xmind_cases(file_path)
    except ValueError as e:
        parse_status = "failed"
        parse_error = str(e)[:500]
        logger.warning(f"历史资产解析失败: {e}")

    final_parse_status = parse_status
    final_parse_error = parse_error
    final_parsed_cases = parsed_cases if parse_status == "completed" else None
    final_case_count = len(parsed_cases) if parse_status == "completed" else 0

    def _create_asset(sync_db: Session) -> HistoryAsset:
        asset = HistoryAsset(
            project_id=project_id,
            user_id=current_user.id,
            asset_type=asset_type,
            file_path=file_path,
            original_filename=filename,
            parse_status=final_parse_status,
            parse_error=final_parse_error,
            parsed_cases_json=final_parsed_cases,
            case_count=final_case_count,
        )
        sync_db.add(asset)
        sync_db.commit()
        sync_db.refresh(asset)
        return asset

    asset = await db.run_sync(_create_asset)

    return create_response(data=_asset_to_upload_response(asset))


@router.get("")
async def list_history_assets(
    project_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _list(sync_db: Session) -> list:
        _validate_project_permission(project_id, current_user.id, sync_db)
        return (
            sync_db.query(HistoryAsset)
            .filter(HistoryAsset.project_id == project_id)
            .order_by(HistoryAsset.created_at.desc())
            .all()
        )

    assets = await db.run_sync(_list)
    items = [_asset_to_upload_response(a) for a in assets]
    return create_response(data=items)


@router.post("/align")
async def align_history_assets(
    project_id: int = Form(...),
    history_asset_ids: str = Form(...),
    requirement_file_ids: str | None = Form(None),
    test_point_ids: str | None = Form(None),
    ui_screen_ids: str | None = Form(None),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    import json

    try:
        asset_ids = json.loads(history_asset_ids)
        req_file_ids = json.loads(requirement_file_ids) if requirement_file_ids else None
        tp_ids = json.loads(test_point_ids) if test_point_ids else None
        ui_ids = json.loads(ui_screen_ids) if ui_screen_ids else None
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"参数 JSON 解析失败: {e}",
        ) from e

    def _align(sync_db: Session) -> dict:
        _validate_project_permission(project_id, current_user.id, sync_db)

        assets = (
            sync_db.query(HistoryAsset)
            .filter(
                HistoryAsset.id.in_(asset_ids),
                HistoryAsset.project_id == project_id,
            )
            .all()
        )
        if len(assets) != len(asset_ids):
            found_ids = {a.id for a in assets}
            missing = set(asset_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"以下历史资产不存在或不属于当前项目: {sorted(missing)}",
            )

        all_cases: list[dict[str, Any]] = []
        for asset in assets:
            if asset.parsed_cases_json:
                all_cases.extend(asset.parsed_cases_json)

        system_cases_query = (
            sync_db.query(TestCase)
            .filter(
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
            )
            .all()
        )
        system_cases: list[dict[str, Any]] = []
        for sc in system_cases_query:
            system_cases.append({
                "case_id": sc.id,
                "title": sc.title,
                "module": sc.module,
                "precondition": sc.precondition,
                "steps": sc.steps_json or [],
                "expected_result": sc.expected_result,
                "priority": sc.priority,
            })

        requirement_keywords: list[str] = []
        if req_file_ids:
            from app.models.project import ProjectFile
            req_files = sync_db.query(ProjectFile).filter(
                ProjectFile.id.in_(req_file_ids),
                ProjectFile.project_id == project_id,
            ).all()
            for rf in req_files:
                if rf.original_filename:
                    name = os.path.splitext(rf.original_filename)[0]
                    requirement_keywords.extend(name.replace("_", " ").replace("-", " ").split())

        classification_items = _classify_history_cases(all_cases, system_cases, requirement_keywords)

        summary = HistoryClassificationSummary(
            reuse_count=sum(1 for i in classification_items if i.classification == "REUSE_CASE"),
            update_count=sum(1 for i in classification_items if i.classification == "UPDATE_CASE"),
            new_count=sum(1 for i in classification_items if i.classification == "NEW_CASE"),
            deprecated_count=sum(1 for i in classification_items if i.classification == "DEPRECATED_CASE"),
            confirm_required_count=sum(1 for i in classification_items if i.classification == "CONFIRM_REQUIRED"),
            total=len(classification_items),
        )

        result = HistoryClassificationResponse(summary=summary, items=classification_items)
        return result.model_dump()

    result_data = await db.run_sync(_align)
    return create_response(data=result_data)


@router.post("/import-system-cases")
async def import_system_cases(
    project_id: int = Form(...),
    case_ids: str = Form(...),
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    import json

    try:
        parsed_case_ids = json.loads(case_ids)
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"case_ids JSON 解析失败: {e}",
        ) from e

    def _import(sync_db: Session) -> HistoryAsset:
        _validate_project_permission(project_id, current_user.id, sync_db)

        cases = (
            sync_db.query(TestCase)
            .filter(
                TestCase.id.in_(parsed_case_ids),
                TestCase.project_id == project_id,
                TestCase.is_deleted.is_(False),
            )
            .all()
        )
        if len(cases) != len(parsed_case_ids):
            found_ids = {c.id for c in cases}
            missing = set(parsed_case_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"以下用例不存在或不属于当前项目: {sorted(missing)}",
            )

        parsed_cases: list[dict[str, Any]] = []
        for case in cases:
            parsed_cases.append({
                "case_id": case.id,
                "case_no": case.case_no,
                "title": case.title,
                "module": case.module,
                "precondition": case.precondition,
                "steps": case.steps_json or [],
                "expected_result": case.expected_result,
                "priority": case.priority,
                "case_type": case.case_type,
            })

        asset = HistoryAsset(
            project_id=project_id,
            user_id=current_user.id,
            asset_type="system_cases",
            file_path=None,
            original_filename=None,
            parse_status="completed",
            parsed_cases_json=parsed_cases,
            case_count=len(parsed_cases),
        )
        sync_db.add(asset)
        sync_db.commit()
        sync_db.refresh(asset)
        return asset

    asset = await db.run_sync(_import)

    return create_response(data=_asset_to_upload_response(asset))


@router.get("/{asset_id}")
async def get_history_asset(
    asset_id: int,
    db: AsyncSession = Depends(async_get_db),
    current_user: User = Depends(get_current_user),
):
    def _get(sync_db: Session) -> HistoryAsset:
        asset = sync_db.query(HistoryAsset).filter(HistoryAsset.id == asset_id).first()
        if not asset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="历史资产不存在"
            )
        if asset.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="无权限访问此历史资产"
            )
        return asset

    asset = await db.run_sync(_get)
    return create_response(data=_asset_to_detail_response(asset))
