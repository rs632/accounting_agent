"""节点：ask_more —— human-in-the-loop，等用户追加图表/数据需求。

通过 LangGraph interrupt() 暂停工作流，等待用户以 resume 方式回复；
收到新请求则路由到 generate_chart 按需生成，否则流程结束。
"""
from __future__ import annotations

from langgraph.types import interrupt

from accounting_agent.state import AgentState
from accounting_agent.tools.request_router import classify_request

ASK_MORE_QUESTION = (
    "账本与报告已处理完毕。是否需要追加图表或数据？例如：\n"
    "  · 本周微信消费分类饼图\n"
    "  · 近 3 个月收支趋势\n"
    "  · 消费集中在哪几天\n"
    "  · 各商户消费 Top10\n"
    "回复「没有」即可结束。"
)


def ask_more_node(state: AgentState) -> dict:
    answer = interrupt({
        "type": "ask_more",
        "question": ASK_MORE_QUESTION,
        "accepted": True,
    })
    text = str(answer).strip()
    keys = classify_request(text)
    if not keys:
        return {"request": text, "pending_charts": []}
    return {"request": text, "pending_charts": keys}


def route_after_ask_more(state: AgentState) -> str:
    """根据 ask_more 结果决定继续生成图表还是结束。"""
    if state.get("pending_charts"):
        return "generate_chart"
    return "__end__"
