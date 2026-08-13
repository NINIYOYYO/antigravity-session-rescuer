"""
SQLite 数据库深度取证与 AI 标题提取模块.

本模块负责：
1. 对历史数据库进行完整性检查与 WAL 恢复；
2. 解析 trajectory_metadata_blob，精确判定是否为后台子代理（Subagent）；
3. 动态提取工作区路径并匹配/推导项目实体；
4. 深度解析 steps 表（step_type=23/14），提取 AI 原生总结标题并过滤乱码与 UUID。
"""

import os
import re
import sqlite3

from antigravity_rescuer.project_normalizer import (
    get_or_create_project_for_path,
    uri_to_local_path,
)
from antigravity_rescuer.proto_compiler import parse_proto_raw


def is_clean_title(title: str | None) -> bool:
    """
    严格校验标题文本是否为人类可读的高质量自然语言标题。

    Args:
        title (Optional[str]): 待校验的标题文本。

    Returns:
        bool: True 表示标题有效可读，False 表示属于噪音或乱码。
    """
    if not title or len(title.strip()) < 2:
        return False
    clean = title.strip()
    bad_prefixes = (
        "mcp(",
        "command(",
        "read_file(",
        "write_file(",
        "file://",
        "<",
        "{",
        "uv run",
        ".\\",
        "python",
        "http://",
        "https://",
        "$",
        "%",
        "@",
        "\\",
    )
    if any(clean.startswith(p) for p in bad_prefixes):
        return False
    if re.match(r"^\$?[0-9a-fA-F-]{32,40}", clean):
        return False
    return True


def parse_proto_strings(blob: bytes) -> dict[int, list[str]]:
    """
    递归解析 Protobuf 二进制数据中的所有文本字符串，并按字段编号归类。

    Args:
        blob (bytes): Protobuf 二进制数据。

    Returns:
        Dict[int, List[str]]: 字段编号到提取出的字符串列表。
    """
    idx = 0
    res: dict[int, list[str]] = {}
    while idx < len(blob):
        tag = 0
        shift = 0
        while idx < len(blob):
            b = blob[idx]
            idx += 1
            tag |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        field_num = tag >> 3
        wire_type = tag & 0x07
        if field_num == 0:
            break
        if wire_type == 0:
            while idx < len(blob):
                b = blob[idx]
                idx += 1
                if not (b & 0x80):
                    break
        elif wire_type == 2:
            length = 0
            shift = 0
            while idx < len(blob):
                b = blob[idx]
                idx += 1
                length |= (b & 0x7F) << shift
                if not (b & 0x80):
                    break
                shift += 7
            if idx + length > len(blob):
                break
            data = blob[idx : idx + length]
            idx += length
            try:
                s = data.decode("utf-8")
                if (
                    len(s.strip()) >= 2
                    and not s.startswith("file://")
                    and not re.match(r"^[0-9a-fA-F-]{36}$", s)
                ):
                    res.setdefault(field_num, []).append(s.strip())
            except Exception:
                pass
            sub = parse_proto_strings(data)
            for k, v in sub.items():
                res.setdefault(k, []).extend(v)
        elif wire_type == 1:
            idx += 8
        elif wire_type == 5:
            idx += 4
        else:
            break
    return res


def extract_pure_title(db_path: str) -> str:
    """
    从 SQLite 会话数据库中深度提取 AI 原生标题或用户首句提问。

    Args:
        db_path (str): 数据库文件的绝对路径。

    Returns:
        str: 提取并清洗后的规范标题 (最长 35 字符)。
    """
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # 1. 优先提取 step_type = 23 (AI Summary)
        cur.execute("SELECT step_payload FROM steps WHERE step_type = 23 ORDER BY idx ASC")
        for r in cur.fetchall():
            if r and r[0]:
                p_map = parse_proto_strings(r[0])
                if 4 in p_map:
                    for title in p_map[4]:
                        clean = re.sub(r"[\r\n\t]+", " ", title).strip()
                        if is_clean_title(clean):
                            conn.close()
                            return clean[:35]

        # 2. 次选 step_type = 14 (用户首句 Query)
        cur.execute("SELECT step_payload FROM steps WHERE step_type = 14 ORDER BY idx ASC")
        for r in cur.fetchall():
            if r and r[0]:
                p_map = parse_proto_strings(r[0])
                for _, str_list in p_map.items():
                    for title in str_list:
                        clean = re.sub(r"[\r\n\t]+", " ", title).strip()
                        if is_clean_title(clean):
                            conn.close()
                            return clean[:35]

        # 3. 扫描前 10 步包含中文的段落
        cur.execute("SELECT step_payload FROM steps ORDER BY idx ASC LIMIT 10")
        for r in cur.fetchall():
            if r and r[0]:
                p_map = parse_proto_strings(r[0])
                for _, str_list in p_map.items():
                    for title in str_list:
                        clean = re.sub(r"[\r\n\t]+", " ", title).strip()
                        if is_clean_title(clean) and any(
                            "\u4e00" <= c <= "\u9fa5" for c in clean
                        ):
                            conn.close()
                            return clean[:35]

        conn.close()
    except Exception:
        pass
    return "对话历史"


