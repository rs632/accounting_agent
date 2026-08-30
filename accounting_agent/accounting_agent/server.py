"""手机端后端服务（FastAPI，异步任务 + 进度反馈）。

手机浏览器访问 `/`（移动端适配页）：
  - 上传支付记录长截图 / 录屏视频（带上传进度条）
  - 实时显示处理阶段（OCR → 解析 → 图表 → 入库 → 报告）
  - 完成后展示结果 + 一键打开图表报告

接口：
  POST /api/process    上传文件 或 传 ocr_text → 立即返回 {job_id}
  GET  /api/status/{id} 轮询任务状态/进度/结果
  GET  /reports/{file} 报告静态托管

启动：
  uvicorn accounting_agent.server:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import shutil
import tempfile
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from accounting_agent.config import load_config
from accounting_agent.engines import build_engine
from accounting_agent.graph import run_pipeline
from accounting_agent.tools.video import frames_to_text, sample_frames

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "accounting_agent" / "web"

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
MAX_UPLOAD_MB = 300  # 视频/图片大小上限

config = load_config()
config._raw.setdefault("report", {})["open_after"] = False  # 服务模式不弹浏览器


@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=_janitor, daemon=True).start()
    yield


app = FastAPI(title="accounting_agent · 智能记账助手", version="0.1.0", lifespan=lifespan)

Path(config.report_dir).mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=config.report_dir), name="reports")


# ---------------- 异步任务 ----------------
@dataclass
class Job:
    id: str
    state: str = "pending"        # pending | processing | done | error
    stage: str = "排队中"
    progress: int = 0
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    media_path: Optional[str] = None
    ocr_text: Optional[str] = None
    is_video: bool = False


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()

# 处理串行化：避免并发 onnxruntime / 并发 DeepSeek 请求导致卡死或限流
_pipeline_lock = threading.Lock()

MAX_JOB_SECONDS = 240  # 单任务硬超时，超时直接判失败，避免手机端无限等待


def _janitor() -> None:
    """后台看门狗：清理并判超时任务。"""
    while True:
        time.sleep(10)
        now = time.time()
        with _jobs_lock:
            for job in list(_jobs.values()):
                if job.state == "processing" and now - job.started_at > MAX_JOB_SECONDS:
                    job.state = "error"
                    job.error = f"处理超时（超过 {MAX_JOB_SECONDS}s），请重试"
                    job.finished_at = now
                    if job.media_path:
                        try:
                            shutil.rmtree(Path(job.media_path).parent, ignore_errors=True)
                        except Exception:
                            pass


def _stage_callback(job: Job):
    # 阶段名 -> 进度百分比（粗略映射）
    _PCT = {
        "获取截图": 5, "OCR 识别文本": 15, "解析结构化账单": 35,
        "载入历史账本": 45, "生成统计图表": 60, "写入账本": 75, "生成报告": 90,
        "提交文本": 35, "视频抽帧": 10, "OCR 识别": 20,
    }

    def cb(stage: str) -> None:
        with _jobs_lock:
            job.stage = stage
            job.progress = _PCT.get(stage, job.progress)
    return cb


def _worker(job: Job) -> None:
    with _jobs_lock:
        job.state = "processing"
        job.progress = 5
    try:
        with _pipeline_lock:
            if job.ocr_text:
                with _jobs_lock:
                    job.stage = "解析记账中"
                state = run_pipeline(config, ocr_text=job.ocr_text,
                                     thread_id=f"mobile-{uuid.uuid4().hex[:8]}",
                                     progress=_stage_callback(job))
            elif job.is_video:
                with _jobs_lock:
                    job.stage = "视频抽帧"
                    job.progress = 8
                work = Path(job.media_path).parent
                frames = sample_frames(job.media_path, str(work / "frames"), interval_sec=1.0)
                engine = build_engine(engine=config.ocr_engine, lang=config.ocr_lang,
                                      use_gpu=config.ocr_use_gpu)
                with _jobs_lock:
                    job.stage = "OCR 识别"
                    job.progress = 20
                ocr_text = frames_to_text(engine, frames)
                if not ocr_text.strip():
                    raise HTTPException(422, "视频中未识别到文本")
                state = run_pipeline(config, ocr_text=ocr_text,
                                     thread_id=f"mobile-{uuid.uuid4().hex[:8]}",
                                     progress=_stage_callback(job))
            else:
                state = run_pipeline(config, input_path=job.media_path,
                                     thread_id=f"mobile-{uuid.uuid4().hex[:8]}",
                                     progress=_stage_callback(job))
        result = _serialize(state)
        with _jobs_lock:
            job.result = result
            job.state = "done"
            job.progress = 100
            job.stage = "完成"
            job.finished_at = time.time()
    except HTTPException as e:
        _fail(job, e.detail)
    except Exception as e:  # noqa: BLE001
        _fail(job, f"{e}")
    finally:
        if job.media_path:
            try:
                shutil.rmtree(Path(job.media_path).parent, ignore_errors=True)
            except Exception:
                pass


def _fail(job: Job, msg: str) -> None:
    with _jobs_lock:
        job.state = "error"
        job.error = msg
        job.finished_at = time.time()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "model": config.llm_model, "db": config.db_path}


@app.post("/api/process")
async def process(file: Optional[UploadFile] = File(None),
                  ocr_text: Optional[str] = Form(None)) -> dict:
    """接收文件或 OCR 文本，创建异步任务并立即返回 job_id。"""
    job_id = uuid.uuid4().hex[:12]
    job = Job(id=job_id)
    with _jobs_lock:
        _jobs[job_id] = job

    if ocr_text is not None and ocr_text.strip():
        with _jobs_lock:
            job.ocr_text = ocr_text.strip()
            job.stage = "提交文本"
            job.state = "processing"
        threading.Thread(target=_worker, args=(job,), daemon=True).start()
        return {"job_id": job_id}

    if file is None or not file.filename:
        _fail(job, "需要上传文件或提供 ocr_text")
        return {"job_id": job_id}
    ext = Path(file.filename).suffix.lower()
    is_vid = ext in VIDEO_EXTS
    if not is_vid and ext not in IMAGE_EXTS:
        _fail(job, f"不支持的格式 {ext}（支持 {'/'.join(IMAGE_EXTS | VIDEO_EXTS)}）")
        return {"job_id": job_id}

    work = Path(tempfile.mkdtemp(prefix="acct_"))
    try:
        raw = work / f"upload{ext}"
        size = 0
        with raw.open("wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    _fail(job, f"文件超过 {MAX_UPLOAD_MB}MB 上限")
                    return {"job_id": job_id}
                f.write(chunk)
    except Exception as e:  # noqa: BLE001
        _fail(job, f"保存文件失败: {e}")
        return {"job_id": job_id}

    with _jobs_lock:
        job.media_path = str(raw)
        job.is_video = is_vid
        job.stage = "已上传，排队处理"
    threading.Thread(target=_worker, args=(job,), daemon=True).start()
    return {"job_id": job_id}


@app.get("/api/status/{job_id}")
def status(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    with _jobs_lock:
        return {
            "job_id": job.id,
            "state": job.state,
            "stage": job.stage,
            "progress": job.progress,
            "elapsed": round(time.time() - job.started_at, 1),
            "error": job.error,
            "result": job.result,
        }


def _serialize(state: dict) -> dict:
    """把最终状态转成手机端 JSON。"""
    txs = state.get("transactions", [])
    report = Path(state["report_path"])
    report_name = report.name if report.exists() else ""
    return {
        "ok": True,
        "parser_used": state.get("parser_used", "rule"),
        "fallback_reason": state.get("fallback_reason"),
        "transaction_count": len(txs),
        "income": round(sum(t.amount for t in txs if t.type == "income"), 2),
        "expense": round(sum(t.amount for t in txs if t.type == "expense"), 2),
        "inserted": len(state.get("inserted", [])),
        "duplicates": len(state.get("duplicates", [])),
        "transactions": [t.model_dump() for t in txs],
        "report_url": f"/reports/{report_name}" if report_name else "",
        "report_path": str(report),
    }
