# Lumo Main Agent Skills

This repository contains three Codex skills:

- `lumo-master-agent`: strict LumoAlpha main-agent orchestration for isolated sub-agent implementation loops.
- `claude-session-context`: bounded recovery of recent Claude Code JSONL, memory, and workflow context.
- `claude-code-auth-token`: safe Claude Code auth/token audits, cleanup summaries, and debug guidance without exposing secrets.

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
  claude-code-auth-token/
    SKILL.md
    agents/openai.yaml
```

`README.md` is intentionally the only top-level file.
