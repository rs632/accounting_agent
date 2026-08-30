"""节点：parse_transactions —— OCR 文本 → 结构化账单。"""
from __future__ import annotations

import threading
import time

from langchain_core.runnables import RunnableConfig

from accounting_agent.config import cfg_from_config
from accounting_agent.parsers import parse_text, parse_with_llm
from accounting_agent.state import AgentState

# LLM 熔断器：连续失败多次后暂停调用一段时间，避免每次都等超时
_llm_failures = 0
_llm_lock = threading.Lock()
_llm_disabled_until = 0.0
LLM_FAIL_THRESHOLD = 2
LLM_COOLDOWN_SEC = 120


def _llm_allowed() -> bool:
    global _llm_disabled_until
    with _llm_lock:
        if time.time() < _llm_disabled_until:
            return False
        return True


def _record_llm_failure() -> None:
    global _llm_failures, _llm_disabled_until
    with _llm_lock:
        _llm_failures += 1
        if _llm_failures >= LLM_FAIL_THRESHOLD:
            _llm_disabled_until = time.time() + LLM_COOLDOWN_SEC
            _llm_failures = 0


def _record_llm_success() -> None:
    global _llm_failures
    with _llm_lock:
        _llm_failures = 0


def parse_transactions_node(state: AgentState, config: RunnableConfig) -> dict:
    cfg = cfg_from_config(config)
    ocr_text = state["ocr_text"]
    mode = cfg.parser_mode

    if mode == "llm" and cfg.has_llm_key and _llm_allowed():
        try:
            result = parse_with_llm(cfg, ocr_text)
            _record_llm_success()
            return {
                "transactions": result.transactions,
                "skipped": result.skipped,
                "parser_used": "llm",
            }
        except Exception as e:  # noqa: BLE001
            _record_llm_failure()
            last_err = str(e)
        # LLM 失败 → 降级规则解析，保证流程可运行
        result = parse_text(ocr_text)
        return {
            "transactions": result.transactions,
            "skipped": result.skipped,
            "parser_used": "rule",
            "fallback_reason": last_err,
        }

    result = parse_text(ocr_text)
    return {
        "transactions": result.transactions,
        "skipped": result.skipped,
        "parser_used": "rule",
    }