def is_subagent_trajectory(db_path: str) -> bool:
    """
    通过解析 trajectory_metadata_blob 判断该数据库是否属于后台子代理 (Subagent)。

    Args:
        db_path (str): 数据库文件路径。

    Returns:
        bool: True 表示是子代理轨迹，False 表示是独立主会话。
    """
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id='main'")
        row = cur.fetchone()
        blob = row[0] if row else b""
        conn.close()

        if not blob:
            return False

        fields = parse_proto_raw(blob)
        return 4 in fields or 5 in fields
    except Exception:
        return False


def extract_workspace_path_from_blob(blob_data: bytes) -> str:
    """
    从 trajectory_metadata_blob 中直接提取工作区本地文件路径。

    Args:
        blob_data (bytes): 数据库中存储的 Protobuf 载荷。

    Returns:
        str: 解析出的工作区绝对路径，若无则返回空字符串。
    """
    fields = parse_proto_raw(blob_data)
    if 7 in fields:
        uri = fields[7][0].decode("utf-8", errors="ignore")
        if uri.startswith("file://"):
            return uri_to_local_path(uri)

    if 1 in fields:
        sub_fields = parse_proto_raw(fields[1][0])
        if 1 in sub_fields:
            uri = sub_fields[1][0].decode("utf-8", errors="ignore")
            if uri.startswith("file://"):
                return uri_to_local_path(uri)

    return ""


def check_and_repair_sqlite_db(db_path: str) -> bool:
    """
    执行 SQLite 数据库完整性检查与 WAL 截断归档。

    Args:
        db_path (str): 数据库文件绝对路径。

    Returns:
        bool: True 表示完整可用，False 表示损坏不可修复。
    """
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        if not row or row[0] != "ok":
            conn.close()
            return False

        cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
        return True
    except Exception:
        return False


def get_conversation_step_count(db_path: str) -> int:
    """
    获取指定会话数据库中的有效步数统计。

    Args:
        db_path (str): 数据库路径。

    Returns:
        int: 步数总量。
    """
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM steps")
        cnt = cur.fetchone()[0]
        conn.close()
        return cnt
    except Exception:
        return 0


def scan_conversation_directory(
    conv_dir: str,
    projects_map: dict[str, tuple[str, str]],
) -> tuple[list[dict[str, str]], int, int]:
    """
    全量扫描会话目录，动态提取工作区路径并推导项目归属。

    Args:
        conv_dir (str): 会话数据库存放目录。
        projects_map (Dict[str, Tuple[str, str]]): 项目字典（动态填充更新）。

    Returns:
        Tuple[List[Dict[str, str]], int, int]:
            - 主会话元数据列表
            - 发现的主会话总数
            - 自动收拢的子代理总数
    """
    if not os.path.exists(conv_dir):
        return [], 0, 0

    main_sessions = []
    subagent_count = 0

    files = [f for f in os.listdir(conv_dir) if f.endswith(".db")]
    for f in files:
        cid = f[:-3]
        fpath = os.path.join(conv_dir, f)

        if not check_and_repair_sqlite_db(fpath):
            continue

        if is_subagent_trajectory(fpath):
            subagent_count += 1
            continue

        title = extract_pure_title(fpath)
        step_cnt = get_conversation_step_count(fpath)
        mtime = int(os.path.getmtime(fpath))

        conn = sqlite3.connect(fpath)
        cur = conn.cursor()
        cur.execute("SELECT data FROM trajectory_metadata_blob WHERE id='main'")
        row = cur.fetchone()
        blob_data = row[0] if row else b""
        conn.close()

        raw_workspace_path = extract_workspace_path_from_blob(blob_data)
        pid, pname = get_or_create_project_for_path(raw_workspace_path, projects_map)

        main_sessions.append(
            {
                "cid": cid,
                "db_path": fpath,
                "title": title,
                "step_count": str(step_cnt),
                "mtime": str(mtime),
                "project_id": pid,
                "project_name": pname,
                "project_path": raw_workspace_path,
            }
        )

    return main_sessions, len(main_sessions), subagent_count
