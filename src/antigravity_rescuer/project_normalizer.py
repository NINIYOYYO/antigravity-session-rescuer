"""
项目实体规范化与动态发现模块.

本模块负责：
1. 自动扫描并发现任意用户电脑上的现有项目实体；
2. 为尚未注册的本地工作区路径自动推导规范的项目实体与确定性 UUID；
3. 生成严格符合 Google protojson 规范的无冲突项目字典。
"""

import json
import os
import sys
import uuid
from urllib.parse import quote, unquote


def to_encoded_uri(raw_path: str) -> str:
    """
    将本地路径转换为标准转义 URI 格式 (file:///d%3A/path 或 file:///path)。

    Args:
        raw_path (str): 本地磁盘路径。

    Returns:
        str: 规范化后的转义 URI 字符串。
    """
    p = raw_path.replace("\\", "/")
    p = p.removeprefix("file:///")
    if len(p) >= 2 and p[1] in (":", "%"):
        drive = p[0].lower()
        if p[1] == ":":
            rest = quote(unquote(p[2:]), safe="/").lstrip("/")
            return f"file:///{drive}%3A/{rest}"
        elif p[1:4].lower() == "%3a":
            rest = quote(unquote(p[4:]), safe="/").lstrip("/")
            return f"file:///{drive}%3A/{rest}"
    return f"file:///{p.lstrip('/')}"


def to_unencoded_uri(raw_path: str) -> str:
    """
    将本地路径转换为未转义 URI 格式 (file:///d:/path)。

    Args:
        raw_path (str): 本地磁盘路径。

    Returns:
        str: 未转义 URI 字符串。
    """
    encoded = to_encoded_uri(raw_path)
    return encoded.replace("%3A", ":").replace("%3a", ":")


def uri_to_local_path(uri: str) -> str:
    """
    将 file:/// URI 逆向解析为本地操作系统原生路径。

    Args:
        uri (str): file:/// URI 字符串。

    Returns:
        str: 本地绝对路径。
    """
    if uri.startswith("file:///"):
        uri = uri[len("file:///") :]
    decoded = unquote(uri)
    if len(decoded) >= 2 and decoded[1] == ":":
        if sys.platform.startswith("win"):
            return decoded.replace("/", "\\")
        return decoded
    return decoded


def build_proto3_project_dict(pid: str, pname: str, raw_path: str) -> dict[str, object]:
    """
    构建符合 Go protojson 严格反序列化要求的纯净 Project 字典。

    Args:
        pid (str): 项目唯一 UUID。
        pname (str): 项目展示名称。
        raw_path (str): 项目本地磁盘路径。

    Returns:
        Dict[str, object]: 符合 Proto3 标准的字典结构。
    """
    encoded_uri = to_encoded_uri(raw_path)
    return {
        "id": pid,
        "name": pname,
        "isWorkspaceOnly": False,
        "updatedAt": "2026-08-14T02:00:00.000000000Z",
        "settings": {"fileAccessPolicy": "AGENT_SETTING_POLICY_ALLOW"},
        "projectResources": {
            "resources": [
                {
                    "gitFolder": {
                        "folderUri": encoded_uri,
                        "defaultBranch": "master",
                    }
                }
            ]
        },
    }


def discover_existing_projects(config_proj_dir: str) -> dict[str, tuple[str, str]]:
    """
    自动从指定配置目录中动态读取并发现所有现有的正式项目配置。

    Args:
        config_proj_dir (str): 项目配置存放目录 (~/.gemini/config/projects)。

    Returns:
        Dict[str, Tuple[str, str]]: 项目 ID 到 (项目名称, 本地路径) 的映射字典。
    """
    projects_map: dict[str, tuple[str, str]] = {}
    if not os.path.exists(config_proj_dir):
        return projects_map

    for f in os.listdir(config_proj_dir):
        if not f.endswith(".json") or f == "outside-of-project.json":
            continue
        pid = f[:-5]
        fpath = os.path.join(config_proj_dir, f)
        try:
            with open(fpath, encoding="utf-8", errors="ignore") as fp:
                data = json.load(fp)
            pname = data.get("name", pid)
            raw_path = ""
            resources = data.get("projectResources", {}).get("resources", [])
            if resources:
                res_obj = resources[0]
                git_folder = res_obj.get("gitFolder", {})
                uri = git_folder.get("folderUri") or res_obj.get("folderUri", "")
                if uri:
                    raw_path = uri_to_local_path(uri)
            projects_map[pid] = (pname, raw_path)
        except Exception:
            pass

    return projects_map


def get_or_create_project_for_path(
    folder_path: str,
    projects_map: dict[str, tuple[str, str]],
) -> tuple[str, str]:
    """
    根据工作区路径查找对应项目，若不存在则根据文件夹名跨平台动态推导新项目实体。

    Args:
        folder_path (str): 目标工作区本地路径。
        projects_map (dict[str, tuple[str, str]]): 当前已知项目映射表。

    Returns:
        tuple[str, str]: (项目ID, 项目名称)。
    """
    if not folder_path:
        return "outside-of-project", "Outside of Project"

    # 跨平台路径统一正斜杠匹配
    norm_key = folder_path.replace("\\", "/").rstrip("/").lower()
    for pid, (pname, raw_p) in projects_map.items():
        if raw_p and raw_p.replace("\\", "/").rstrip("/").lower() == norm_key:
            return pid, pname

    # 跨平台稳健提取文件夹名称
    clean_p = folder_path.replace("\\", "/").rstrip("/")
    folder_name = clean_p.split("/")[-1] if "/" in clean_p else clean_p
    folder_name = folder_name or "Project"

    deterministic_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, folder_path))
    projects_map[deterministic_uuid] = (folder_name, folder_path)
    return deterministic_uuid, folder_name


def sync_all_projects_to_disk(
    target_dirs: list[str],
    projects_map: dict[str, tuple[str, str]],
) -> int:
    """
    将规范化后的项目配置批量写入指定的目标目录列表中。

    Args:
        target_dirs (List[str]): 目标存储目录列表。
        projects_map (Dict[str, Tuple[str, str]]): 项目映射表。

    Returns:
        int: 成功写入的文件总数。
    """
    written_count = 0
    for target_dir in target_dirs:
        os.makedirs(target_dir, exist_ok=True)
        for pid, (pname, raw_p) in projects_map.items():
            pdata = build_proto3_project_dict(pid, pname, raw_p)
            pfile = os.path.join(target_dir, f"{pid}.json")
            with open(pfile, "w", encoding="utf-8") as fp:
                json.dump(pdata, fp, indent=2, ensure_ascii=False)
            written_count += 1
    return written_count
