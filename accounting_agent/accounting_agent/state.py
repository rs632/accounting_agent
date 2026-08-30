"""LangGraph 共享状态。"""
from __future__ import annotations

from typing import TypedDict

from accounting_agent.models import MonthStats, Transaction


class AgentState(TypedDict, total=False):
    """记账 agent 的图状态。"""

    input_path: str                      # 用户输入的截图路径 / auto / adb
    image_path: str                      # 解析后的本地图片路径
    ocr_text: str                        # OCR 识别出的文本
    transactions: list[Transaction]      # 结构化账单（本次解析结果）
    history: list[Transaction]           # 历史账本（load_history 载入）
    inserted: list[Transaction]          # 本次真正入库的新记录
    duplicates: list[Transaction]        # 去重丢弃的记录
    skipped: list[str]                   # 未识别的原始行
    parser_used: str                     # llm | rule
    fallback_reason: str                 # LLM 失败降级原因
    stats: list[MonthStats]              # 月度统计
    charts: list[str]                    # 本次生成的图表 key 列表
    chart_svgs: list[tuple[str, str]]    # 按需追加的图表 (key, svg)
    pending_charts: list[str]            # 用户请求解析出的待生成图表
    report_path: str                     # 生成的报告路径
    outbox_id: int | None                # 发送记录 id
    request: str                         # 用户追加的图表/数据请求（human-in-the-loop）
    error: str | None                    # 错误信息
