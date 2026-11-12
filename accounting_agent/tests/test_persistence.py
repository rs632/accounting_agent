"""SQLite checkpointer 持久化测试：模拟进程重启后仍能读回会话状态。"""
import accounting_agent.graph as g
from accounting_agent.config import load_config, thread_config


def _cfg(tmp_path):
    config = load_config()
    config._raw["storage"]["db_path"] = str(tmp_path / "ledger.db")
    config._raw["storage"]["csv_path"] = str(tmp_path / "ledger.csv")
    config._raw["storage"]["checkpoint_path"] = str(tmp_path / "checkpoints.db")
    config._raw["report"]["dir"] = str(tmp_path / "reports")
    config._raw["parser"]["mode"] = "rule"
    config._raw["ocr"]["engine"] = "mock"
    config._raw["report"]["open_after"] = False
    return config


def _make_mock_image(tmp_path, text: str) -> str:
    img = tmp_path / "screenshots" / "demo.png"
    img.parent.mkdir(parents=True, exist_ok=True)
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 16)
    img.with_suffix(".txt").write_text(text, encoding="utf-8")
    return str(img)


def test_checkpoint_persists_across_instances(tmp_path):
    from langgraph.types import Command

    config = _cfg(tmp_path)
    thread = thread_config(config, "persist-thread")
    img = _make_mock_image(tmp_path, "2025-06-05 12:30  -45.00  美团外卖\n")

    graph1 = g.build_graph(checkpointer=g.make_checkpointer(config))
    list(graph1.stream({"input_path": img}, config=thread, stream_mode="updates"))
    list(graph1.stream(Command(resume="没有，结束"), config=thread, stream_mode="updates"))
    report_path = graph1.get_state(thread).values.get("report_path")
    assert report_path

    # 模拟进程重启：关闭连接、清空进程内缓存，从磁盘重建 checkpointer
    with g._CHECKPOINTERS_LOCK:
        for saver in g._CHECKPOINTERS.values():
            saver.conn.close()
        g._CHECKPOINTERS.clear()

    assert (tmp_path / "checkpoints.db").exists()
    graph2 = g.build_graph(checkpointer=g.make_checkpointer(config))
    restored = graph2.get_state(thread).values
    assert restored.get("report_path") == report_path
    assert len(restored.get("transactions", [])) == 1
