"""
Protobuf 编译与中央索引生成模块.

本模块实现纯 Python 零依赖的 Protobuf Varint 与 Length-delimited 编解码，
负责将扫描解析出的主会话元数据编译为官方标准格式的 `agyhub_summaries_proto.pb`。
"""

from typing import Dict, List


def encode_varint(value: int) -> bytes:
    """
    将整数编码为标准 Protobuf Varint 字节流。

    Args:
        value (int): 待编码的非负整数。

    Returns:
        bytes: Varint 编码后的二进制字节流。

    Raises:
        ValueError: 当传入的整数为负数时抛出。
    """
    if value < 0:
        raise ValueError(f"Varint 仅支持非负整数，收到负数: {value}")
    res = bytearray()
    while value > 0x7F:
        res.append((value & 0x7F) | 0x80)
        value >>= 7
    res.append(value & 0x7F)
    return bytes(res)


def decode_varint(blob: bytes, start_idx: int = 0) -> tuple[int, int]:
    """
    从二进制流中解码单个 Protobuf Varint。

    Args:
        blob (bytes): 包含 Varint 数据的二进制流。
        start_idx (int): 起始字节偏移量。

    Returns:
        tuple[int, int]: 解码出的整数值与读取完毕后的新偏移量。
    """
    val = 0
    shift = 0
    idx = start_idx
    while idx < len(blob):
        b = blob[idx]
        idx += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return val, idx


def encode_field(field_num: int, wire_type: int, data: bytes) -> bytes:
    """
    将字段编号、WireType 与数据内容封装为 Protobuf Tag + Payload 格式。

    Args:
        field_num (int): Protobuf 字段编号 (1-indexed)。
        wire_type (int): Protobuf 线路类型 (0=Varint, 2=Length-delimited 等)。
        data (bytes): 字段的原始二进制数据。

    Returns:
        bytes: 编码后的完整字段数据。
    """
    tag = (field_num << 3) | wire_type
    if wire_type == 2:
        return encode_varint(tag) + encode_varint(len(data)) + data
    elif wire_type in (0, 1, 5):
        return encode_varint(tag) + data
    return b""


def make_timestamp(seconds: int, nanos: int = 0) -> bytes:
    """
    生成符合 Google Protobuf 标准的 Timestamp 二进制子消息。

    Args:
        seconds (int): 秒级 Unix 时间戳。
        nanos (int, optional): 纳秒偏移量。默认为 0。

    Returns:
        bytes: Timestamp 子消息的二进制字节。
    """
    f1 = encode_field(1, 0, encode_varint(seconds))
    f2 = encode_field(2, 0, encode_varint(nanos))
    return f1 + f2


def build_workspace_metadata(folder_unencoded_uri: str) -> bytes:
    """
    构建符合 Antigravity 2.0 规范的 WorkspaceMetadata (Field 1) 子消息。

    Args:
        folder_unencoded_uri (str): 未转义的工作区 URI (例如 'file:///d:/project')。

    Returns:
        bytes: WorkspaceMetadata 的二进制内容。
    """
    if not folder_unencoded_uri:
        return b""
    sub1 = encode_field(1, 2, folder_unencoded_uri.encode("utf-8"))
    sub2 = encode_field(2, 2, folder_unencoded_uri.encode("utf-8"))
    sub4 = encode_field(4, 2, b"master")
    return sub1 + sub2 + sub4


def parse_proto_raw(blob: bytes) -> Dict[int, List[bytes]]:
    """
    对 Protobuf 二进制数据进行第一层扁平化解析，提取所有 Length-delimited 字段。

    Args:
        blob (bytes): 原始 Protobuf 二进制数据。

    Returns:
        Dict[int, List[bytes]]: 字段编号到字节列表的映射字典。
    """
    idx = 0
    fields: Dict[int, List[bytes]] = {}
    while idx < len(blob):
        tag, idx = decode_varint(blob, idx)
        field_num = tag >> 3
        wire_type = tag & 0x07
        if field_num == 0:
            break
        if wire_type == 0:
            _, idx = decode_varint(blob, idx)
        elif wire_type == 2:
            length, idx = decode_varint(blob, idx)
            if idx + length > len(blob):
                break
            data = blob[idx : idx + length]
            idx += length
            fields.setdefault(field_num, []).append(data)
        elif wire_type == 1:
            idx += 8
        elif wire_type == 5:
            idx += 4
        else:
            break
    return fields


def build_single_summary_record(
    cid: str,
    title: str,
    step_count: int,
    mtime: int,
    target_unencoded_uri: str,
    target_encoded_uri: str,
    target_pid: str,
) -> bytes:
    """
    编译单个主会话的完整 Summary 索引条目 (Field 1 为 cid，Field 2 为 SummaryBody)。

    Args:
        cid (str): 会话唯一 UUID。
        title (str): 会话的高质量 AI 总结标题。
        step_count (int): 会话包含的总步数。
        mtime (int): 最后修改时间戳 (秒)。
        target_unencoded_uri (str): 标准工作区 URI (如 'file:///c:/project')。
        target_encoded_uri (str): 驱动器转义 URI (如 'file:///c%3A/project')。
        target_pid (str): 所属项目的 UUID。

    Returns:
        bytes: 封装为 Repeated Entry 的完整 Protobuf 字节。
    """
    f1_bytes = build_workspace_metadata(target_unencoded_uri) if target_unencoded_uri else b""
    ts_bytes = make_timestamp(mtime)

    # 组装 trajectory_metadata_blob (Field 17)
    f17_parts = bytearray()
    if f1_bytes:
        f17_parts.extend(encode_field(1, 2, f1_bytes))
    f17_parts.extend(encode_field(2, 2, ts_bytes))
    f17_parts.extend(encode_field(3, 2, cid.encode("utf-8")))
    f17_parts.extend(encode_field(6, 2, cid.encode("utf-8")))
    if target_encoded_uri:
        f17_parts.extend(encode_field(7, 2, target_encoded_uri.encode("utf-8")))
    f17_parts.extend(encode_field(18, 2, target_pid.encode("utf-8")))
    f17_meta_clean = bytes(f17_parts)

    # 组装 SummaryBody
    s1_title = encode_field(1, 2, title.encode("utf-8"))
    s2_step_cnt = encode_field(2, 0, encode_varint(step_count))
    s3_updated = encode_field(3, 2, ts_bytes)
    s4_cid = encode_field(4, 2, cid.encode("utf-8"))
    s5_status = encode_field(5, 0, encode_varint(1))
    s9_ws = encode_field(9, 2, f1_bytes) if f1_bytes else b""
    s10_created = encode_field(10, 2, ts_bytes)
    s15_inner = encode_field(7, 2, ts_bytes)
    s15_status = encode_field(15, 2, s15_inner)
    s16_cnt = encode_field(16, 0, encode_varint(0))
    s17_meta = encode_field(17, 2, f17_meta_clean)
    s22_format = encode_field(22, 0, encode_varint(4))

    summary_body = (
        s1_title
        + s2_step_cnt
        + s3_updated
        + s4_cid
        + s5_status
        + s9_ws
        + s10_created
        + s15_status
        + s16_cnt
        + s17_meta
        + s22_format
    )

    entry_f1 = encode_field(1, 2, cid.encode("utf-8"))
    entry_f2 = encode_field(2, 2, summary_body)
    return encode_field(1, 2, entry_f1 + entry_f2)
