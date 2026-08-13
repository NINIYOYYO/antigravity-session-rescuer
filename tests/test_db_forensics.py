"""
数据库取证与标题提取单元测试.

测试 is_clean_title 过滤逻辑、SQLite 完整性校验与模拟会话数据库读取。
"""

import sqlite3

from antigravity_rescuer.db_forensics import (
    check_and_repair_sqlite_db,
    extract_pure_title,
    is_clean_title,
    is_subagent_trajectory,
)
from antigravity_rescuer.proto_compiler import encode_field


def test_is_clean_title():
    """测试标题有效性过滤器。"""
    assert is_clean_title("调整磁盘分区空间") is True
    assert is_clean_title("Fix video subtitle parser") is True
    assert is_clean_title("") is False
    assert is_clean_title("a") is False
    assert is_clean_title("mcp(read_file(...))") is False
    assert is_clean_title("command(python test.py)") is False
    assert is_clean_title("1a31b76f-ccfa-485a-a433-f9e4bb5f466c") is False
    assert is_clean_title("$1a31b76f-ccfa-485a-a433-f9e4bb5f466c") is False


def test_sqlite_db_forensics(tmp_path):
    """测试模拟 SQLite 会话数据库的完整性与标题提取。"""
    db_file = tmp_path / "test_session.db"
    conn = sqlite3.connect(str(db_file))
    cur = conn.cursor()

    # 创建标准表
    cur.execute("CREATE TABLE steps (idx INTEGER, step_type INTEGER, step_payload BLOB)")
    cur.execute("CREATE TABLE trajectory_metadata_blob (id TEXT, data BLOB)")

    # 插入主会话元数据 (Field 1 = WorkspaceMetadata, Field 18 = ProjectId)
    f1 = encode_field(1, 2, b"file:///c:/test_proj")
    f18 = encode_field(18, 2, b"test-project-uuid")
    cur.execute(
        "INSERT INTO trajectory_metadata_blob VALUES ('main', ?)",
        (f1 + f18,),
    )

    # 插入 step_type = 23 (AI Title Payload, Field 4 = Title)
    title_field = encode_field(4, 2, "优化图像渲染性能".encode())
    cur.execute(
        "INSERT INTO steps VALUES (1, 23, ?)",
        (title_field,),
    )
    conn.commit()
    conn.close()

    # 校验完整性
    assert check_and_repair_sqlite_db(str(db_file)) is True

    # 校验主会话判定
    assert is_subagent_trajectory(str(db_file)) is False

    # 校验标题提取
    extracted = extract_pure_title(str(db_file))
    assert extracted == "优化图像渲染性能"
