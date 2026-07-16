"""用例编号统一生成服务 — CaseNumberService。

本模块提供统一的用例编号生成能力，格式: TC-{project_id:03d}-{seq:04d}。
使用 case_number_seqs 表 + SELECT ... FOR UPDATE 行级锁保证并发安全，
seq 溢出 9999 时自动扩展位数（Python f-string 天然支持）。

核心类:
    CaseNumberService: 统一编号生成服务，提供 generate / generate_batch 方法
    （sync 版本）与 generate_async / generate_batch_async 方法（async 版本）。

迁移说明:
    sync 版本保留供 test_case_generation.validate_mixin / excel_import_mixin /
    url_driven.auto_case_generator / pipelines.steps.persist 等仍在 sync 上下文
    中运行的调用方使用；新增 async 版本供 case_migration 等已迁移到 AsyncSession
    的服务调用，使用 select().with_for_update() + await db.execute() 模式。
"""
from typing import List

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.case_number_seq import CaseNumberSeq


class CaseNumberService:
    """统一用例编号生成服务。

    编号格式: TC-{project_id:03d}-{seq:04d}
    示例: TC-001-0001, TC-001-0002, ..., TC-001-10000 (溢出自动扩展)

    并发安全:
        通过 SELECT ... FOR UPDATE 对 case_number_seqs 行加排他锁，
        同一 project_id 下的编号生成串行化，杜绝重复编号。

    跳号不复用:
        current_seq 只增不减，即使用例被删除，序号也不会回退重用。
    """

    @staticmethod
    def generate(project_id: int, db: Session) -> str:
        """生成下一个用例编号。

        使用 SELECT ... FOR UPDATE 加行级锁，保证并发安全。
        若项目首次生成编号，自动创建初始记录。

        Args:
            project_id: 项目ID。
            db: 数据库会话。

        Returns:
            格式为 TC-{project_id:03d}-{seq:04d} 的用例编号。
        """
        seqRow = (
            db.query(CaseNumberSeq)
            .filter(CaseNumberSeq.project_id == project_id)
            .with_for_update()
            .first()
        )
        if seqRow is None:
            seqRow = CaseNumberSeq(project_id=project_id, current_seq=0)
            db.add(seqRow)
            db.flush()

        nextNum = seqRow.current_seq + 1
        seqRow.current_seq = nextNum
        db.flush()

        caseNo = f"TC-{project_id:03d}-{nextNum:04d}"
        logger.debug(f"生成用例编号: {caseNo}")
        return caseNo

    @staticmethod
    def generate_batch(project_id: int, count: int, db: Session) -> List[str]:
        """批量生成用例编号。

        一次加锁分配连续序号，减少锁持有时间和 flush 次数。

        Args:
            project_id: 项目ID。
            count: 需要生成的编号数量。
            db: 数据库会话。

        Returns:
            编号列表，格式均为 TC-{project_id:03d}-{seq:04d}。
        """
        if count <= 0:
            return []

        seqRow = (
            db.query(CaseNumberSeq)
            .filter(CaseNumberSeq.project_id == project_id)
            .with_for_update()
            .first()
        )
        if seqRow is None:
            seqRow = CaseNumberSeq(project_id=project_id, current_seq=0)
            db.add(seqRow)
            db.flush()

        startNum = seqRow.current_seq + 1
        seqRow.current_seq = startNum + count - 1
        db.flush()

        caseNos = [f"TC-{project_id:03d}-{startNum + i:04d}" for i in range(count)]
        logger.debug(f"批量生成用例编号: {caseNos[0]} ~ {caseNos[-1]}")
        return caseNos

    @staticmethod
    async def generate_async(project_id: int, db: AsyncSession) -> str:
        """异步生成下一个用例编号。

        使用 select(...).with_for_update() 加行级锁，保证并发安全。
        若项目首次生成编号，自动创建初始记录。

        Args:
            project_id: 项目ID。
            db: 异步数据库会话。

        Returns:
            格式为 TC-{project_id:03d}-{seq:04d} 的用例编号。
        """
        stmt = (
            select(CaseNumberSeq)
            .where(CaseNumberSeq.project_id == project_id)
            .with_for_update()
        )
        seqRow = (await db.execute(stmt)).scalar_one_or_none()
        if seqRow is None:
            seqRow = CaseNumberSeq(project_id=project_id, current_seq=0)
            db.add(seqRow)
            await db.flush()

        nextNum = seqRow.current_seq + 1
        seqRow.current_seq = nextNum
        await db.flush()

        caseNo = f"TC-{project_id:03d}-{nextNum:04d}"
        logger.debug(f"生成用例编号: {caseNo}")
        return caseNo

    @staticmethod
    async def generate_batch_async(
        project_id: int, count: int, db: AsyncSession
    ) -> List[str]:
        """异步批量生成用例编号。

        一次加锁分配连续序号，减少锁持有时间和 flush 次数。

        Args:
            project_id: 项目ID。
            count: 需要生成的编号数量。
            db: 异步数据库会话。

        Returns:
            编号列表，格式均为 TC-{project_id:03d}-{seq:04d}。
        """
        if count <= 0:
            return []

        stmt = (
            select(CaseNumberSeq)
            .where(CaseNumberSeq.project_id == project_id)
            .with_for_update()
        )
        seqRow = (await db.execute(stmt)).scalar_one_or_none()
        if seqRow is None:
            seqRow = CaseNumberSeq(project_id=project_id, current_seq=0)
            db.add(seqRow)
            await db.flush()

        startNum = seqRow.current_seq + 1
        seqRow.current_seq = startNum + count - 1
        await db.flush()

        caseNos = [f"TC-{project_id:03d}-{startNum + i:04d}" for i in range(count)]
        logger.debug(f"批量生成用例编号: {caseNos[0]} ~ {caseNos[-1]}")
        return caseNos
