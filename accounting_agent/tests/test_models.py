"""Transaction 模型与 checkpoint 序列化回归测试。"""
from accounting_agent.models import Transaction


def test_amount_signed_input():
    tx = Transaction(date="2026-08-05", amount=-32.5, merchant="美团外卖")
    assert tx.type == "expense" and tx.amount == 32.5
    inc = Transaction(date="2026-08-05", amount=12000.0)
    assert inc.type == "income" and inc.amount == 12000.0


def test_explicit_type_preserved():
    tx = Transaction(date="2026-08-05", amount=32.5, type="expense", merchant="美团外卖")
    assert tx.type == "expense" and tx.amount == 32.5


def test_checkpoint_roundtrip_preserves_type():
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer(allowed_msgpack_modules=[
        ("accounting_agent.models", "Transaction"),
        ("accounting_agent.models", "MonthStats"),
    ])
    tx = Transaction(date="2026-08-05", amount=-32.5, merchant="美团外卖")
    assert tx.type == "expense"

    back = serde.loads_typed(serde.dumps_typed([tx]))[0]
    assert back.type == "expense", "checkpoint 回读后 expense 不应变成 income"
    assert back.amount == 32.5
