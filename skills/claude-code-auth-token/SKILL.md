---
name: claude-code-auth-token
description: Audit, summarize, repair, or debug Claude Code authentication and token state. Use when the user asks about Claude Code OAuth/API tokens, `claude setup-token`, `CLAUDE_CODE_OAUTH_TOKEN` warnings, Claude auth cleanup, whether a token is set, debug/auth-status commands, or Codex/Claude threads that changed Claude Code credentials. Always avoid printing secret token values.
---

# Claude Code Auth Token

Use this skill to investigate Claude Code auth/token state without exposing secrets, and to recover the known June 12, 2026 Codex token-cleanup threads when they are relevant.

## Core Rules

- Never print actual token values, credential JSON contents, bearer tokens, or API keys.
- Report whether a token is `set`, `unset`, `present`, or `absent`.
- Redact command output before showing snippets that may contain `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, `CLAUDE_API_KEY`, bearer tokens, or `sk-*` values.
- Prefer clean-environment checks when verifying disk auth, so live inherited env tokens do not mask the real state.
- Treat existing debug logs as sensitive until searched and redacted.

## Known Local Threads

Use these as historical context, not as current truth. Verify current files before acting.

### Auth Cleanup Thread

Codex session:

```text
/home/mark/.codex/sessions/2026/06/12/rollout-2026-06-12T10-20-30-019ebcd9-7d81-7ab2-8c7f-7502a0f7c4c6.jsonl
```

What it found:
- A persisted `CLAUDE_CODE_OAUTH_TOKEN` export in `~/.bashrc`.
- A nearby comment: `Claude Code OAuth token (issued via claude setup-token)`.

What it did:
- Removed the persisted `CLAUDE_CODE_OAUTH_TOKEN` export from `~/.bashrc`.
- Removed `~/.claude/.credentials.json`.
- Removed `oauthAccount` and `userID` from `~/.claude.json`.
- Verified disk auth with a clean environment:

```bash
env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY claude auth status
```

Known result at that time:

```json
{
  "loggedIn": false,
  "authMethod": "none",
  "apiProvider": "firstParty"
}
```

It also ran `claude --help`, which showed `--debug`, `--debug-file <path>`, and deprecated `--mcp-debug`. It did not run Claude in debug mode or produce a debug log.

### Warning Fix Thread

Codex session:

```text
/home/mark/.codex/sessions/2026/06/12/rollout-2026-06-12T10-28-42-019ebce0-fecb-74e0-9aaf-ebe6f1a5ca9d.jsonl
```

Prompt handled:

```text
Warning: CLAUDE_CODE_OAUTH_TOKEN is set in your environment and will override this login token at runtime. After logging in, unset that variable for your new credentials to take effect.
```

What it did:
- Added this guard to `~/.bashrc` and `~/.profile`:

```bash
unset CLAUDE_CODE_OAUTH_TOKEN
```

- Verified explicit login shells, interactive bash shells, and profile-sourced shells saw the variable as unset.
- Noted that an already-running parent Codex process can still inherit the old variable until restarted; for already-open terminals, run:

```bash
unset CLAUDE_CODE_OAUTH_TOKEN
```

## Investigation Workflow

1. Check live environment without printing values:

```bash
printf 'CLAUDE_CODE_OAUTH_TOKEN='
if [ -n "${CLAUDE_CODE_OAUTH_TOKEN+x}" ]; then echo set; else echo unset; fi
```

2. Search common shell/config sources:

```bash
rg -n 'CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY|CLAUDE_API_KEY' \
  "$HOME/.bashrc" "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bash_login" \
  "$HOME/.zshrc" "$HOME/.config" 2>/dev/null
```

Redact matches before showing them to the user.

3. Check Claude disk auth with env credentials removed:

```bash
env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY claude auth status
```

4. Check shell startup behavior after fixes:

```bash
bash -lc 'printf explicit_login=; if [ -n "${CLAUDE_CODE_OAUTH_TOKEN+x}" ]; then echo set; else echo unset; fi'
bash -ic 'printf explicit_interactive=; if [ -n "${CLAUDE_CODE_OAUTH_TOKEN+x}" ]; then echo set; else echo unset; fi'
sh -lc '. "$HOME/.profile"; printf explicit_profile=; if [ -n "${CLAUDE_CODE_OAUTH_TOKEN+x}" ]; then echo set; else echo unset; fi'
```

5. If the user asks for thread evidence, search only targeted Codex logs first:

```bash
rg -n -i 'CLAUDE_CODE_OAUTH_TOKEN|setup-token|claude auth status|--debug|debug-file' \
  "$HOME/.codex/sessions/2026/06/12/rollout-2026-06-12T10-20-30-019ebcd9-7d81-7ab2-8c7f-7502a0f7c4c6.jsonl" \
  "$HOME/.codex/sessions/2026/06/12/rollout-2026-06-12T10-28-42-019ebce0-fecb-74e0-9aaf-ebe6f1a5ca9d.jsonl"
```

## Repair Patterns

If a persisted token export exists and the user wants it removed:
- Remove only the export/comment lines that set the token.
- Prefer `apply_patch` for shell startup files.
- Do not delete unrelated shell config.
- Re-run the startup checks above.

If Claude login should use stored credentials instead of an inherited token:
- Add `unset CLAUDE_CODE_OAUTH_TOKEN` near the top of `~/.bashrc`, before non-interactive early returns.
- Add the same guard near the top of `~/.profile` for non-bash login shells.
- Tell the user already-open terminals need a one-time `unset CLAUDE_CODE_OAUTH_TOKEN` or restart.

If Claude disk auth should be cleared:
- Remove `~/.claude/.credentials.json` only when explicitly requested.
- Remove `oauthAccount` and `userID` from `~/.claude.json` only when explicitly requested.
- Verify with clean-env `claude auth status`.

## Debug Handling

Use debug only when the user asks for it or when ordinary auth/status checks are insufficient.

- Discover flags with `claude --help`; expected options include `--debug [filter]` and `--debug-file <path>`.
- Prefer a temporary debug file path.
- Search and redact debug logs before quoting or summarizing.
- Do not assume a thread produced a debug log just because `claude --help` listed debug flags.
