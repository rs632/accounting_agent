"""节点：load_history —— 载入历史数据用于周/月汇总。"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from accounting_agent.config import cfg_from_config
from accounting_agent.state import AgentState
from accounting_agent.tools import LedgerDB, monthly_stats, weekly_pie


def load_history_node(state: AgentState, config: RunnableConfig) -> dict:
    cfg = cfg_from_config(config)
    db = LedgerDB(cfg.db_path)
    history = db.all()
    return {
        "history": history,
        "stats": monthly_stats(history),
        "weekly_pie": weekly_pie(history),
    }
