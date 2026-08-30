"""用户追加图表/数据需求的意图路由。

纯关键字路由（离线可用）；若配置了 LLM，可先用 LLM 兜底增强。
"""
from __future__ import annotations

import re

from accounting_agent.prompts import CHART_REQUEST_TYPES

_ALL_KEYS = list(CHART_REQUEST_TYPES.keys()) + [
    "weekly_income_pie", "monthly_income_pie",
]

# (正则, key, 收入/支出匹配是否需要命中"收入")
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"本周|这个星期|近7天|最近7天|这周"), "weekly", ""),
    (re.compile(r"本月|这个月|月度|当月|近30天"), "monthly", ""),
    (re.compile(r"日|天|哪几天|每天|每日|柱状"), "daily", ""),
    (re.compile(r"趋势|近\d+\s*个?月|折线|对比|走势"), "trend", ""),
]
_INCOME_HINT = re.compile(r"收入|赚|进账|入账")
_EXPENSE_HINT = re.compile(r"支出|消费|花|付|开销")
_PIE_HINT = re.compile(r"饼|占比|分类|比例|构成")
_BAR_HINT = re.compile(r"柱|哪几天|每天|每日")
_DONE_HINT = re.compile(r"没有|不需要|不用|够了|完事|结束|停止|quit|done|exit", re.I)


def classify_request(text: str) -> list[str]:
    """把用户的自然语言请求映射为一个或多个图表 key。空列表 = 无有效请求。"""
    if _DONE_HINT.search(text):
        return []
    if "收入" in text or "赚" in text or "进账" in text:
        only_income = True
    elif "支出" in text or "消费" in text or "花" in text or "付" in text:
        only_income = False
    else:
        only_income = None

    want_pie = bool(_PIE_HINT.search(text))
    want_bar = bool(_BAR_HINT.search(text))
    want_trend = bool(_TREND_MATCH(text))

    keys: list[str] = []
    if want_trend:
        keys.append("monthly_trend")
        return keys
    if want_pie:
        keys.append("monthly_pie" if "月" in text or "monthly" in text.lower() else "weekly_pie")
    if want_bar:
        keys.append("daily_bar")
    if not keys:
        # 没有任何明确图表类型：默认按时间维度给一个最相关的
        if "周" in text:
            keys.append("weekly_pie")
        elif "月" in text:
            keys.append("monthly_pie")
        else:
            keys.append("daily_bar")
    return keys


def _TREND_MATCH(text: str) -> bool:
    return bool(re.search(r"趋势|近\d+\s*个?月|折线|走势", text))
