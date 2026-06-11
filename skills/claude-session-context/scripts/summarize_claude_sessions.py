#!/usr/bin/env python3
"""Summarize recent Claude Code JSONL sessions without flooding context."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    ".claude",
    ".codex",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    "__pycache__",
    "output",
    "outputs",
    "logs",
    "verifier_data",
    ".lumo-live-codex",
}

WORKFLOW_NAMES = {
    "CLAUDE.md",
    "AGENTS.md",
    "MEMORY.md",
}

WORKFLOW_KEYWORDS = (
    "closeout",
    "handoff",
    "workflow",
    "worklog",
    "memory",
    "status",
    "plan",
)

TEXT_DOC_SUFFIXES = {".md", ".txt", ".rst", ".adoc"}


@dataclass
class Event:
    timestamp: str
    kind: str
    text: str
    cwd: str | None = None
    branch: str | None = None


@dataclass
class SessionSummary:
    path: Path
    size: int
    mtime: float
    line_count: int = 0
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    title: str | None = None
    cwds: Counter[str] = field(default_factory=Counter)
    branches: Counter[str] = field(default_factory=Counter)
    event_types: Counter[str] = field(default_factory=Counter)
    events: deque[Event] = field(default_factory=deque)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-root", default=str(Path.home() / ".claude"))
    parser.add_argument("--project", default=os.getcwd())
    parser.add_argument("--all-projects", action="store_true")
    parser.add_argument("--sessions", type=int, default=5)
    parser.add_argument("--events", type=int, default=80)
    parser.add_argument("--since-days", type=float)
    parser.add_argument("--max-text-chars", type=int, default=700)
    parser.add_argument("--workflow-root", default=os.getcwd())
    parser.add_argument("--workflow-max-depth", type=int, default=5)
    parser.add_argument("--workflow-limit", type=int, default=40)
    parser.add_argument("--claude-memory-limit", type=int, default=20)
    parser.add_argument("--claude-workflow-limit", type=int, default=20)
    parser.add_argument("--no-workflow-files", action="store_true")
    return parser.parse_args()


def encoded_project_path(path: Path) -> str:
    resolved = path.resolve()
    return "-" + str(resolved).strip("/").replace("/", "-")


def iter_jsonl_files(claude_root: Path, project: Path, all_projects: bool) -> list[Path]:
    projects_root = claude_root / "projects"
    if not projects_root.exists():
        return []

    if not all_projects:
        direct = projects_root / encoded_project_path(project)
        if direct.exists():
            return sorted(direct.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)

    return sorted(projects_root.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def truncate(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def content_events(obj: dict[str, Any], max_chars: int) -> Iterable[tuple[str, str]]:
    msg = obj.get("message")
    if not isinstance(msg, dict):
        if obj.get("type") == "attachment":
            attachment = obj.get("attachment")
            yield "attachment", truncate(json.dumps(attachment, sort_keys=True), max_chars)
        return

    content = msg.get("content")
    if isinstance(content, str):
        yield obj.get("type") or msg.get("role") or "message", truncate(content, max_chars)
        return

    if not isinstance(content, list):
        return

    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "thinking":
            continue
        if item_type == "text":
            yield obj.get("type") or msg.get("role") or "text", truncate(item.get("text", ""), max_chars)
        elif item_type == "tool_use":
            name = item.get("name", "tool")
            tool_input = item.get("input")
            if isinstance(tool_input, dict):
                desc = tool_input.get("description")
                command = tool_input.get("command")
                compact = desc or command or json.dumps(tool_input, sort_keys=True)
            else:
                compact = tool_input
            yield "tool_use", truncate(f"{name}: {compact}", max_chars)
        elif item_type == "tool_result":
            prefix = "tool_result_error" if item.get("is_error") else "tool_result"
            yield prefix, truncate(item.get("content", ""), max_chars)


def summarize_file(path: Path, event_limit: int, max_chars: int) -> SessionSummary:
    summary = SessionSummary(
        path=path,
        size=path.stat().st_size,
        mtime=path.stat().st_mtime,
        events=deque(maxlen=event_limit),
    )

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            summary.line_count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            obj_type = obj.get("type", "unknown")
            summary.event_types[obj_type] += 1

            timestamp = obj.get("timestamp")
            if timestamp:
                summary.first_timestamp = summary.first_timestamp or timestamp
                summary.last_timestamp = timestamp

            if obj_type == "ai-title" and obj.get("aiTitle"):
                summary.title = str(obj["aiTitle"])

            cwd = obj.get("cwd")
            if cwd:
                summary.cwds[str(cwd)] += 1

            branch = obj.get("gitBranch")
            if branch:
                summary.branches[str(branch)] += 1

            for kind, text in content_events(obj, max_chars):
                if text:
                    summary.events.append(Event(timestamp or "", kind, text, cwd=cwd, branch=branch))

    return summary


def is_recent_enough(path: Path, since_days: float | None) -> bool:
    if since_days is None:
        return True
    cutoff = datetime.now(timezone.utc).timestamp() - since_days * 86400
    return path.stat().st_mtime >= cutoff


def format_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def top(counter: Counter[str], limit: int = 3) -> str:
    if not counter:
        return "-"
    return ", ".join(f"{key} ({count})" for key, count in counter.most_common(limit))


def repo_workflow_score(path: Path) -> bool:
    name = path.name
    lower = name.lower()
    if name in WORKFLOW_NAMES:
        return True
    if path.suffix.lower() not in TEXT_DOC_SUFFIXES:
        return False
    return any(keyword in lower for keyword in WORKFLOW_KEYWORDS)


def find_workflow_files(root: Path, max_depth: int, limit: int) -> list[Path]:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        return []

    matches: list[Path] = []
    root_depth = len(root.parts)
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        depth = len(current_path.parts) - root_depth
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and depth < max_depth]
        for filename in files:
            path = current_path / filename
            if repo_workflow_score(path):
                matches.append(path)

    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def first_heading(path: Path, max_chars: int = 160) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            in_frontmatter = False
            first_line = True
            for line in handle:
                stripped = line.strip()
                if first_line and stripped == "---":
                    in_frontmatter = True
                    first_line = False
                    continue
                first_line = False
                if in_frontmatter:
                    if stripped == "---":
                        in_frontmatter = False
                    continue
                if stripped:
                    return truncate(stripped.lstrip("#").strip(), max_chars)
    except OSError:
        return None
    return None


def selected_claude_project_dirs(summaries: list[SessionSummary]) -> list[Path]:
    dirs: list[Path] = []
    seen: set[Path] = set()
    for summary in summaries:
        parent = summary.path.parent
        if parent not in seen:
            dirs.append(parent)
            seen.add(parent)
    return dirs


def find_claude_memory_files(project_dirs: list[Path], limit: int) -> list[Path]:
    matches: list[Path] = []
    for project_dir in project_dirs:
        memory_dir = project_dir / "memory"
        if memory_dir.exists():
            matches.extend(p for p in memory_dir.iterdir() if p.is_file())
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def summarize_workflow_json(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return ""
    if not isinstance(data, dict):
        return ""

    pieces = []
    for key in ("workflowName", "status", "timestamp"):
        if data.get(key):
            pieces.append(f"{key}={data[key]}")
    if data.get("totalToolCalls") is not None:
        pieces.append(f"toolCalls={data['totalToolCalls']}")
    if data.get("totalTokens") is not None:
        pieces.append(f"tokens={data['totalTokens']}")
    if data.get("summary"):
        pieces.append("summary=" + truncate(str(data["summary"]), 220))
    if data.get("scriptPath"):
        pieces.append(f"scriptPath={data['scriptPath']}")
    return "; ".join(pieces)


def find_claude_workflows(summaries: list[SessionSummary], limit: int) -> list[Path]:
    matches: list[Path] = []
    for summary in summaries:
        workflow_dir = summary.path.with_suffix("") / "workflows"
        if workflow_dir.exists():
            matches.extend(workflow_dir.glob("*.json"))
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def print_summary(summaries: list[SessionSummary], args: argparse.Namespace) -> None:
    print("# Claude Code Session Context")
    print()
    print(f"- Claude root: `{Path(args.claude_root).expanduser()}`")
    print(f"- Project filter: `{'all projects' if args.all_projects else Path(args.project).resolve()}`")
    print(f"- Sessions shown: {len(summaries)}")
    print()

    for index, summary in enumerate(summaries, start=1):
        modified = datetime.fromtimestamp(summary.mtime, timezone.utc).isoformat()
        print(f"## {index}. `{summary.path}`")
        print()
        print(f"- Modified: {modified}")
        print(f"- Size / lines: {format_bytes(summary.size)} / {summary.line_count}")
        print(f"- Transcript timestamps: {summary.first_timestamp or '-'} to {summary.last_timestamp or '-'}")
        print(f"- Title: {summary.title or '-'}")
        print(f"- CWDs: {top(summary.cwds)}")
        print(f"- Branches: {top(summary.branches)}")
        print(f"- Event types: {top(summary.event_types, 8)}")
        print()
        print("### Recent Events")
        print()
        if not summary.events:
            print("- No high-value events found.")
            print()
            continue

        for event in summary.events:
            ts = f"{event.timestamp} " if event.timestamp else ""
            print(f"- {ts}`{event.kind}`: {event.text}")
        print()


def print_claude_memory_and_workflows(summaries: list[SessionSummary], args: argparse.Namespace) -> None:
    if args.no_workflow_files:
        return

    project_dirs = selected_claude_project_dirs(summaries)
    memory_files = find_claude_memory_files(project_dirs, args.claude_memory_limit)
    workflows = find_claude_workflows(summaries, args.claude_workflow_limit)

    print("## Claude Memory And Workflows")
    print()
    if not memory_files and not workflows:
        print("- No Claude memory or workflow files found for selected sessions.")
        print()
        return

    if memory_files:
        print("### Memory")
        print()
        for path in memory_files:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            heading = first_heading(path)
            suffix = f" - {heading}" if heading else ""
            print(f"- `{path}` ({format_bytes(path.stat().st_size)}, modified {modified}){suffix}")
        print()

    if workflows:
        print("### Workflow Runs")
        print()
        for path in workflows:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            detail = summarize_workflow_json(path)
            suffix = f" - {detail}" if detail else ""
            print(f"- `{path}` ({format_bytes(path.stat().st_size)}, modified {modified}){suffix}")
        print()


def print_repo_workflow_files(args: argparse.Namespace) -> None:
    if args.no_workflow_files:
        return
    files = find_workflow_files(Path(args.workflow_root), args.workflow_max_depth, args.workflow_limit)
    print("## Repo Workflow Files")
    print()
    print(f"- Search root: `{Path(args.workflow_root).resolve()}`")
    if not files:
        print("- No likely repo workflow files found.")
        print()
        return

    for path in files:
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        print(f"- `{path}` ({format_bytes(path.stat().st_size)}, modified {modified})")
    print()


def main() -> int:
    args = parse_args()
    claude_root = Path(args.claude_root).expanduser()
    project = Path(args.project).expanduser()
    files = [p for p in iter_jsonl_files(claude_root, project, args.all_projects) if is_recent_enough(p, args.since_days)]
    selected = files[: max(0, args.sessions)]
    summaries = [summarize_file(path, max(0, args.events), args.max_text_chars) for path in selected]
    print_summary(summaries, args)
    print_claude_memory_and_workflows(summaries, args)
    print_repo_workflow_files(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
