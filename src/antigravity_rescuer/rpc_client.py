"""
Language Server 动态 RPC 同步客户端.

本模块负责：
1. 自动从 Antigravity 主日志中嗅探运行中的 HTTPS 动态端口与 CSRF 安全令牌；
2. 构造标准的 Connect-RPC POST 请求并携带 x-codeium-csrf-token 请求头；
3. 实时向内存树与持久化存储推送项目名称与资源配置，无需重启客户端即可即时生效。
"""

import json
import os
import re
import ssl
import urllib.error
import urllib.request

from antigravity_rescuer.project_normalizer import build_proto3_project_dict


def get_active_server_info(log_path: str | None = None) -> tuple[int | None, str | None]:
    """
    从 Antigravity 的 main.log 中解析当前活跃的 Language Server 端口号与 CSRF Token。

    Args:
        log_path (Optional[str], optional): main.log 的绝对路径。
            默认为 None（自动定位到 %APPDATA%/Antigravity/logs/main.log）。

    Returns:
        Tuple[Optional[int], Optional[str]]: (端口号, CSRF令牌)，若未找到则返回 (None, None)。
    """
    if not log_path:
        log_path = os.path.join(
            os.path.expandvars(r"%APPDATA%"),
            "Antigravity",
            "logs",
            "main.log",
        )

    if not os.path.exists(log_path):
        return None, None

    try:
        with open(log_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        port_matches = re.findall(r"https://127\.0\.0\.1:(\d+)/", content)
        token_matches = re.findall(r"--csrf_token\s+([0-9a-fA-F\-]+)", content)

        if not port_matches or not token_matches:
            return None, None

        return int(port_matches[-1]), token_matches[-1]
    except Exception:
        return None, None


def update_project_via_rpc(
    port: int,
    token: str,
    pid: str,
    pname: str,
    raw_path: str,
    timeout: int = 5,
) -> tuple[bool, str]:
    """
    向 Language Server 发送 UpdateProject RPC 请求更新单个项目配置。

    Args:
        port (int): Language Server 本地 HTTPS 监听端口。
        token (str): CSRF 认证安全令牌。
        pid (str): 项目唯一 UUID。
        pname (str): 项目名称。
        raw_path (str): 本地磁盘路径。
        timeout (int, optional): 请求超时时间 (秒)。默认为 5。

    Returns:
        Tuple[bool, str]: (是否成功, 响应体或错误描述)。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    url = f"https://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/UpdateProject"
    project_payload = build_proto3_project_dict(pid, pname, raw_path)
    body_data = json.dumps({"project": project_payload}).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=body_data,
        headers={
            "Content-Type": "application/json",
            "x-codeium-csrf-token": token,
            "Connect-Protocol-Version": "1",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            return True, body.strip() or "OK"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return False, f"HTTP {e.code}: {err_body}"
    except Exception as e:
        return False, str(e)


def broadcast_all_projects(
    projects_map: dict[str, tuple[str, str]],
    log_path: str | None = None,
) -> tuple[int, int]:
    """
    自动检测正在运行的 Antigravity 实例，并将所有项目名称全量广播推送。

    Args:
        projects_map (Dict[str, Tuple[str, str]]): 项目映射表。
        log_path (Optional[str], optional): 日志路径。

    Returns:
        Tuple[int, int]: (成功数量, 总目标数量)。
    """
    port, token = get_active_server_info(log_path)
    if not port or not token:
        return 0, len(projects_map)

    success_cnt = 0
    for pid, (pname, raw_p) in projects_map.items():
        ok, _ = update_project_via_rpc(port, token, pid, pname, raw_p)
        if ok:
            success_cnt += 1
    return success_cnt, len(projects_map)
