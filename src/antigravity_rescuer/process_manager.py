"""
跨平台进程控制与生命周期管理模块.

支持 Windows / macOS / Linux 操作系统的 Antigravity 与 Language Server 进程安全停止与自动拉起。
"""

import os
import subprocess
import sys
import time


def stop_antigravity_processes() -> bool:
    """
    跨平台安全终止运行中的 Antigravity 与 Language Server 进程。

    Returns:
        bool: True 表示终止指令已发送并等待完成。
    """
    try:
        if sys.platform.startswith("win"):
            subprocess.run(
                ["taskkill", "/F", "/IM", "Antigravity.exe", "/T"],
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "language_server.exe", "/T"],
                capture_output=True,
                check=False,
            )
        else:
            subprocess.run(
                ["pkill", "-9", "-f", "Antigravity"],
                capture_output=True,
                check=False,
            )
            subprocess.run(
                ["pkill", "-9", "-f", "language_server"],
                capture_output=True,
                check=False,
            )
        time.sleep(1.5)
        return True
    except Exception:
        return False


def get_default_antigravity_executable() -> str | None:
    """
    根据当前操作系统自动探测 Antigravity 客户端可执行文件的默认安装路径。

    Returns:
        Optional[str]: 发现的可执行文件路径，未找到则返回 None。
    """
    if sys.platform.startswith("win"):
        candidates = [
            os.path.join(
                os.path.expandvars(r"%LOCALAPPDATA%"),
                "Programs",
                "antigravity",
                "Antigravity.exe",
            ),
            os.path.join(
                os.path.expandvars(r"%USERPROFILE%"),
                "AppData",
                "Local",
                "Programs",
                "antigravity",
                "Antigravity.exe",
            ),
        ]
    elif sys.platform.startswith("darwin"):
        candidates = [
            "/Applications/Antigravity.app/Contents/MacOS/Antigravity",
            os.path.expanduser("~/Applications/Antigravity.app/Contents/MacOS/Antigravity"),
        ]
    else:
        candidates = [
            os.path.expanduser("~/.local/share/antigravity/antigravity"),
            "/usr/bin/antigravity",
            "/usr/local/bin/antigravity",
        ]

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def start_antigravity_process(exe_path: str | None = None) -> bool:
    """
    重新启动 Antigravity 客户端。

    Args:
        exe_path (Optional[str], optional): 可执行文件路径。默认为 None (自动探测)。

    Returns:
        bool: True 表示启动成功发起。
    """
    if not exe_path:
        exe_path = get_default_antigravity_executable()

    if not exe_path or not os.path.exists(exe_path):
        return False

    try:
        subprocess.Popen([exe_path], close_fds=True)
        return True
    except Exception:
        return False
