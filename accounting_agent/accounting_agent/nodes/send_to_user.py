"""节点：send_to_user —— 组装 HTML 报告、自动打开、记录 outbox。"""
from __future__ import annotations

import os
import webbrowser

from langchain_core.runnables import RunnableConfig

from accounting_agent.config import cfg_from_config
from accounting_agent.nodes.generate_chart import CORE_CHARTS
from accounting_agent.state import AgentState
from accounting_agent.tools import Outbox, build_report


def send_to_user_node(state: AgentState, config: RunnableConfig) -> dict:
    cfg = cfg_from_config(config)
    all_txs = list(state.get("transactions", [])) + list(state.get("history", []))
    charts = [k for k in dict.fromkeys(state.get("charts", []))]
    extra = [k for k in charts if k not in CORE_CHARTS]

    report_path = build_report(
        cfg,
        all_txs,
        inserted=state.get("inserted"),
        duplicates=state.get("duplicates"),
        extra_charts=extra,
    )

    summary = (f"共 {len(all_txs)} 笔 · 本次入库 {len(state.get('inserted', []))} 笔 · "
               f"生成图表 {len(charts)} 张")
    outbox_id = Outbox(cfg.db_path).record(report_path, charts, summary)

    if cfg.open_after:
        try:
            webbrowser.open(f"file://{os.path.abspath(report_path)}")
        except Exception:
            pass

    return {"report_path": report_path, "outbox_id": outbox_id}
