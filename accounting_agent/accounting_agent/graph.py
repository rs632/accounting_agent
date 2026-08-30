"""LangGraph 工作流组装。

流程（对应需求）：
  capture_screen → ocr_image → parse_transactions → load_history
  → generate_chart → save_transactions → send_to_user → ask_more
  → (human-in-the-loop) 按需 generate_chart → send_to_user → ask_more ... → END
"""
from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from accounting_agent.config import thread_config

from accounting_agent.nodes import (
    ask_more_node,
    capture_screen_node,
    generate_chart_node,
    load_history_node,
    ocr_image_node,
    parse_transactions_node,
    route_after_ask_more,
    save_transactions_node,
    send_to_user_node,
)
from accounting_agent.state import AgentState

DEFAULT_THREAD_ID = "accounting-session"


def build_graph(checkpointer=None, entry: str = "capture"):
    """组装并编译图。checkpointer 缺省用内存版（支持 interrupt）。

    entry: "capture" 完整流水线（截图→OCR→解析→…）
           "ocr"     跳过截图/OCR，直接解析（state 需预置 ocr_text，用于录屏视频）
    """
    g = StateGraph(AgentState)

    g.add_node("capture_screen", capture_screen_node)
    g.add_node("ocr_image", ocr_image_node)
    g.add_node("parse_transactions", parse_transactions_node)
    g.add_node("load_history", load_history_node)
    g.add_node("generate_chart", generate_chart_node)
    g.add_node("save_transactions", save_transactions_node)
    g.add_node("send_to_user", send_to_user_node)
    g.add_node("ask_more", ask_more_node)

    if entry == "ocr":
        g.set_entry_point("parse_transactions")
    else:
        g.set_entry_point("capture_screen")
        g.add_edge("capture_screen", "ocr_image")
    g.add_edge("ocr_image", "parse_transactions")
    g.add_edge("parse_transactions", "load_history")
    g.add_edge("load_history", "generate_chart")
    g.add_edge("generate_chart", "save_transactions")
    g.add_edge("save_transactions", "send_to_user")
    g.add_edge("send_to_user", "ask_more")
    g.add_conditional_edges(
        "ask_more",
        route_after_ask_more,
        {"generate_chart": "generate_chart", END: END},
    )

    checkpointer = checkpointer or MemorySaver(
        serde=JsonPlusSerializer(allowed_msgpack_modules=[
            ("accounting_agent.models", "Transaction"),
            ("accounting_agent.models", "MonthStats"),
        ])
    )
    return g.compile(checkpointer=checkpointer)


def run_pipeline(config, input_path: str = "auto", thread_id: str = DEFAULT_THREAD_ID,
                 ocr_text: str | None = None, progress=None) -> dict:
    """非交互式跑完整个流程（自动结束 ask_more），返回最终状态。

    视频/录屏场景：先自行抽帧 + OCR，再通过 ocr_text 从 parse 节点进入。
    progress: 可选回调 progress(stage: str)，用于向前端反馈当前阶段。
    """
    graph = build_graph(entry="ocr" if ocr_text is not None else "capture")
    thread = thread_config(config, thread_id)
    initial = {"ocr_text": ocr_text} if ocr_text is not None else {"input_path": input_path}

    def _emit(node: str) -> None:
        if progress:
            progress(_NODE_STAGE.get(node, node))

    for event in graph.stream(initial, config=thread, stream_mode="updates"):
        for node in event:
            _emit(node)
    # 自动结束 human-in-the-loop
    while True:
        snap = graph.get_state(thread)
        tasks = snap.tasks
        if not (tasks and getattr(tasks[0], "interrupts", None)):
            break
        for event in graph.stream(Command(resume="没有，结束"), config=thread, stream_mode="updates"):
            for node in event:
                _emit(node)
    return graph.get_state(thread).values


_NODE_STAGE = {
    "capture_screen": "获取截图",
    "ocr_image": "OCR 识别文本",
    "parse_transactions": "解析结构化账单",
    "load_history": "载入历史账本",
    "generate_chart": "生成统计图表",
    "save_transactions": "写入账本",
    "send_to_user": "生成报告",
}
