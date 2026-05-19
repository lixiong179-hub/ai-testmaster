from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from loguru import logger
from openai import OpenAI

from app.core.config import settings
from app.services.xmind_ai_parser._prompts import SYSTEM_PROMPT, _build_user_prompt
from app.services.xmind_ai_parser._parsing import _parse_ai_response, _normalize_case
from app.utils.ai_client_core import AITimeoutError, _detect_ai_error

BATCH_SIZE = 10
DEFAULT_AI_TIMEOUT = 90
DEFAULT_MAX_WORKERS = 4
DEFAULT_MAX_TOKENS = 8192


class XmindAIParser:

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        batch_size: Optional[int] = None,
        timeout: Optional[int] = None,
        max_workers: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.DEEPSEEK_API_KEY
        self._base_url = base_url if base_url is not None else "https://api.deepseek.com"
        self._model = model if model is not None else settings.DEEPSEEK_MODEL
        self._batch_size = (
            batch_size if batch_size is not None
            else getattr(settings, "XMIND_AI_BATCH_SIZE", BATCH_SIZE)
        )
        self._timeout = (
            timeout if timeout is not None
            else getattr(settings, "XMIND_AI_TIMEOUT", DEFAULT_AI_TIMEOUT)
        )
        self._max_workers = (
            max_workers if max_workers is not None
            else getattr(settings, "XMIND_AI_MAX_WORKERS", DEFAULT_MAX_WORKERS)
        )
        self._max_tokens = (
            max_tokens if max_tokens is not None
            else getattr(settings, "XMIND_AI_MAX_TOKENS", DEFAULT_MAX_TOKENS)
        )

        if self._batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {self._batch_size}")
        if self._timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self._timeout}")
        if self._max_workers <= 0:
            raise ValueError(f"max_workers must be positive, got {self._max_workers}")
        if self._max_tokens <= 0:
            raise ValueError(f"max_tokens must be positive, got {self._max_tokens}")
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    def parse_paths(
        self,
        paths: List[List[str]],
        progress_callback: Optional[Callable[[int, int, int, int], None]] = None,
    ) -> List[Dict[str, Any]]:
        if not paths:
            return []

        batches: List[tuple] = []
        for batch_start in range(0, len(paths), self._batch_size):
            batch = paths[batch_start : batch_start + self._batch_size]
            batches.append((batch_start, batch))

        worker_count = min(self._max_workers, len(batches))
        logger.info(
            f"AI 增强解析开始：{len(paths)} 条路径，{len(batches)} 批，"
            f"并发 {worker_count}，单批超时 {self._timeout}s"
        )

        overall_start = time.perf_counter()
        results_by_index: Dict[int, List[Dict[str, Any]]] = {}
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_meta = {
                executor.submit(self._call_ai, batch): (idx, batch_start, batch)
                for idx, (batch_start, batch) in enumerate(batches)
            }
            for future in as_completed(future_to_meta):
                idx, batch_start, batch = future_to_meta[future]
                try:
                    batch_results = future.result()
                except Exception as exc:
                    logger.error(
                        f"AI 批次 {batch_start}-{batch_start + len(batch)} "
                        f"线程异常: {exc}"
                    )
                    batch_results = None

                normalized: List[Dict[str, Any]] = []
                if batch_results is not None:
                    if len(batch_results) != len(batch):
                        logger.warning(
                            f"AI 批次 {batch_start}-{batch_start + len(batch)} "
                            f"返回 {len(batch_results)} 条，按可用结果导入"
                        )
                    for raw, path in zip(batch_results, batch):
                        fallback_module = path[0] if path else ""
                        normalized.append(_normalize_case(raw, fallback_module))
                else:
                    logger.warning(
                        f"AI 批次 {batch_start}-{batch_start + len(batch)} 失败，跳过"
                    )
                results_by_index[idx] = normalized

                if progress_callback:
                    completed_batches = len(results_by_index)
                    completed_paths = sum(
                        len(results_by_index.get(i, [])) for i in range(len(batches))
                    )
                    progress_callback(
                        completed_batches, len(batches), completed_paths, len(paths)
                    )

        all_results: List[Dict[str, Any]] = []
        for idx in range(len(batches)):
            all_results.extend(results_by_index.get(idx, []))

        elapsed = time.perf_counter() - overall_start
        logger.info(
            f"AI 增强解析完成，成功 {len(all_results)}/{len(paths)} 条，"
            f"总耗时 {elapsed:.1f}s"
        )
        return all_results

    def _call_ai(self, batch: List[List[str]]) -> Optional[List[Dict[str, Any]]]:
        user_prompt = _build_user_prompt(batch)
        start = time.perf_counter()
        try:
            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                max_tokens=self._max_tokens,
                response_format={"type": "json_object"},
            )
            elapsed = time.perf_counter() - start
            content = response.choices[0].message.content or ""
            finish_reason = getattr(response.choices[0], "finish_reason", "")
            logger.debug(
                f"AI 批次返回：长度 {len(content)} 字符，耗时 {elapsed:.1f}s，"
                f"finish_reason={finish_reason}"
            )
            if not content.strip():
                logger.warning(
                    f"AI 响应内容为空，finish_reason={finish_reason}，耗时 {elapsed:.1f}s"
                )
                return None
            if finish_reason == "length":
                logger.warning(
                    "AI 响应被 max_tokens 截断，建议调大 XMIND_AI_MAX_TOKENS 或减小 XMIND_AI_BATCH_SIZE"
                )
            return _parse_ai_response(content, len(batch))
        except Exception as exc:
            elapsed = time.perf_counter() - start
            ai_error = _detect_ai_error(exc)
            if isinstance(ai_error, AITimeoutError):
                logger.warning(f"AI 调用超时（{self._timeout}秒），耗时 {elapsed:.1f}s: {exc}")
            else:
                logger.error(f"AI 调用失败，耗时 {elapsed:.1f}s: {exc}")
            return None
