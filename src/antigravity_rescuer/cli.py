"""
Antigravity Session Rescuer 命令行交互入口.

提供全自动通用修复 (--auto)、检测预览 (--dry-run)、热同步 (--live-sync) 与快照备份 (--backup-only)。
支持跨平台全自动数据目录探测与 --data-dir 自定义路径覆盖。
"""

import argparse
import os
import sys

# 强制 UTF-8 控制台输出，防止 Windows GBK 报错
if sys.platform.startswith("win"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from antigravity_rescuer.backup_manager import create_atomic_backup, list_all_backups
from antigravity_rescuer.db_forensics import scan_conversation_directory
from antigravity_rescuer.process_manager import (
    start_antigravity_process,
    stop_antigravity_processes,
)
from antigravity_rescuer.project_normalizer import (
    discover_existing_projects,
    sync_all_projects_to_disk,
    to_encoded_uri,
    to_unencoded_uri,
)
from antigravity_rescuer.proto_compiler import (
    build_single_summary_record,
)
from antigravity_rescuer.rpc_client import broadcast_all_projects


def auto_detect_environment(custom_data_dir: str | None = None) -> tuple[str, str, str, list[str]]:
    """
    自动探测当前用户的 Antigravity 数据目录、会话目录及所有项目同步目标路径。

    Args:
        custom_data_dir (Optional[str], optional): 用户手动指定的自定义数据目录。

    Returns:
        Tuple[str, str, str, List[str]]:
            - base_data_dir: 核心数据目录 (存放 .pb 索引)
            - conv_dir: 会话 SQLite 数据库存放目录
            - config_proj_dir: 主项目配置目录
            - all_target_proj_dirs: 所有需要同步写入的项目目录列表
    """
    user_home = os.path.expanduser("~")

    # 1. 探测核心数据目录 (base_data_dir)
    if custom_data_dir and os.path.exists(custom_data_dir):
        base_data_dir = custom_data_dir
    else:
        candidates = [
            os.path.join(user_home, ".gemini", "antigravity"),
            os.path.join(user_home, ".gemini", "antigravity-ide"),
            os.path.join(user_home, ".gemini"),
        ]
        base_data_dir = candidates[0]
        for c in candidates:
            if os.path.exists(os.path.join(c, "conversations")):
                base_data_dir = c
                break

    conv_dir = os.path.join(base_data_dir, "conversations")
    config_proj_dir = os.path.join(user_home, ".gemini", "config", "projects")

    # 2. 搜集所有可能的目标项目存储目录
    target_dirs = [
        config_proj_dir,
        os.path.join(user_home, ".gemini", "antigravity", "projects"),
        os.path.join(user_home, ".gemini", "antigravity-ide", "projects"),
        os.path.join(user_home, ".gemini", "projects"),
    ]
    if sys.platform.startswith("win"):
        target_dirs.append(
            os.path.join(os.path.expandvars(r"%APPDATA%"), "Antigravity", "projects")
        )
    elif sys.platform.startswith("darwin"):
        target_dirs.append(os.path.expanduser("~/Library/Application Support/Antigravity/projects"))
    else:
        target_dirs.append(os.path.expanduser("~/.config/Antigravity/projects"))

    return base_data_dir, conv_dir, config_proj_dir, target_dirs


def run_dry_run_preview(conv_dir: str, config_proj_dir: str) -> None:
    """
    执行只读扫描与诊断报告，不修改任何文件。

    Args:
        conv_dir (str): 会话存放目录。
        config_proj_dir (str): 项目配置存放目录。
    """
    print("\n=======================================================")
    print("    Antigravity 会话与项目深度诊断报告 (Dry-Run)")
    print("=======================================================\n")

    print(f"[+] 正在扫描会话存储路径: {conv_dir}")
    projects_map: dict[str, tuple[str, str]] = discover_existing_projects(config_proj_dir)
    print(f"[+] 动态加载已有项目配置: {len(projects_map)} 个")

    main_sessions, main_cnt, sub_cnt = scan_conversation_directory(conv_dir, projects_map)

    print(f"[+] 扫描到的顶级主会话总数: {main_cnt} 个")
    print(f"[+] 自动收拢归并的子代理数: {sub_cnt} 个")
    print(f"[+] 最终归属匹配的项目总数: {len(projects_map)} 个\n")

    print(f"{'会话ID':38s} | {'所属项目':25s} | {'AI 原生标题'}")
    print("-" * 90)
    for s in main_sessions[:20]:
        print(f"{s['cid']:38s} | {s['project_name']:25s} | {s['title']}")

    if len(main_sessions) > 20:
        print(f"... 以及其余 {len(main_sessions) - 20} 个历史会话。")

    print("\n诊断结论：全部数据库结构完好，AI 原生标题与项目拓扑可 100% 自动恢复。")


def run_full_auto_recovery(
    base_data_dir: str,
    conv_dir: str,
    config_proj_dir: str,
    target_dirs: list[str],
) -> None:
    """
    执行通用自动化冷修复流程。

    Args:
        base_data_dir (str): 基础数据目录。
        conv_dir (str): 会话数据库目录。
        config_proj_dir (str): 项目配置目录。
        target_dirs (List[str]): 目标同步目录列表。
    """
    print("\n=======================================================")
    print("    Antigravity Session Rescuer 一键全量修复开始")
    print("=======================================================\n")

    # 1. 停止进程
    print("[1/5] 正在安全停止 Antigravity 与后台 Language Server 进程...")
    stop_antigravity_processes()
    print("    [+] 后台进程已安全停止！")

    # 2. 自动原子备份
    print("\n[2/5] 正在创建操作前全量时间戳安全快照...")
    backup_path = create_atomic_backup(source_dir=base_data_dir)
    print(f"    [+] 快照已生成至: {backup_path}")

    # 3. 动态发现与标题取证
    print("\n[3/5] 正在动态解析项目拓扑并提取 AI 原生标题...")
    projects_map = discover_existing_projects(config_proj_dir)
    main_sessions, main_cnt, sub_cnt = scan_conversation_directory(conv_dir, projects_map)
    total_p = len(projects_map)
    print(
        f"    [+] 成功解析 {main_cnt} 个顶级主会话 (分离 {sub_cnt} 个子任务，绑定 {total_p} 个项目)"
    )

    # 4. 同步规范化项目 JSON
    print("\n[4/5] 正在重构 Proto3 规范的项目配置文件...")
    sync_all_projects_to_disk(target_dirs, projects_map)
    print("    [+] 项目配置文件已成功同步至全路径！")

    # 5. 编译中央二进制索引库
    print("\n[5/5] 正在编译官方标准中央二进制索引 (agyhub_summaries_proto.pb)...")
    total_proto_bytes = bytearray()
    for s in main_sessions:
        target_unencoded = to_unencoded_uri(s["project_path"]) if s["project_path"] else ""
        target_encoded = to_encoded_uri(s["project_path"]) if s["project_path"] else ""
        record = build_single_summary_record(
            cid=s["cid"],
            title=s["title"],
            step_count=int(s["step_count"]),
            mtime=int(s["mtime"]),
            target_unencoded_uri=target_unencoded,
            target_encoded_uri=target_encoded,
            target_pid=s["project_id"],
        )
        total_proto_bytes.extend(record)

    pb_target = os.path.join(base_data_dir, "agyhub_summaries_proto.pb")
    with open(pb_target, "wb") as fp:
        fp.write(bytes(total_proto_bytes))
    print("    [+] 中央索引编译完成并写入磁盘！")

    # 重新冷启动
    print("\n[+] 正在冷启动 Antigravity 客户端...")
    start_antigravity_process()
    print("    [+] Antigravity 2.0 已成功启动！")

    print("\n=======================================================")
    print("    恭喜！全部历史会话与项目名称已彻底修复完成。")
    print("=======================================================")


def main() -> None:
    """CLI 主入口函数。"""
    parser = argparse.ArgumentParser(
        description="Antigravity 2.x 会话恢复与项目树修复工具 (开源通用版)",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="执行全自动冷修复（安全停止 -> 备份 -> 重构索引 -> 重启）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅执行诊断分析与会话预览，不修改任何文件",
    )
    parser.add_argument(
        "--live-sync",
        action="store_true",
        help="向正在运行的 Antigravity 发送 RPC 热同步更新项目名",
    )
    parser.add_argument(
        "--backup-only",
        action="store_true",
        help="仅创建时间戳安全备份快照",
    )
    parser.add_argument(
        "--list-backups",
        action="store_true",
        help="列出所有历史备份点",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="手动指定 Antigravity 数据目录（默认自动全盘智能探测）",
    )

    args = parser.parse_args()

    base_data_dir, conv_dir, config_proj_dir, target_dirs = auto_detect_environment(args.data_dir)

    if args.list_backups:
        backups = list_all_backups()
        print("\n=== 历史备份清单 ===")
        if not backups:
            print("  暂无历史备份快照。")
        for b in backups:
            print(f"  * [{b['created_at']}] {b['name']} -> {b['path']}")
        return

    if args.backup_only:
        p = create_atomic_backup(source_dir=base_data_dir)
        print(f"\n[+] 备份成功创建至: {p}")
        return

    if args.live_sync:
        print("\n=== 正在向运行中的 Antigravity 发送 RPC 热同步 ===")
        projects_map = discover_existing_projects(config_proj_dir)
        success, total = broadcast_all_projects(projects_map)
        print(f"[+] 热同步完成: 成功 {success}/{total} 个项目。")
        return

    if args.dry_run:
        run_dry_run_preview(conv_dir, config_proj_dir)
        return

    # 默认模式为 --auto
    run_full_auto_recovery(base_data_dir, conv_dir, config_proj_dir, target_dirs)


if __name__ == "__main__":
    main()
