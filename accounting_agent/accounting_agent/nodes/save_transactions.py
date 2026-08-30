"""节点：save_transactions —— 存入本地历史（SQLite 自动去重）。"""
from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from accounting_agent.config import cfg_from_config
from accounting_agent.state import AgentState
from accounting_agent.tools import LedgerDB


def save_transactions_node(state: AgentState, config: RunnableConfig) -> dict:
    cfg = cfg_from_config(config)
    txs = state.get("transactions", [])
    if not txs:
        return {"inserted": [], "duplicates": []}
    db = LedgerDB(cfg.db_path)
    inserted, duplicates = db.insert_many(txs)
    db.export_csv(cfg.csv_path)
    return {"inserted": inserted, "duplicates": duplicates}
