"""端到端工作流测试：mock OCR + 规则解析 + 入库 + 报告 + human-in-the-loop。"""
import pytest

from accounting_agent.config import load_config, thread_config


def _setup_config(tmp_path) -> tuple:
    """返回 (config, thread)。把数据/OCR/解析切到测试模式。"""
    config = load_config()
    data_dir = tmp_path / "data"
    config._raw["storage"]["db_path"] = str(data_dir / "ledger.db")
    config._raw["storage"]["csv_path"] = str(data_dir / "ledger.csv")
    config._raw["report"]["dir"] = str(data_dir / "reports")
    config._raw["parser"]["mode"] = "rule"
    config._raw["ocr"]["engine"] = "mock"
    config._raw["report"]["open_after"] = False
    return config, thread_config(config, "test-run")


def _make_mock_image(tmp_path, text: str) -> str:
    img = tmp_path / "screenshots" / "demo.png"
    img.parent.mkdir(parents=True)
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)  # 假 PNG
    img.with_suffix(".txt").write_text(text, encoding="utf-8")
    return str(img)


def test_graph_end_to_end(tmp_path):
    from langgraph.types import Command
    from accounting_agent.graph import build_graph
    from accounting_agent.state import AgentState

    config, thread = _setup_config(tmp_path)
    img = _make_mock_image(tmp_path, "2025-06-05 12:30  -45.00  美团外卖\n2025-06-06 08:00  +12000.00  工资发放\n")

    graph = build_graph()
    state: AgentState = {"input_path": img}
    events = list(graph.stream(state, config=thread, stream_mode="updates"))
    nodes = [n for e in events for n in e]
    assert "__interrupt__" in nodes, f"应执行到 ask_more (interrupt)，实际: {nodes}"

    snap = graph.get_state(thread)
    assert snap.tasks and snap.tasks[0].interrupts

    # 结束（无追加需求）
    events2 = list(graph.stream(Command(resume="没有，结束"), config=thread, stream_mode="updates"))
    assert events2

    final = graph.get_state(thread).values
    assert len(final.get("inserted", [])) == 2
    assert final.get("report_path"), "应生成 HTML 报告"
    assert (tmp_path / "data" / "ledger.db").exists()
    assert (tmp_path / "data" / "ledger.csv").exists()
    assert (tmp_path / "data" / "reports").is_dir()


def test_ondemand_chart_loop(tmp_path):
    from langgraph.types import Command
    from accounting_agent.graph import build_graph
    from accounting_agent.state import AgentState

    config, thread = _setup_config(tmp_path)
    img = _make_mock_image(tmp_path, "2025-06-05 12:30  -45.00  美团外卖\n")

    graph = build_graph()
    state: AgentState = {"input_path": img}
    list(graph.stream(state, config=thread, stream_mode="updates"))

    # 追加：近3个月趋势折线图
    list(graph.stream(Command(resume="近3个月收支趋势折线图"), config=thread, stream_mode="updates"))
    snap = graph.get_state(thread)
    assert "monthly_trend" in snap.values.get("charts", [])

    # 再追加：本周支出分类饼图
    list(graph.stream(Command(resume="本周支出分类饼图"), config=thread, stream_mode="updates"))
    snap = graph.get_state(thread)
    assert "weekly_pie" in snap.values.get("charts", [])

    # 结束
    list(graph.stream(Command(resume="没有了，结束"), config=thread, stream_mode="updates"))
    assert graph.get_state(thread).next == ()
