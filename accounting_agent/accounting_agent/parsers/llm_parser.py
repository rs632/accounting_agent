"""LLM 解析器：用大模型从 OCR 文本抽取结构化账单。

兼容 OpenAI 兼容接口（DeepSeek / 各类网关）。
针对「thinking mode」模型（不支持 tool_choice / json_schema），
采用明文 JSON 输出 + 手动解析的稳健方案。
"""
from __future__ import annotations

import concurrent.futures
import json
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import httpx
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from accounting_agent.config import Config
from accounting_agent.models import ParseResult, Transaction
from accounting_agent.prompts import LLM_PARSE_SYSTEM

# DeepSeek thinking 模式会缓慢流式输出，httpx 的 read 超时按"读取间隔"计算，
# 无法覆盖总时长，因此必须用"墙钟超时"：future.result(timeout) 到点即放弃并降级规则解析。
LLM_TIMEOUT_SEC = 30
LLM_CONNECT_TIMEOUT_SEC = 15

# 全局线程池：超时后线程会滞留（socket 阻塞），限制 worker 数防止无限堆积
_llm_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm")


class _LLMTransaction(BaseModel):
    date: str = Field(description="交易日期 YYYY-MM-DD，无法确定则留空字符串")
    time: Optional[str] = Field(default=None, description="交易时间 HH:MM:SS，可选")
    amount: float = Field(description="金额。收入为正数，支出为负数")
    merchant: str = Field(default="", description="商户/交易对方名称")
    category: str = Field(default="其他", description="消费类别")
    note: Optional[str] = Field(default=None, description="备注")


class _LLMParseResult(BaseModel):
    transactions: list[_LLMTransaction] = Field(description="识别出的交易列表")
    skipped: list[str] = Field(default_factory=list, description="疑似交易但无法确定金额/日期的原始行")


def build_llm_parser(config: Config) -> OpenAI:
    """构造 OpenAI 兼容客户端（DeepSeek / 国产网关 / OpenAI 均可）。

    直接使用 openai SDK 并显式设置 httpx 超时——langchain 的 timeout 参数
    在本环境未生效会导致请求无限挂起，这里在 socket 层强制限时。
    """
    key = config.llm_api_key
    if not key:
        raise ValueError(
            f"未配置 LLM API Key：请在 config.yaml 的 llm.api_key 填写，"
            f"或设置环境变量 {config.llm_api_key_env}"
        )
    kwargs: dict = {
        "api_key": key,
        "max_retries": 1,
        "timeout": httpx.Timeout(LLM_TIMEOUT_SEC, connect=LLM_CONNECT_TIMEOUT_SEC),
    }
    base_url = config.llm_base_url.strip()
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def parse_with_llm(config: Config, ocr_text: str) -> ParseResult:
    client = build_llm_parser(config)

    def _call() -> str:
        resp = client.chat.completions.create(
            model=config.llm_model,
            temperature=0,
            messages=[
                {"role": "system", "content": LLM_PARSE_SYSTEM},
                {"role": "user", "content": f"--- OCR 文本 ---\n{ocr_text}\n\n请只输出 JSON，不要输出任何其它文字。"},
            ],
        )
        return resp.choices[0].message.content or ""

    future = _llm_pool.submit(_call)
    try:
        raw = future.result(timeout=LLM_TIMEOUT_SEC)
    except concurrent.futures.TimeoutError:
        future.cancel()
        raise TimeoutError(f"LLM 响应超时（>{LLM_TIMEOUT_SEC}s），已降级规则解析")

    data = _extract_json(raw)
    res = _LLMParseResult.model_validate(data)

    txs = []
    for t in res.transactions:
        txs.append(Transaction(
            date=t.date,
            time=t.time,
            amount=t.amount,
            merchant=t.merchant,
            category=t.category or "其他",
            note=t.note,
            raw_text=t.note,
        ))
    result = ParseResult(transactions=txs, skipped=list(res.skipped or []))
    result.transactions.sort(key=lambda t: (t.date, t.time or ""))
    return result


def _extract_json(text: str) -> dict:
    """从模型输出中稳健地取出 JSON 对象（容忍 markdown 代码块与前后噪声）。"""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fenced:
        text = fenced.group(1).strip()
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            data = json.loads(text[start:end + 1])
        else:
            raise
    # 模型可能直接返回交易数组 → 包装成标准结构
    if isinstance(data, list):
        return {"transactions": data, "skipped": []}
    if isinstance(data, dict):
        return data
    raise ValueError("模型输出不是有效的 JSON 对象")
