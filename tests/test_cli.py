"""
CLI 命令行接口集成测试.

测试环境自动探测、--help、--dry-run、--backup-only、--list-backups 与 --data-dir 参数调用。
"""

from unittest.mock import patch
from antigravity_rescuer.cli import main, auto_detect_environment


def test_auto_detect_environment(tmp_path):
    """测试多环境与自定义数据目录自动探测。"""
    # 1. 默认探测
    base_dir, conv_dir, config_proj_dir, target_dirs = auto_detect_environment()
    assert ".gemini" in base_dir
    assert ".gemini" in conv_dir
    assert len(target_dirs) >= 4

    # 2. 自定义目录探测
    custom_dir = tmp_path / "custom_antigravity"
    custom_dir.mkdir()
    base_custom, conv_custom, _, _ = auto_detect_environment(str(custom_dir))
    assert base_custom == str(custom_dir)
    assert conv_custom == str(custom_dir / "conversations")


def test_cli_dry_run(capsys):
    """测试 CLI --dry-run 参数输出。"""
    with patch("sys.argv", ["antigravity-rescuer", "--dry-run"]):
        main()
    captured = capsys.readouterr()
    assert "Antigravity 会话与项目深度诊断报告" in captured.out
    assert "诊断结论" in captured.out


def test_cli_list_backups(capsys):
    """测试 CLI --list-backups 参数输出。"""
    with patch("sys.argv", ["antigravity-rescuer", "--list-backups"]):
        main()
    captured = capsys.readouterr()
    assert "历史备份清单" in captured.out


def test_cli_backup_only(tmp_path, capsys):
    """测试 CLI --backup-only 参数输出。"""
    with patch("sys.argv", ["antigravity-rescuer", "--backup-only"]):
        with patch("antigravity_rescuer.cli.create_atomic_backup", return_value=str(tmp_path / "backup_test")):
            main()
    captured = capsys.readouterr()
    assert "备份成功创建至" in captured.out
