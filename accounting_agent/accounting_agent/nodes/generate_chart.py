"""节点：generate_chart —— 生成图表（核心三类 + 按需追加）。

核心图表（每次都会生成）：
  本周支出/收入分类占比【饼图·含具体数值】、本月支出/收入分类占比【饼图】、
  本月每日消费【柱状图】
按需追加：根据 user 请求（ask_more → pending_charts）生成对应图表。
"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from accounting_agent.config import cfg_from_config
from accounting_agent.state import AgentState
from accounting_agent.tools import CHART_BUILDERS

CORE_CHARTS = ["weekly_pie", "weekly_income_pie", "monthly_pie", "monthly_income_pie", "daily_bar"]


def generate_chart_node(state: AgentState, config: RunnableConfig) -> dict:
    cfg = cfg_from_config(config)
    all_txs = list(state.get("transactions", [])) + list(state.get("history", []))

    # 追加模式：只生成请求的图表
    if state.get("pending_charts"):
        keys = [k for k in state["pending_charts"] if k in CHART_BUILDERS]
        svgs = [(key, CHART_BUILDERS[key](cfg, all_txs)) for key in keys]
        charts = list(dict.fromkeys(state.get("charts", []) + keys))
        return {"chart_svgs": state.get("chart_svgs", []) + svgs, "charts": charts}

    # 首次：生成核心图表
    svgs = [(key, CHART_BUILDERS[key](cfg, all_txs)) for key in CORE_CHARTS if key in CHART_BUILDERS]
    return {"charts": list(CORE_CHARTS), "chart_svgs": svgs}
