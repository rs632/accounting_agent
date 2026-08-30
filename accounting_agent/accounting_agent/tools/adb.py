"""adb 安卓截屏工具。"""
from __future__ import annotations

import subprocess
from pathlib import Path


def adb_available() -> bool:
    try:
        subprocess.run(["adb", "version"], capture_output=True, check=True, timeout=10)
        return True
    except Exception:
        return False


def capture_screen(adb: str = "adb", out_dir: str = "screenshots") -> str:
    """通过 adb 截取安卓手机当前屏幕，返回保存的图片路径。"""
    if not adb_available():
        raise RuntimeError("未找到 adb 命令，请先安装 platform-tools 并配置 PATH")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    remote = "/sdcard/accounting_agent_capture.png"
    subprocess.run([adb, "shell", "screencap", "-p", remote], check=True, timeout=60)
    local = out / "adb_capture.png"
    subprocess.run([adb, "pull", remote, str(local)], check=True, timeout=60)
    subprocess.run([adb, "shell", "rm", "-f", remote], check=True, timeout=30)
    return str(local)
