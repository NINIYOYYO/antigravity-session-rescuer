"""
自动化时间戳备份与回滚管理模块.

本模块负责：
1. 在对 Antigravity 目录执行任何写操作前，自动创建完整时间戳快照；
2. 包含 SQLite 会话数据库、中央二进制索引与项目配置；
3. 支持列出历史备份点。
"""

import os
import shutil
import time
from typing import List, Dict, Optional


def create_atomic_backup(
    source_dir: Optional[str] = None,
    backup_root: Optional[str] = None,
) -> str:
    """
    为 Antigravity 数据目录创建带精确时间戳的完整原子备份。

    Args:
        source_dir (Optional[str], optional): Antigravity 数据目录。
            默认为 None (~/.gemini/antigravity)。
        backup_root (Optional[str], optional): 备份存储根目录。
            默认为 None (~/.gemini/antigravity/backups)。

    Returns:
        str: 成功生成的备份目录绝对路径。
    """
    user_home = os.path.expandvars(r"%USERPROFILE%")
    if not source_dir:
        source_dir = os.path.join(user_home, ".gemini", "antigravity")
    if not backup_root:
        backup_root = os.path.join(user_home, ".gemini", "antigravity_rescuer_backups")

    timestamp_str = time.strftime("%Y%m%d_%H%M%S")
    target_backup_dir = os.path.join(backup_root, f"backup_{timestamp_str}")
    os.makedirs(target_backup_dir, exist_ok=True)

    # 1. 备份 conversations 目录
    conv_src = os.path.join(source_dir, "conversations")
    if os.path.exists(conv_src):
        shutil.copytree(conv_src, os.path.join(target_backup_dir, "conversations"))

    # 2. 备份 agyhub_summaries_proto.pb
    pb_src = os.path.join(source_dir, "agyhub_summaries_proto.pb")
    if os.path.exists(pb_src):
        shutil.copy2(pb_src, target_backup_dir)

    # 3. 备份 config/projects 目录
    proj_src = os.path.join(user_home, ".gemini", "config", "projects")
    if os.path.exists(proj_src):
        shutil.copytree(proj_src, os.path.join(target_backup_dir, "config_projects"))

    return target_backup_dir


def list_all_backups(backup_root: Optional[str] = None) -> List[Dict[str, str]]:
    """
    扫描并列出所有历史备份点。

    Args:
        backup_root (Optional[str], optional): 备份根目录。

    Returns:
        List[Dict[str, str]]: 包含备份路径、创建时间与大小的字典列表。
    """
    if not backup_root:
        backup_root = os.path.join(
            os.path.expandvars(r"%USERPROFILE%"),
            ".gemini",
            "antigravity_rescuer_backups",
        )

    if not os.path.exists(backup_root):
        return []

    backups = []
    for item in sorted(os.listdir(backup_root), reverse=True):
        full_p = os.path.join(backup_root, item)
        if os.path.isdir(full_p) and item.startswith("backup_"):
            mtime = time.strftime(
                "%Y-%m-%d %H:%M:%S",
                time.localtime(os.path.getmtime(full_p)),
            )
            backups.append(
                {
                    "name": item,
                    "path": full_p,
                    "created_at": mtime,
                }
            )
    return backups
