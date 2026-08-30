# 一键演示：生成模拟支付记录长截图 → 跑完整 LangGraph 流程
# 用法： powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "`n=== 1/2 生成模拟支付记录长截图 ===" -ForegroundColor Cyan
python -X utf8 scripts/make_sample_screenshot.py

Write-Host "`n=== 2/2 运行智能记账助手（真实 RapidOCR + 规则解析） ===" -ForegroundColor Cyan
Write-Host "（如需追加图表，请在提示时输入，例如：近3个月收支趋势折线图；回车直接结束）`n"
python -X utf8 -m accounting_agent.main screenshots/payment_history.png --no-llm

Write-Host "`n=== 报表文件 ===" -ForegroundColor Cyan
Get-ChildItem data\reports\*.html | Select-Object -ExpandProperty Name
