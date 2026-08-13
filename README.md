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

**Antigravity Session Rescuer** is a zero-external-dependency, production-grade recovery and forensics toolkit for **Google Antigravity 2.x**. It repairs session loss, corrupted/truncated central indices, title degradations (UUID titles), and sidebar folder fallbacks (`Recovered Project`) caused by version upgrades (1.x to 2.x) or unexpected crashes.

---

## The Problem

When Antigravity updates to 2.x or suffers unexpected terminations, users commonly encounter:
1. **Catastrophic Session Loss**: Out of 100+ conversation databases, the UI only shows 2 to 3 sessions.
2. **Title Degradation**: Session titles are replaced by raw UUIDs, file paths, or random MCP tool strings.
3. **`Recovered Project` Fallback**: All project folders in the sidebar are renamed to `Recovered Project`.
4. **Strict `protojson` Unmarshaling Crashes**: Go backend's `language_server.exe` fails with `duplicate field` or `oneof is already set` errors when reading project configs, silently falling back to placeholder projects.

---

## Key Features

- **Automatic Multi-Environment Detection**: Auto-detects user data directories across Windows, macOS, and Linux with zero manual setup.
- **Deep DB Forensics & AI Title Extraction**: Decodes Protobuf payloads inside SQLite `steps` (`step_type=23/14`) to restore native AI-generated Chinese and English session titles.
- **Topological Subagent Separation**: Automatically parses `trajectory_metadata_blob` (Field 4/5) to isolate background subagents from main conversations, preventing dozens of phantom project folders.
- **Zero-Dependency Protobuf Compiler**: Pure Python implementation of Varint and Length-delimited encoders to build 100% compliant `agyhub_summaries_proto.pb` binary indices without needing `protoc`.
- **Dynamic Project Discovery**: Automatically detects existing workspace projects and generates deterministic UUIDs for unmapped repositories.
- **Strict Proto3 Compliance**: Eliminates duplicate field conflicts (camelCase vs snake_case) and enforces single `gitFolder` union structures to satisfy Go `protojson.Unmarshal`.
- **Live Connect-RPC Sync**: Sniffs dynamic ports and `x-codeium-csrf-token` from logs to push project tree updates in real-time without restarting Antigravity.
- **Atomic Time-Stamped Backups**: Automatically takes a full snapshot before making any modifications, allowing zero-risk rollbacks.

---

## Quick Start

### 1. Prerequisites
We recommend using [uv](https://github.com/astral-sh/uv) for blazing fast dependency management:

```bash
git clone https://github.com/your-username/antigravity-session-rescuer.git
cd antigravity-session-rescuer
```

### 2. Core Commands

#### Full Automatic Recovery (Recommended)
Stops background processes, takes an atomic backup, scans all SQLite databases, rebuilds `agyhub_summaries_proto.pb`, normalizes project JSON files, and restarts Antigravity:
```bash
uv run antigravity-rescuer --auto
```

#### Diagnostic Dry-Run (Read-Only)
Scans your local Antigravity environment and prints a detailed forensic report without writing to disk:
```bash
uv run antigravity-rescuer --dry-run
```

#### Custom Data Directory Override
If your data directory is stored in a non-standard path (e.g. external drive):
```bash
uv run antigravity-rescuer --auto --data-dir "/custom/path/to/antigravity"
```

#### Live RPC Sync
Sends Connect-RPC requests to the currently running Antigravity instance to update project names in real-time:
```bash
uv run antigravity-rescuer --live-sync
```

#### Create Safe Backup Only
```bash
uv run antigravity-rescuer --backup-only
```

#### List Existing Backups
```bash
uv run antigravity-rescuer --list-backups
```

---

## Complete CLI Options Matrix

| Flag | Argument | Description |
| :--- | :--- | :--- |
| `--auto` | None | Run full automated recovery workflow (Stop -> Backup -> Rebuild -> Launch) |
| `--dry-run` | None | Read-only scan and diagnostics report without modifying any files |
| `--live-sync` | None | Push project renaming updates to running Antigravity via Connect-RPC |
| `--backup-only` | None | Create a timestamped atomic backup snapshot and exit |
| `--list-backups` | None | Display a list of all historical recovery snapshots |
| `--data-dir` | `<PATH>` | Explicitly specify custom Antigravity data directory (defaults to auto-detection) |
| `-h`, `--help` | None | Show help message and exit |

---

## Development & Testing

Run static linting with `ruff`:
```bash
uv run ruff check .
```

Run the complete test suite (19 unit & integration tests):
```bash
uv run pytest -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).
