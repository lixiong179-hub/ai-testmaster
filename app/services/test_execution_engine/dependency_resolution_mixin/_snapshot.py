from typing import Any, Dict, List, Optional
from loguru import logger

from app.models.test_case import TestCase


class _SnapshotMixin:

    async def _save_anchor_snapshot(
        self, case: TestCase, anchor_step: int
    ) -> bool:
        is_mobile = getattr(self, '_mobile_device_id', None) is not None

        if is_mobile:
            return await self._save_mobile_snapshot(case, anchor_step)
        return await self._save_web_snapshot(case, anchor_step)

    async def _save_web_snapshot(
        self, case: TestCase, anchor_step: int
    ) -> bool:
        if not self.browser or not getattr(self.browser, '_page', None):
            logger.warning("浏览器未初始化，无法保存Web快照")
            return False

        try:
            page = self.browser._page
            context = getattr(self.browser, '_context', None)
            snapshot: Dict[str, Any] = {
                "type": "web",
                "url": page.url,
                "anchor_step": anchor_step,
                "case_title": case.title,
            }

            if context:
                storage_state = await context.storage_state()
                snapshot["storage_state"] = storage_state

            snapshot_key = f"{case.title}_{anchor_step}"
            self._anchor_snapshots[snapshot_key] = snapshot
            logger.info(f"Web快照已保存: key={snapshot_key}, url={page.url}")
            return True

        except Exception as e:
            logger.warning(f"Web快照保存失败: {e}")
            return False

    async def _save_mobile_snapshot(
        self, case: TestCase, anchor_step: int
    ) -> bool:
        mobile_executor = getattr(self, '_mobile_executor', None)
        if not mobile_executor:
            logger.warning("移动端执行器未初始化，无法保存Mobile快照")
            return False

        adb = getattr(mobile_executor, 'adb', None)
        if not adb:
            logger.warning("ADB控制器未初始化，无法保存Mobile快照")
            return False

        try:
            current_activity = await adb.get_current_activity()
            ui_summary = await self._capture_mobile_ui_summary(mobile_executor)
            screenshot_hash = await self._capture_screenshot_hash(adb)

            snapshot: Dict[str, Any] = {
                "type": "mobile",
                "current_activity": current_activity,
                "ui_element_summary": ui_summary,
                "screenshot_hash": screenshot_hash,
                "anchor_step": anchor_step,
                "case_title": case.title,
            }

            project = getattr(self, '_current_project', None)
            if project:
                snapshot["app_package"] = getattr(project, 'test_object_app_package', None)
                snapshot["app_activity"] = getattr(project, 'test_object_app_activity', None)

            snapshot_key = f"{case.title}_{anchor_step}"
            self._anchor_snapshots[snapshot_key] = snapshot
            logger.info(
                f"Mobile快照已保存: key={snapshot_key}, "
                f"activity={current_activity}"
            )
            return True

        except Exception as e:
            logger.warning(f"Mobile快照保存失败: {e}")
            return False

    async def _capture_mobile_ui_summary(
        self, mobile_executor: Any
    ) -> List[Dict[str, str]]:
        try:
            uiautomator = getattr(mobile_executor, 'uiautomator', None)
            if not uiautomator:
                return []

            elements = await uiautomator.get_clickable_elements()
            summary = []
            for elem in elements[:20]:
                item: Dict[str, str] = {}
                if elem.resource_id:
                    item["resource_id"] = elem.resource_id
                if elem.text:
                    item["text"] = elem.text
                if elem.content_desc:
                    item["content_desc"] = elem.content_desc
                if item:
                    summary.append(item)

            return summary

        except Exception:
            return []

    async def _capture_screenshot_hash(self, adb: Any) -> Optional[str]:
        try:
            import hashlib
            screenshot_bytes = await adb.take_screenshot()
            if screenshot_bytes:
                return hashlib.md5(screenshot_bytes).hexdigest()
        except Exception:
            pass
        return None

    async def _restore_anchor_snapshot(
        self, case: TestCase
    ) -> bool:
        depends_on = getattr(case, 'depends_on', None)
        anchor_step = getattr(case, 'anchor_step', None)
        if not depends_on or anchor_step is None:
            return False

        snapshot_key = f"{depends_on}_{anchor_step}"
        snapshot = self._anchor_snapshots.get(snapshot_key)
        if not snapshot:
            logger.info(f"快照不存在: key={snapshot_key}，将尝试降级导航")
            return False

        snapshot_type = snapshot.get("type", "web")
        if snapshot_type == "mobile":
            return await self._restore_mobile_snapshot(snapshot)
        return await self._restore_web_snapshot(snapshot)

    async def _restore_web_snapshot(
        self, snapshot: Dict[str, Any]
    ) -> bool:
        if not self.browser or not getattr(self.browser, '_page', None):
            logger.warning("浏览器未初始化，无法恢复Web快照")
            return False

        try:
            page = self.browser._page
            context = getattr(self.browser, '_context', None)

            target_url = snapshot.get("url", "")
            if not target_url:
                logger.warning("Web快照中无有效URL")
                return False

            await page.goto(target_url, wait_until="networkidle")

            storage_state = snapshot.get("storage_state")
            if storage_state and context:
                browser_cookies = storage_state.get("cookies", [])
                if browser_cookies:
                    await context.add_cookies(browser_cookies)

                origins = storage_state.get("origins", [])
                for origin_entry in origins:
                    local_storage = origin_entry.get("localStorage", [])
                    for item in local_storage:
                        name = item.get("name", "")
                        value = item.get("value", "")
                        await page.evaluate(
                            "([n, v]) => localStorage.setItem(n, v)",
                            [name, value],
                        )

            logger.info(f"Web快照恢复成功: url={target_url}")
            return True

        except Exception as e:
            logger.warning(f"Web快照恢复失败: {e}，将尝试降级导航")
            return False

    async def _restore_mobile_snapshot(
        self, snapshot: Dict[str, Any]
    ) -> bool:
        mobile_executor = getattr(self, '_mobile_executor', None)
        if not mobile_executor:
            logger.warning("移动端执行器未初始化，无法恢复Mobile快照")
            return False

        adb = getattr(mobile_executor, 'adb', None)
        if not adb:
            logger.warning("ADB控制器未初始化，无法恢复Mobile快照")
            return False

        try:
            target_activity = snapshot.get("current_activity")
            if not target_activity:
                logger.warning("Mobile快照中无Activity信息")
                return False

            current_activity = await adb.get_current_activity()

            if current_activity and target_activity in (current_activity or ""):
                logger.info(f"已在目标Activity: {current_activity}")
                ui_match = await self._verify_mobile_ui(snapshot, mobile_executor)
                if ui_match:
                    return True
                logger.info("Activity匹配但UI不匹配，可能需要重新导航")

            app_package = snapshot.get("app_package")
            if app_package and "/" in target_activity:
                activity_name = target_activity.split("/")[1] if "/" in target_activity else target_activity
                try:
                    await adb.start_app(app_package, activity_name)
                    logger.info(f"已导航到Activity: {target_activity}")
                except Exception as e:
                    logger.warning(f"Activity导航失败: {e}")
                    return False

                import asyncio
                await asyncio.sleep(1.0)

                ui_match = await self._verify_mobile_ui(snapshot, mobile_executor)
                if ui_match:
                    return True

                logger.info("Activity导航后UI不匹配，快照恢复失败")
                return False

            logger.warning(f"Mobile快照缺少app_package，无法导航: {target_activity}")
            return False

        except Exception as e:
            logger.warning(f"Mobile快照恢复失败: {e}")
            return False

    async def _verify_mobile_ui(
        self,
        snapshot: Dict[str, Any],
        mobile_executor: Any,
    ) -> bool:
        expected_elements = snapshot.get("ui_element_summary", [])
        if not expected_elements:
            return True

        try:
            uiautomator = getattr(mobile_executor, 'uiautomator', None)
            if not uiautomator:
                return True

            current_elements = await uiautomator.get_clickable_elements()
            if not current_elements:
                return False

            matched = 0
            for expected in expected_elements:
                for current in current_elements:
                    if self._element_matches(expected, current):
                        matched += 1
                        break

            match_ratio = matched / len(expected_elements) if expected_elements else 0
            logger.info(
                f"UI元素匹配: {matched}/{len(expected_elements)} "
                f"({match_ratio:.0%})"
            )
            return match_ratio >= 0.5

        except Exception:
            return False

    @staticmethod
    def _element_matches(
        expected: Dict[str, str], current: Any
    ) -> bool:
        match_count = 0
        total_fields = 0
        if expected.get("resource_id") and current.resource_id:
            total_fields += 1
            if expected["resource_id"] == current.resource_id:
                match_count += 1
        if expected.get("text") and current.text:
            total_fields += 1
            if expected["text"] == current.text:
                match_count += 1
        if expected.get("content_desc") and current.content_desc:
            total_fields += 1
            if expected["content_desc"] == current.content_desc:
                match_count += 1
        if total_fields >= 2:
            return match_count >= 2
        return match_count == total_fields and total_fields > 0
