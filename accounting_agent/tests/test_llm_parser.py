"""LLM 解析器单元测试（不调用真实 API，只测 JSON 提取与模型组装）。"""
import pytest

from accounting_agent.config import load_config
from accounting_agent.parsers.llm_parser import _extract_json


def test_extract_json_plain():
    data = _extract_json('{"transactions": [], "skipped": []}')
    assert data == {"transactions": [], "skipped": []}


def test_extract_json_fenced():
    text = "```json\n{\"transactions\": [{\"amount\": -1.5}], \"skipped\": []}\n```"
    data = _extract_json(text)
    assert data["transactions"][0]["amount"] == -1.5


def test_extract_json_noise():
    text = "好的，结果如下：\n{\"transactions\": [], \"skipped\": [\"余额 100\"]}\n（以上为全部）"
    data = _extract_json(text)
    assert data["skipped"] == ["余额 100"]


def test_extract_json_malformed():
    with pytest.raises(Exception):
        _extract_json("不是 JSON")


def test_build_llm_parser_uses_deepseek_config():
    from accounting_agent.parsers.llm_parser import build_llm_parser

    config = load_config()
    if not config.llm_api_key:
        pytest.skip("未配置 LLM API Key")
    llm = build_llm_parser(config)
    assert str(llm.base_url).rstrip("/") == config.llm_base_url.rstrip("/")
    assert llm.api_key == config.llm_api_key
    assert llm.max_retries == 1
