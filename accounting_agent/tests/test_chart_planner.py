"""模型驱动图表规划器测试（无 LLM 时走规则兜底）。"""
from accounting_agent.config import load_config
from accounting_agent.parsers.chart_planner import (
    _extract_obj,
    _normalize,
    plan_charts,
)


def _rule_config():
    config = load_config()
    config._raw["parser"]["mode"] = "rule"
    return config


def test_plan_charts_falls_back_to_rules():
    config = _rule_config()
    assert plan_charts(config, "给我看本周支出分类占比饼图") == ["weekly_pie"]
    assert plan_charts(config, "近3个月收支趋势折线图") == ["monthly_trend"]


def test_plan_charts_done_returns_empty():
    config = _rule_config()
    assert plan_charts(config, "没有了，结束") == []
    assert plan_charts(config, "") == []


def test_normalize_valid():
    assert _normalize({"charts": ["monthly_trend"]}) == ["monthly_trend"]
    assert _normalize(["weekly_pie", "weekly_pie", "monthly_pie"]) == [
        "weekly_pie",
        "monthly_pie",
    ]


def test_normalize_empty_is_valid_done():
    assert _normalize({"charts": []}) == []


def test_normalize_invalid_keys_falls_back():
    assert _normalize({"charts": ["不存在的图"]}) is None
    assert _normalize({"foo": 1}) is None
    assert _normalize("oops") is None


def test_extract_obj_handles_fence_and_noise():
    assert _extract_obj('```json\n{"charts": ["daily_bar"]}\n```') == {
        "charts": ["daily_bar"]
    }
    assert _extract_obj('好的，结果如下：{"charts": ["monthly_pie"]} 谢谢') == {
        "charts": ["monthly_pie"]
    }
