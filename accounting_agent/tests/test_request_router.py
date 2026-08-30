"""用户追加需求路由测试。"""
from accounting_agent.tools.request_router import classify_request


def test_weekly_pie():
    assert classify_request("给我看本周支出分类占比饼图") == ["weekly_pie"]


def test_monthly_trend():
    assert classify_request("近3个月收支趋势折线图") == ["monthly_trend"]


def test_daily_bar():
    assert classify_request("消费集中在哪几天") == ["daily_bar"]


def test_done():
    assert classify_request("没有了，结束") == []
    assert classify_request("不用了谢谢") == []
