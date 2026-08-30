# accounting_agent · 智能记账助手

基于 **LangChain / LangGraph** 的智能记账 Agent：把支付记录**长截图**自动转成**账本 + 统计图表**，存入本地历史（SQLite 自动去重）并生成报告发送给用户；通过 **human-in-the-loop** 支持用户随时追加图表/数据需求。

## 完整流程

```
capture_screen      读取长截图（本地路径 / auto 取最新 / adb 安卓截屏）
        ↓
ocr_image           图片识别文字（PaddleOCR / RapidOCR / Mock 可插拔）
        ↓
parse_transactions  OCR 文本 → 结构化账单（金额/收支/类别/商户/日期）
        ↓                    （LLM 结构化抽取，无 Key 自动降级规则解析）
load_history        载入历史周/月汇总
        ↓
generate_chart      ★本周支出/收入分类占比【饼图·含具体数值】
                    ★本月支出/收入分类占比【饼图】
                    ★消费集中在哪几天【柱状图】
                    （按用户请求按需追加：近6个月趋势折线图等）
        ↓
save_transactions   一份存入本地历史（SQLite 自动去重 + CSV 导出）
        ↓
send_to_user        一份发送给你（HTML 报告自动打开 + outbox 记录）
        ↓
ask_more            等你追加图表/数据需求 → 按需再生成（LangGraph interrupt）
```

## 快速开始

```bash
# 1) 安装依赖（OCR 二选一；rapid 兼容新版 Python）
pip install -r requirements.txt
pip install rapidocr_onnxruntime          # 或安装 paddlepaddle+paddleocr

# 2) 生成模拟支付记录长截图（含同名 .txt 供 mock OCR）
python scripts/make_sample_screenshot.py

# 3) 运行（截图路径 / auto / adb）
python -m accounting_agent.main screenshots/payment_history.png --no-llm
python -m accounting_agent.main auto --no-llm
```

Windows 一键演示：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_demo.ps1
```

## 使用 LLM 解析（更准，默认 DeepSeek）

`config.yaml` 默认 `parser.mode: llm`，接入 **DeepSeek（deepseek-v4-flash）**：

1. API Key 写在项目根目录 `.env`（已 gitignore，不会被提交）：
   ```
   DEEPSEEK_API_KEY=sk-xxxx
   ```
2. 直接运行即走 LLM 解析（失败自动降级规则解析）：
   ```bash
   python -m accounting_agent.main screenshots/payment_history.png
   ```

换其它 OpenAI 兼容网关：修改 `config.yaml` 的 `llm.base_url` / `llm.model` / `llm.api_key_env`。
说明：`deepseek-v4-flash` 处于 thinking 模式，不支持 tool_choice/json_schema，
解析器已改用「明文 JSON + 稳健提取」方案，兼容此类模型。

## 命令与配置

```
usage: accounting-agent [path] [--config PATH] [--thread ID] [--no-llm]
  path       截图路径 | auto(取最新) | adb(安卓截屏)，默认 auto
  --no-llm   强制规则解析（不调用 LLM）
  --thread   LangGraph 会话 ID（配合 checkpointer 持久化）
```

`config.yaml` 关键项：`capture.source`（local/auto/adb）、`ocr.engine`（auto/paddle/rapid/mock）、
`parser.mode`（llm/rule）、`storage.db_path`、`report.dir`、`report.open_after`。

## 项目结构

```
accounting_agent/
├── accounting_agent/
│   ├── graph.py            # LangGraph 工作流组装（含 ask_more 循环）
│   ├── state.py            # 共享状态 AgentState
│   ├── nodes/              # capture/ocr/parse/load_history/generate_chart/
│   │                       #   save_transactions/send_to_user/ask_more
│   ├── engines/            # OCR 引擎：paddle / rapid / mock（可插拔）
│   ├── parsers/            # rule（正则）+ llm（结构化输出）双引擎
│   ├── tools/              # storage(SQLite去重)/stats/report(内联SVG图表)/adb/outbox
│   ├── models.py           # Transaction 等 Pydantic 模型
│   └── main.py             # CLI（rich 输出 + interrupt 交互）
├── scripts/                # 示例截图生成、一键 demo
├── tests/                  # 解析/存储/图端到端测试
└── config.yaml
```

## 手机端使用（FastAPI 服务）

```powershell
python -m uvicorn accounting_agent.server:app --host 0.0.0.0 --port 8000
```
手机与电脑连同一 WiFi，用手机浏览器打开 **`http://<电脑IP>:8000`**：
- 选「支付记录**长截图**」或「**录屏视频**」（自动抽帧 OCR）→ 自动识别
- 页面直接显示支出/收入/笔数 + 交易明细，点按钮打开**统计图表报告**（移动端适配）

其它接口：
- `GET /api/health` 健康检查
- `POST /api/process` 上传图片/视频（multipart `file`），或直接传 `ocr_text` 文本
- `GET /reports/{file}` 查看历史报告
- 安卓 adb 直连截图：`python -m accounting_agent.main adb --no-llm`

## 测试

```bash
python -m pytest tests -q
```

## 说明

- 本机 Python 3.14 下 PaddlePaddle 暂无 Windows 轮子，`ocr.engine: auto` 会自动回退到 RapidOCR（已安装即可用），无需改配置。
- 手机端落地：`capture.source: adb` 通过 adb 截取安卓屏幕；接口可被手机 App 调用（`run(graph, state, config)` 返回最终状态）。
