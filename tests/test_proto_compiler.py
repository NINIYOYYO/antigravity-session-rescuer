"""
Protobuf 编译器单元测试.

测试 Varint 编解码、Timestamp 生成、WorkspaceMetadata 结构及单个 Summary 记录的二进制序列化。
"""

import pytest

from antigravity_rescuer.proto_compiler import (
    build_single_summary_record,
    build_workspace_metadata,
    decode_varint,
    encode_varint,
    make_timestamp,
    parse_proto_raw,
)


def test_varint_encode_decode():
    """测试不同范围整数的 Varint 编解码一致性。"""
    test_cases = [0, 1, 127, 128, 300, 65535, 123456789]
    for val in test_cases:
        encoded = encode_varint(val)
        decoded, new_idx = decode_varint(encoded, 0)
        assert decoded == val
        assert new_idx == len(encoded)


def test_varint_negative_raises():
    """测试 Varint 对负数输入抛出 ValueError。"""
    with pytest.raises(ValueError):
        encode_varint(-1)


def test_make_timestamp():
    """测试 Protobuf Timestamp 结构。"""
    ts_bytes = make_timestamp(1723500000, 500)
    assert len(ts_bytes) > 0
    # Field 1 tag: 1 << 3 | 0 = 8 -> 0x08
    assert ts_bytes[0] == 0x08


def test_build_workspace_metadata():
    """测试 WorkspaceMetadata 二进制生成。"""
    uri = "file:///c:/Users/Test/Documents/project"
    res = build_workspace_metadata(uri)
    assert len(res) > 0
    assert uri.encode("utf-8") in res
    assert b"master" in res


def test_build_single_summary_record():
    """测试完整单个 Summary 记录生成与第一层解析。"""
    cid = "11111111-2222-3333-4444-555555555555"
    title = "测试会话标题"
    step_count = 15
    mtime = 1723500000
    target_unencoded = "file:///c:/project"
    target_encoded = "file:///c%3A/project"
    pid = "aaaa-bbbb-cccc"

    record_bytes = build_single_summary_record(
        cid=cid,
        title=title,
        step_count=step_count,
        mtime=mtime,
        target_unencoded_uri=target_unencoded,
        target_encoded_uri=target_encoded,
        target_pid=pid,
    )

    assert len(record_bytes) > 0
    # 顶层必须是 Field 1 (Repeated)
    assert record_bytes[0] == 0x0A

    # 解析第一层
    parsed = parse_proto_raw(record_bytes)
    assert 1 in parsed
    inner = parsed[1][0]
    assert cid.encode("utf-8") in inner
    assert title.encode("utf-8") in inner
