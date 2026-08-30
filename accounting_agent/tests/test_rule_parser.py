"""规则解析器测试。"""
import pytest

from accounting_agent.parsers.rule_parser import parse_amount, parse_text


def test_parse_amount_expense():
    assert parse_amount("-45.00") == -45.00
    assert parse_amount("-¥45.00") == -45.00
    assert parse_amount("¥123.45") == -123.45


def test_parse_amount_income():
    assert parse_amount("+12000.00") == 12000.00
    assert parse_amount("收入 ¥8,888.88") == 8888.88
    assert parse_amount("工资到账 12000.00") == 12000.00


def test_parse_text_multiple():
    text = "2025-06-05 12:30  -¥45.00  美团外卖\n06-06 08:00  工资  +¥12000.00\n"
    res = parse_text(text)
    assert len(res.transactions) == 2
    assert res.transactions[0].amount == 45.00
    assert res.transactions[0].type == "expense"
    assert res.transactions[0].category == "餐饮"
    assert res.transactions[1].amount == 12000.00
    assert res.transactions[1].type == "income"


def test_parse_skips_noise():
    text = "余额 123.45\n上月账单已还清\n"
    res = parse_text(text)
    assert res.transactions == []
    assert len(res.skipped) >= 2


def test_classify_categories():
    text = "2025-06-05 09:00 -4.00 地铁\n2025-06-05 20:00 -159.00 京东商城\n2025-06-05 21:00 -25.00 电影票\n"
    res = parse_text(text)
    cats = {t.merchant: t.category for t in res.transactions}
    assert cats["地铁"] == "交通"
    assert cats["京东商城"] == "购物"
    assert cats["电影票"] == "娱乐"


@pytest.mark.parametrize("line", ["2024-06-05 12:30 -¥45.00 美团外卖",
                                  "06-05 12:30  -45.00  瑞幸咖啡",
                                  "2024-06-05 08:00 收款 8.88 支付宝红包"])
def test_parse_single_line(line):
    res = parse_text(line)
    assert len(res.transactions) == 1
    assert res.transactions[0].date
