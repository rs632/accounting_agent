"""CLI 入口：accounting-agent [图片路径|auto|adb]。

支持 LangGraph human-in-the-loop：处理完一轮后询问是否需要追加图表。
"""
from __future__ import annotations

import argparse
import sys

from langgraph.types import Command
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from accounting_agent.config import load_config, thread_config
from accounting_agent.graph import DEFAULT_THREAD_ID, build_graph
from accounting_agent.state import AgentState

console = Console()

NODE_LABELS = {
    "capture_screen": "📱 获取支付记录截图",
    "ocr_image": "🔍 OCR 识别文本",
    "parse_transactions": "🧾 解析结构化账单",
    "load_history": "🗄️ 载入历史账本",
    "generate_chart": "📊 生成统计图表",
    "save_transactions": "💾 写入账本历史(SQLite)",
    "send_to_user": "📤 发送报告",
    "ask_more": "💬 询问追加需求",
}

GREETING = """[bold cyan]智能记账助手 accounting_agent[/bold cyan] · LangGraph Workflow
支付记录长截图 → 账本 + 统计图表 → 存历史 + 发送报告
"""


def _print_update(node: str, data: dict) -> None:
    label = NODE_LABELS.get(node, node)
    console.print(f"[dim]·[/dim] [bold]{label}[/bold] [dim]完成[/dim]")
    if node == "parse_transactions":
        n = len(data.get("transactions") or [])
        income = sum(t.amount for t in data.get("transactions") or [] if t.type == "income")
        expense = sum(t.amount for t in data.get("transactions") or [] if t.type == "expense")
        used = "LLM" if data.get("parser_used") == "llm" else "规则"
        console.print(f"    [dim]({used}解析)[/dim] 识别 [bold]{n}[/bold] 笔 · 支出 [red]{expense:,.2f}[/red] · 收入 [green]{income:,.2f}[/green]")
        if data.get("fallback_reason"):
            console.print(f"    [yellow]LLM 解析失败，已降级规则解析[/yellow]: {data['fallback_reason'][:160]}")
        skipped = data.get("skipped") or []
        if skipped:
            console.print(f"    [yellow]未识别 {len(skipped)} 行[/yellow]: {skipped[:3]}")
    elif node == "save_transactions":
        console.print(f"    入库 [bold green]{len(data.get('inserted') or [])}[/bold green] 笔 · 重复跳过 [dim]{len(data.get('duplicates') or [])}[/dim] 笔")
    elif node == "send_to_user":
        console.print(f"    报告: [underline cyan]{data.get('report_path')}[/underline cyan]")


def _print_summary(state: dict) -> None:
    txs = state.get("transactions") or []
    inserted = state.get("inserted") or []
    duplicates = state.get("duplicates") or []
    if not txs:
        return
    table = Table(title="本次识别明细", show_lines=True)
    for col in ["日期", "时间", "金额", "类别", "商户"]:
        table.add_column(col)
    for t in txs:
        sign = "+" if t.type == "income" else "-"
        amount = f"{sign}{t.amount:,.2f}"
        table.add_row(t.date, t.time or "-", amount, t.category, t.merchant or "-")
    console.print(table)
    console.print(f"本次: [green]入库 {len(inserted)}[/green] · [dim]重复跳过 {len(duplicates)}[/dim]")


def _run_pipeline(graph, config, input_path: str, thread_id: str) -> dict:
    state: AgentState = {"input_path": input_path}
    thread = thread_config(config, thread_id)
    resume_value = None
    final: dict = {}

    while True:
        events = list(graph.stream(
            Command(resume=resume_value) if resume_value is not None else state,
            config=thread,
            stream_mode="updates",
        ))
        resume_value = None
        for event in events:
            for node, data in event.items():
                _print_update(node, data)

        snapshot = graph.get_state(thread)
        tasks = snapshot.tasks
        if tasks and getattr(tasks[0], "interrupts", None):
            for iv in tasks[0].interrupts:
                payload = iv.value
                console.print(Panel(payload.get("question", "是否需要追加图表？"),
                                    border_style="magenta", title="等待输入"))
            try:
                answer = console.input("[bold magenta]你的回复[/bold magenta] (Enter 直接结束): ").strip()
            except (KeyboardInterrupt, EOFError):
                console.print("\n[yellow]已结束。[/yellow]")
                break
            if not answer:
                resume_value = "没有，结束"
            else:
                resume_value = answer
            continue
        final = snapshot.values
        break

    return final


def _run(graph, config, input_path: str, thread_id: str) -> None:
    final = _run_pipeline(graph, config, input_path, thread_id)
    if final:
        _print_summary(final)
        report = final.get("report_path")
        if report:
            console.print(Panel(f"[bold green]报告已生成并自动打开[/bold green]\n{report}\n"
                                f"账单历史: {config.db_path}\nCSV 导出: {config.csv_path}",
                                title="📤 已发送给用户", border_style="green"))


def cli(argv: list[str] | None = None) -> None:
    # Windows 控制台统一用 UTF-8，避免中文乱码
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(prog="accounting-agent", description="智能记账助手：长截图 → 账本 + 统计图表")
    parser.add_argument("path", nargs="?", default=None,
                        help="截图路径 / auto(取最新截图) / adb(安卓截屏)，默认 auto")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--thread", default=DEFAULT_THREAD_ID, help="会话 thread_id（用于状态持久化）")
    parser.add_argument("--no-llm", action="store_true", help="强制使用规则解析，不调用 LLM")
    args = parser.parse_args(argv)

    console.print(GREETING)
    config = load_config(args.config)
    if args.no_llm:
        config._raw.setdefault("parser", {})["mode"] = "rule"

    graph = build_graph()
    try:
        _run(graph, config, args.path, args.thread)
    except Exception as e:  # noqa: BLE001
        console.print(f"[bold red]流程失败:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()
