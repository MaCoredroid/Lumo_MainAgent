# Lumo Main Agent Skills

This repository contains two Codex skills:

- `lumo-master-agent`: strict LumoAlpha main-agent orchestration for isolated sub-agent implementation loops.
- `claude-session-context`: bounded recovery of recent Claude Code JSONL, memory, and workflow context.

## Layout

```text
skills/
  lumo-master-agent/
    SKILL.md
    agents/openai.yaml
  claude-session-context/
    SKILL.md
    agents/openai.yaml
    scripts/summarize_claude_sessions.py
```

`README.md` is intentionally the only top-level file.
