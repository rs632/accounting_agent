"""录屏视频 → 抽帧 → 每帧 OCR → 合并文本。

支持手机录屏（mp4 等）上传：按固定间隔抽帧 + 场景变化检测，
对每帧做 OCR 后再合并，避免一屏重复文本。
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

SCENE_CHANGE_THRESHOLD = 28.0   # 帧间差异均值，低于阈值视为相同画面
MAX_FRAMES = 120                # 最多抽帧数


def sample_frames(video_path: str, out_dir: str, interval_sec: float = 1.0) -> list[str]:
    """从视频中抽取代表性帧，返回保存的帧图片路径列表。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"无法打开视频: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frame_gap = max(int(fps * interval_sec), 1)
    saved: list[str] = []
    prev: np.ndarray | None = None
    idx = 0

    while cap.isOpened() and len(saved) < MAX_FRAMES:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % frame_gap == 0:
            small = cv2.resize(frame, (320, int(frame.shape[0] * 320 / frame.shape[1])))
            diff = 1e9
            if prev is not None:
                diff = float(np.mean(np.abs(small.astype(float) - prev.astype(float))))
            if prev is None or diff > SCENE_CHANGE_THRESHOLD:
                path = out / f"frame_{idx:06d}.png"
                cv2.imwrite(str(path), frame)
                saved.append(str(path))
                prev = small
        idx += 1

    cap.release()
    if not saved:
        raise RuntimeError("视频中没有提取到有效帧")
    return saved


def frames_to_text(ocr, frame_paths: list[str]) -> str:
    """对每帧做 OCR，去重后合并成整段文本。"""
    seen: set[str] = set()
    all_lines: list[str] = []
    for path in frame_paths:
        for line in ocr.recognize_text(path).splitlines():
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                all_lines.append(line)
    return "\n".join(all_lines)
