# Antigravity Session Rescuer

<p align="center">
  <a href="README.md">English</a> | <a href="README_zh.md">简体中文</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/Python-3.10+-brightgreen.svg" alt="Python: 3.10+">
  <img src="https://img.shields.io/badge/Package%20Manager-uv-purple.svg" alt="Package Manager: uv">
  <img src="https://img.shields.io/badge/Tests-19%20Passed-success.svg" alt="Tests: 19 Passed">
</p>

**Antigravity Session Rescuer** 是专为 **Google Antigravity 2.x** 打造的纯 Python、零外部二进制编译依赖的工程级会话恢复与取证修复工具。专门解决在大版本升级（1.x 升至 2.x）或异常闪退后导致的**历史会话大面积丢失（仅剩 2~3 个）、会话标题退化为 UUID 乱码、左侧项目文件夹被重置为 `Recovered Project`** 等痛点问题。

---

## 背景与痛点根因

Antigravity 在 2.x 版本对底层存储进行了深度重构，导致常见以下严重故障：
1. **官方迁移器超时截断**：官方自动迁移模块在扫描大量历史数据库（100+ 个）时发生截断，导致只有最后活跃的 2~3 个会话被写入中央二进制索引，其余 100 多个会话被静默遗漏；
2. **AI 原生标题丢失**：原生标题保存在 `steps` 表 `step_type=23/14` 的二进制载荷深处，若未深度反解，标题会降级显示为 UUID 或代码片段；
3. **`Recovered Project` 安全降级**：未有效关联项目实体的会话会被官方强制触发 `newRecoveredProject` 降级策略；
4. **Go `protojson` 反序列化崩溃**：`language_server.exe` 底层严禁下划线与驼峰重复字段（如 `duplicate field is_workspace_only`）及 `oneof` 联合体冲突，导致配置文件被解析器拒绝并持续跌入降级模式。

---

## 核心特性

- **跨系统全自动数据目录探测**：自动识别 Windows / macOS / Linux 用户主目录与 Antigravity 默认数据路径，真正做到 0 配置即开即用。
- **深度数据库取证与 AI 标题提取**：直接解析底层 SQLite `steps` 表 Protobuf 载荷（`step_type=23` 与 `step_type=14`），100% 恢复中英文原生高质量总结标题。
- **主会话与后台子代理（Subagent）拓扑分离**：精准识别 `trajectory_metadata_blob`（Field 4/5），将后台子任务从顶级项目树中剥离，杜绝数十个垃圾占位文件夹。
- **零依赖纯 Python Protobuf 编译器**：纯 Python 实现 Varint 与 Length-delimited 编解码，无需安装 `protoc` 即可直接编译出 100% 合规的 `agyhub_summaries_proto.pb` 中央索引。
- **动态项目发现与零配置推导**：自动发现用户现有项目配置，对全新工作区按目录名自动推导并分配稳定确定性 UUID。
- **Proto3 严格规范化**：消除驼峰/下划线同存引发的 `duplicate field` 崩溃，规范化单一 `gitFolder` 联合体。
- **动态 Connect-RPC 热同步**：从主日志动态嗅探活动端口与 `x-codeium-csrf-token`，热同步更新正在运行的 Antigravity 项目名，无需重启客户端。
- **操作前原子级时间戳快照**：在执行写操作前自动创建完整时间戳备份快照，确保数据 0 风险。

---

## 快速上手

### 1. 环境准备
推荐使用极速 Python 包管理器 [uv](https://github.com/astral-sh/uv)：

```bash
git clone https://github.com/your-username/antigravity-session-rescuer.git
cd antigravity-session-rescuer
```

### 2. 核心指令示例

#### (1) 一键全自动冷修复（推荐）
安全停止后台常驻进程 -> 创建时间戳备份 -> 扫描所有 SQLite 数据库并提取标题 -> 重构中央二进制索引 `agyhub_summaries_proto.pb` -> 规范化全路径项目 JSON -> 自动重新拉起 Antigravity 客户端：
```bash
uv run antigravity-rescuer --auto
```

#### (2) 只读检测与会话预览（不修改任何文件）
扫描当前系统环境，打印详细的取证诊断报告：
```bash
uv run antigravity-rescuer --dry-run
```

#### (3) 手动指定自定义数据目录
若您的 Antigravity 数据存放在非默认路径（如移动硬盘或外置存储）：
```bash
uv run antigravity-rescuer --auto --data-dir "/自定义/antigravity/数据路径"
```

#### (4) 运行中热同步项目名称（无需重启）
通过 Connect-RPC 向正在运行的 Antigravity 发送项目重命名指令：
```bash
uv run antigravity-rescuer --live-sync
```

#### (5) 仅创建安全备份快照
```bash
uv run antigravity-rescuer --backup-only
```

#### (6) 查看所有历史备份点
```bash
uv run antigravity-rescuer --list-backups
```

---

## 完整命令行参数速查表 (CLI Options)

| 参数项 | 接受值 | 功能说明 |
| :--- | :--- | :--- |
| `--auto` | 无 | 执行完整自动化冷修复流程（停止进程 -> 快照备份 -> 重构索引 -> 启动客户端） |
| `--dry-run` | 无 | 仅执行只读诊断分析与会话预览，不修改任何磁盘文件 |
| `--live-sync` | 无 | 向正在运行的 Antigravity 后台发送 Connect-RPC 实时热同步项目名 |
| `--backup-only` | 无 | 仅在本地生成带精确时间戳的原子快照备份后退出 |
| `--list-backups` | 无 | 枚举并列出所有历史已创建的备份快照 |
| `--data-dir` | `<路径>` | 手动指定 Antigravity 数据目录（默认自动全盘智能探测） |
| `-h`, `--help` | 无 | 打印命令行帮助信息并退出 |

---

## 开发者与测试

执行代码静态检查：
```bash
uv run ruff check .
```

运行全部 19 个单元与集成测试用例：
```bash
uv run pytest -v
```

---

## 开源协议

本项目采用 [MIT License](LICENSE) 开源协议，欢迎提交 Issue 与 PR 共同完善！
