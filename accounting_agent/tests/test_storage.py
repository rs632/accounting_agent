"""存储去重测试。"""
from accounting_agent.models import Transaction
from accounting_agent.tools.storage import LedgerDB


def test_dedupe_via_unique(tmp_path):
    db = LedgerDB(str(tmp_path / "test.db"))
    tx = Transaction(date="2025-06-05", time="12:30:00", amount=-45.0, merchant="美团外卖")

    inserted, dup = db.insert_many([tx])
    assert len(inserted) == 1 and len(dup) == 0

    inserted2, dup2 = db.insert_many([tx])
    assert len(inserted2) == 0 and len(dup2) == 1

    assert db.count() == 1


def test_export_csv(tmp_path):
    db = LedgerDB(str(tmp_path / "test.db"))
    db.insert_many([Transaction(date="2025-06-05", amount=-45.0, merchant="美团外卖")])
    csv_path = str(tmp_path / "ledger.csv")
    path = db.export_csv(csv_path)
    assert path == csv_path
    assert "美团外卖" in open(csv_path, encoding="utf-8-sig").read()
