"""
项目规范化与动态发现单元测试.

测试 URI 编解码、Proto3 字典生成、动态项目发现与路径推导。
"""

import json

from antigravity_rescuer.project_normalizer import (
    build_proto3_project_dict,
    discover_existing_projects,
    get_or_create_project_for_path,
    sync_all_projects_to_disk,
    to_encoded_uri,
    to_unencoded_uri,
    uri_to_local_path,
)


def test_uri_encoding_and_decoding():
    """测试 Windows 本地路径到 URI 及逆向解析的一致性。"""
    raw = r"D:\programing\anime_mini_site"
    encoded = to_encoded_uri(raw)
    unencoded = to_unencoded_uri(raw)
    back_path = uri_to_local_path(encoded)

    assert encoded == "file:///d%3A/programing/anime_mini_site"
    assert unencoded == "file:///d:/programing/anime_mini_site"
    assert back_path.lower() == raw.lower()


def test_build_proto3_project_dict():
    """测试生成的 JSON 符合 Proto3 无冲突规范。"""
    pid = "1a31b76f-ccfa-485a-a433-f9e4bb5f466c"
    pname = "gallant-fermi"
    raw_path = r"C:\Users\User\Documents\gallant-fermi"

    pdict = build_proto3_project_dict(pid, pname, raw_path)

    assert pdict["id"] == pid
    assert pdict["name"] == pname
    assert pdict["isWorkspaceOnly"] is False

    # 严禁出现 snake_case 别名
    assert "is_workspace_only" not in pdict
    assert "project_id" not in pdict
    assert "project_name" not in pdict


def test_discover_and_dynamic_creation(tmp_path):
    """测试动态项目发现与未知路径自动推导注册。"""
    config_dir = tmp_path / "config_projects"
    config_dir.mkdir()

    # 创建一个已有项目
    p1_data = build_proto3_project_dict("id-1", "ExistingApp", r"d:\code\existing")
    with open(config_dir / "id-1.json", "w", encoding="utf-8") as f:
        json.dump(p1_data, f)

    # 1. 动态发现
    discovered = discover_existing_projects(str(config_dir))
    assert "id-1" in discovered
    assert discovered["id-1"][0] == "ExistingApp"

    # 2. 对已有路径获取
    pid, pname = get_or_create_project_for_path(r"d:\code\existing", discovered)
    assert pid == "id-1"
    assert pname == "ExistingApp"

    # 3. 对全新路径自动推导
    pid_new, pname_new = get_or_create_project_for_path(r"d:\new_repos\my_awesome_tool", discovered)
    assert pname_new == "my_awesome_tool"
    assert pid_new in discovered


def test_sync_all_projects_to_disk(tmp_path):
    """测试项目文件落盘。"""
    target_dir = str(tmp_path / "projects")
    projects_map = {
        "uuid-1": ("project-1", r"d:\code\p1"),
        "uuid-2": ("project-2", r"d:\code\p2"),
    }
    written = sync_all_projects_to_disk([target_dir], projects_map)
    assert written == 2
