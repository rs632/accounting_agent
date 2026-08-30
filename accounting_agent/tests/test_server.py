"""手机端服务 API 测试（规则解析，不依赖外部资源）。"""
import time

from fastapi.testclient import TestClient

from accounting_agent.server import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_index_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "智能记账助手" in r.text
    assert "/api/process" in r.text


def _wait_done(job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        j = client.get(f"/api/status/{job_id}").json()
        if j["state"] in ("done", "error"):
            return j
        time.sleep(0.5)
    raise TimeoutError("任务超时")


def test_process_ocr_text(tmp_path):
    import accounting_agent.server as srv

    # 隔离数据目录 + 规则解析
    srv.config._raw["parser"]["mode"] = "rule"
    srv.config._raw["report"]["open_after"] = False
    srv.config._raw["storage"]["db_path"] = str(tmp_path / "ledger.db")
    srv.config._raw["storage"]["csv_path"] = str(tmp_path / "ledger.csv")
    srv.config._raw["report"]["dir"] = str(tmp_path / "reports")

    r = client.post("/api/process", data={
        "ocr_text": "2026-08-05 12:30  -45.00  美团外卖\n2026-08-06 08:00  +12000.00  工资发放\n",
    })
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    j = _wait_done(job_id)
    assert j["state"] == "done", j
    res = j["result"]
    assert res["transaction_count"] == 2
    assert res["expense"] == 45.0
    assert res["income"] == 12000.0
    assert res["report_url"], "应返回报告地址"
    assert (tmp_path / "reports").is_dir()


def test_status_missing():
    r = client.get("/api/status/nonexistent")
    assert r.status_code == 404
