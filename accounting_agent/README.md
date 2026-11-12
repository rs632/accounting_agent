# accounting_agent · 智能记账助手

基于 **LangGraph** 的智能记账 Agent：把支付记录的**长截图 / 录屏**自动转成**账本 + 统计图表**，
存入本地历史（SQLite 自动去重）并生成 HTML 报告；支持 human-in-the-loop，按需追加图表/数据。

## 特性

- **多来源输入**：本地图片、`auto` 取最新截图、`adb` 安卓实时截屏、录屏视频自动抽帧
- **可插拔 OCR**：PaddleOCR / RapidOCR / Mock，按环境自动回退
- **双解析引擎**：LLM 结构化抽取（DeepSeek 等 OpenAI 兼容接口）+ 规则解析兜底
- **模型驱动意图**：追加图表请求由 LLM 理解（失败自动降级关键字规则）
- **自动去重入库**：SQLite 指纹去重，同时导出 CSV
- **图表报告**：本周/本月分类占比饼图、每日消费柱状图、近 6 个月趋势等
- **human-in-the-loop**：`interrupt()` 暂停等待用户追加需求，状态经 SQLite 持久化
- **两种入口**：CLI（rich 终端）+ FastAPI 移动端网页

## 工作流程

```
capture_screen      读取长截图（本地路径 / auto / adb）
        ↓
ocr_image           图片识别文字（PaddleOCR / RapidOCR / Mock）
        ↓
parse_transactions  OCR 文本 → 结构化账单（LLM 优先，失败降级规则）
        ↓
load_history        载入历史账本，生成周/月汇总
        ↓
generate_chart      本周/本月分类占比饼图、每日消费柱状图（按需追加趋势图等）
        ↓
save_transactions   写入本地历史（SQLite 自动去重 + CSV 导出）
        ↓
send_to_user        生成 HTML 报告并记录 outbox
        ↓
ask_more            human-in-the-loop：等待追加图表/数据需求
        ↓  (按需) generate_chart → send_to_user → ask_more ... → END
```

## 快速开始

```bash
# 1) 安装依赖
pip install -r requirements.txt
pip install rapidocr_onnxruntime        # OCR（或安装 paddlepaddle + paddleocr）

# 2) 生成示例支付记录长截图（含同名 .txt 供 mock OCR）
python scripts/make_sample_screenshot.py

# 3) 运行（截图路径 / auto / adb）
python -m accounting_agent.main screenshots/payment_history.png --no-llm
python -m accounting_agent.main auto --no-llm
```

## 使用 LLM 解析

`config.yaml` 默认 `parser.mode: llm`，接入 DeepSeek（OpenAI 兼容接口）：

1. 在项目根目录 `.env` 写入 API Key（已 gitignore，不会被提交）：
   ```
   DEEPSEEK_API_KEY=sk-xxxx
   ```
2. 直接运行即走 LLM 解析，失败自动降级规则解析：
   ```bash
   python -m accounting_agent.main screenshots/payment_history.png
   ```

换其它兼容网关：修改 `config.yaml` 的 `llm.base_url` / `llm.model` / `llm.api_key_env`。

> 说明：`deepseek-v4-flash` 为 thinking 模式，不支持 `tool_choice` / `json_schema`，
> 因此解析与图表规划均采用「明文 JSON + 稳健提取 + 墙钟超时」方案。

## 命令行

```
usage: accounting-agent [path] [--config PATH] [--thread ID] [--no-llm]

  path       截图路径 | auto(取最新) | adb(安卓截屏)，默认 auto
  --config   配置文件路径
  --thread   LangGraph 会话/状态持久化 ID
  --no-llm   强制规则解析（不调用 LLM）
```

## 配置项

`config.yaml` 关键项：

| 配置 | 说明 |
| --- | --- |
| `capture.source` | `local` / `auto` / `adb` |
| `ocr.engine` | `auto` / `paddle` / `rapid` / `mock` |
| `parser.mode` | `llm` / `rule` |
| `storage.db_path` | 账本 SQLite 路径 |
| `storage.checkpoint_path` | 会话/中断状态持久化 SQLite（默认与账本同目录） |
| `storage.dedupe_window_days` | 去重窗口 |
| `report.dir` / `report.open_after` | 报告目录 / 生成后是否自动打开 |
| `llm.*` | `model` / `base_url` / `api_key_env` 等 |

## 手机端 / Web 服务

```powershell
python -m uvicorn accounting_agent.server:app --host 0.0.0.0 --port 8000
```

手机与电脑连同一 WiFi，浏览器打开 `http://<电脑IP>:8000`：

- 上传支付记录**长截图**或**录屏视频**（自动抽帧 OCR）
- 实时显示处理阶段（OCR → 解析 → 图表 → 入库 → 报告）
- 完成后展示支出/收入/笔数 + 明细，可打开统计图表报告

接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/process` | 上传 `file` 或传 `ocr_text`，返回 `job_id` |
| GET | `/api/status/{id}` | 轮询任务状态/进度/结果 |
| GET | `/reports/{file}` | 查看历史报告 |

> 任务表与处理串行锁为进程内状态，**必须单进程运行**（不要加 `--workers`）。
> 服务端会强制关闭「报告自动打开」，由用户在页面点击查看。

## 项目结构

```
accounting_agent/
├── accounting_agent/
│   ├── graph.py            # LangGraph 工作流组装（含 ask_more 循环 + SQLite checkpointer）
│   ├── state.py            # 共享状态 AgentState
│   ├── config.py           # 配置加载（config.yaml + .env）
│   ├── models.py           # Transaction / MonthStats 等模型
│   ├── prompts.py          # LLM 提示词（账单解析 + 图表规划）
│   ├── main.py             # CLI 入口
│   ├── server.py           # FastAPI 手机端服务
│   ├── nodes/              # capture/ocr/parse/load_history/generate_chart/save/send/ask_more
│   ├── engines/            # OCR 引擎：paddle / rapid / mock
│   ├── parsers/            # rule / llm / chart_planner
│   └── tools/              # storage / report / stats / adb / outbox / video / request_router
├── scripts/                # 示例截图生成、一键 demo
├── tests/                  # 解析 / 存储 / 图端到端 / 服务 / 持久化测试
├── config.yaml
└── requirements.txt
```

## 测试

```bash
python -m pytest tests -q
```

覆盖：规则/LLM 解析、图表意图规划、去重存储、图端到端、Web 接口、SQLite 持久化。

## 说明

- 本机 Python 3.14 下 PaddlePaddle 暂无 Windows 轮子，`ocr.engine: auto` 会自动回退 RapidOCR。
- 图表意图规划仅在 `parser.mode: llm` 且配置了 API Key 时生效，否则使用关键字规则。
- 会话/中断状态通过 `langgraph-checkpoint-sqlite` 持久化到 `storage.checkpoint_path`，
  同一 `--thread` 在进程重启后仍可恢复。
