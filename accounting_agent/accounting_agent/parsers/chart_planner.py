"""模型驱动的图表意图规划器。

把用户自然语言请求映射为图表 key 列表（CHART_BUILDERS 的 key）。
优先用 LLM 决策；无 Key / 非 llm 模式 / 调用失败 / 输出不合法时，
回落到 request_router.classify_request 的关键字规则。

针对 thinking 模式模型（不支持 tool_choice / json_schema），
沿用「明文 JSON + 稳健提取 + 墙钟超时」方案。
"""
from __future__ import annotations

import concurrent.futures
import json
import re

from accounting_agent.config import Config
from accounting_agent.parsers import llm_parser
from accounting_agent.prompts import CHART_PLANNING_SYSTEM
from accounting_agent.tools.request_router import classify_request

VALID_CHART_KEYS = [
    "weekly_pie",
    "weekly_income_pie",
    "monthly_pie",
    "monthly_income_pie",
    "daily_bar",
    "monthly_trend",
]
_VALID = set(VALID_CHART_KEYS)

LLM_TIMEOUT_SEC = llm_parser.LLM_TIMEOUT_SEC


def plan_charts(config: Config, text: str) -> list[str]:
    """返回用户请求对应的图表 key 列表；空列表表示无需追加（如“结束”）。"""
    text = (text or "").strip()
    if not text:
        return []

    if config.parser_mode == "llm" and config.has_llm_key:
        try:
            keys = _plan_with_llm(config, text)
            if keys is not None:
                return keys
        except Exception:  # noqa: BLE001 - 任何失败都降级规则路由
            pass

    return classify_request(text)


def _plan_with_llm(config: Config, text: str) -> list[str] | None:
    """调用 LLM 规划；返回 None 表示输出不可用，需调用方降级。"""
    client = llm_parser.build_llm_parser(config)

    def _call() -> str:
        resp = client.chat.completions.create(
            model=config.llm_model,
            temperature=0,
            messages=[
                {"role": "system", "content": CHART_PLANNING_SYSTEM},
                {"role": "user", "content": f"--- 用户请求 ---\n{text}\n\n请只输出 JSON。"},
            ],
        )
        return resp.choices[0].message.content or ""

    future = llm_parser._llm_pool.submit(_call)
    try:
        raw = future.result(timeout=LLM_TIMEOUT_SEC)
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise TimeoutError(f"图表规划 LLM 响应超时（>{LLM_TIMEOUT_SEC}s）")

    return _normalize(_extract_obj(raw))


def _normalize(data: object) -> list[str] | None:
    """把模型输出标准化为合法 key 列表；None 表示不可用（应降级）。"""
    if isinstance(data, dict):
        raw_keys = data.get("charts")
        if raw_keys is None:
            return None
    elif isinstance(data, list):
        raw_keys = data
    else:
        return None

    if isinstance(raw_keys, str):
        raw_keys = [raw_keys]
    if not isinstance(raw_keys, list):
        return None

    keys: list[str] = []
    for item in raw_keys:
        if isinstance(item, str):
            key = item.strip()
            if key in _VALID and key not in keys:
                keys.append(key)

    if raw_keys and not keys:
        # 模型给了内容但全是非法 key → 视为不可用，交给规则兜底
        return None
    return keys


def _extract_obj(text: str) -> object:
    """从模型输出中稳健取出 JSON（对象或数组，容忍代码块与前后噪声）。"""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = text.find(opener), text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError("模型输出不是有效的 JSON")
