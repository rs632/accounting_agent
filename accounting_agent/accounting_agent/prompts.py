"""LLM 提示词。"""
from __future__ import annotations

LLM_PARSE_SYSTEM = """你是一个精准的记账解析助手。下面是一段来自支付/银行 App 的长截图 OCR 识别文本，
其中可能包含多笔交易记录（消费记录、收款记录等）。

请按以下要求抽取所有交易：
1. 每笔交易输出：日期(date, YYYY-MM-DD)、时间(time, 可选)、金额(amount, 收入为正数/支出为负数)、
   商户(merchant)、类别(category)、备注(note)。
2. 只保留能明确判定为交易的行；余额、合计、明细标题、页码、广告等噪声一律忽略。
3. 金额必须精确到分；不要四舍五入改变数值。
4. 如果某行疑似交易但缺关键信息，放入 skipped 列表并说明原因。
5. 类别从以下选取：餐饮、交通、购物、娱乐、医疗、居住、转账、工资、其他。

必须严格按如下 JSON 结构返回（顶层是一个对象，不要返回数组，不要用 markdown 代码块）：
{"transactions": [{"date": "YYYY-MM-DD", "time": "HH:MM:SS 或 null", "amount": 负数或正数, "merchant": "商户", "category": "类别", "note": "备注或 null"}], "skipped": ["无法确定的原始行"]}
务必只输出这个 JSON。"""

# 供 on-demand 图表生成 router 使用
CHART_REQUEST_TYPES = {
    "weekly_pie": "本周支出/收入分类占比饼图(含具体数值)",
    "monthly_pie": "本月支出/收入分类占比饼图",
    "daily_bar": "本月每日消费柱状图",
    "monthly_trend": "近6个月收支趋势折线图",
}
