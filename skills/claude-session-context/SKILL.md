---
name: claude-session-context
description: Recover working context from local Claude Code transcripts and workflow artifacts. Use when Codex is asked to read recent Claude Code session JSONL, reconstruct prior implementation state, continue work from Claude sessions, inspect handoff/closeout/workflow context, or understand what happened in another agent's recent coding sessions.
---

# Claude Session Context

Use this skill to build a compact working brief from local Claude Code history before continuing implementation work.

## Workflow

1. Run the bundled summarizer instead of opening raw JSONL directly:

```bash
python3 skills/claude-session-context/scripts/summarize_claude_sessions.py --sessions 5 --events 80
```

2. If the user asks for "all recent" Claude sessions across projects, add `--all-projects`:

```bash
python3 skills/claude-session-context/scripts/summarize_claude_sessions.py --all-projects --sessions 8 --events 60
```

3. Read the summary in this order:
   - Session metadata: path, cwd, branch, title, first/last timestamps.
   - User prompts: identify the actual goal, constraints, and any pivots.
   - Assistant text and tool use: identify files touched, commands run, tests attempted, and blockers.
   - Tool results: use only bounded snippets for evidence; rerun current commands when accuracy matters.
   - Claude memory/workflow files: read the relevant memory note or workflow run JSON when it matches the task.
   - Repo workflow docs: open relevant closeout, handoff, `CLAUDE.md`, `AGENTS.md`, or workflow docs before editing.

4. Before implementing, state the recovered context briefly: current objective, likely repo path, relevant files, last known status, and remaining risks.

## Guardrails

- Do not load full large `.jsonl` transcripts into context unless the summary points to a very specific line range or file section.
- Do not quote or expose `thinking` blocks from Claude transcripts. The helper skips them; keep that behavior if patching it.
- Treat old tool outputs as stale evidence. Verify current repository state with local commands before making code changes.
- Prefer the active workspace project first. Use `--all-projects` only when explicitly requested or when the active project has no useful sessions.
- When a transcript mentions a closeout/handoff/workflow file, search for and read that artifact directly; it is usually higher signal than the full chat.

## Helper Options

- `--project PATH`: summarize sessions associated with a specific working directory. Defaults to the current directory.
- `--all-projects`: ignore project filtering and rank all Claude project transcripts by modification time.
- `--sessions N`: number of recent session files to summarize.
- `--events N`: number of recent high-value events to show per session.
- `--since-days N`: only include files modified in the last N days.
- `--max-text-chars N`: per-event truncation limit.
- `--no-workflow-files`: skip listing likely workflow/handoff files.
