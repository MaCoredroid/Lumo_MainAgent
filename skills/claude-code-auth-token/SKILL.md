---
name: claude-code-auth-token
description: Audit, summarize, repair, or debug Claude Code authentication and token state. Use when the user asks about Claude Code OAuth/API tokens, `claude setup-token`, `CLAUDE_CODE_OAUTH_TOKEN` warnings, Claude auth cleanup, whether a token is set, an interactive Claude session stuck on a login/onboarding screen while headless works, a subscription model (e.g. Fable) wrongly demanding "usage credits" on Max, stale resumed tmux/Claude sessions, debug/auth-status commands, or Codex/Claude threads that changed Claude Code credentials. Always avoid printing secret token values.
---

# Claude Code Auth Token

Use this skill to investigate and repair Claude Code auth/token state without exposing secrets. It covers the two auth models (env token vs on-disk login), the interactive-vs-headless gap, the Fable/subscription "usage credits" bug, live tmux/pane recovery, and the June 12, 2026 Codex token-cleanup threads.

## Core Rules

- Never print actual token values, credential JSON contents, bearer tokens, or API keys.
- Report whether a token is `set`, `unset`, `present`, or `absent`.
- Redact command output before showing snippets that may contain `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`, `CLAUDE_API_KEY`, bearer tokens, `sk-*` values, or OAuth login URLs/codes.
- To confirm *which* token is in place without revealing it, compare a **SHA-256 fingerprint prefix** of the value across locations (file, tmux global, live shell). A hash is not a secret; equal prefixes prove the same token.
- Prefer clean-environment checks when verifying disk auth, so live inherited env tokens do not mask the real state.
- `/proc/<pid>/environ` is frozen at exec time — it does **not** reflect a running shell's later `export`/`unset`. For a live interactive shell, verify behaviorally (have the pane print the `+x` test or a fingerprint), never from `/proc`.
- Headless `claude -p` and `claude auth status` honor the env token, but the interactive TUI has separate gating (onboarding/login). A headless pass does not prove the interactive pane is healthy — read the actual pane.
- Treat existing debug logs as sensitive until searched and redacted.

## Two Auth Models

Claude Code can authenticate two ways, and they interact:

1. **Env token** — `CLAUDE_CODE_OAUTH_TOKEN` (a `sk-ant-oat01-...` long-lived token from `claude setup-token`). Great for headless. `claude auth status` reports `"authMethod": "oauth_token"`. In the TUI the status line reads **`· Claude API`**.
2. **On-disk login** — interactive `/login` (browser OAuth) writes `~/.claude/.credentials.json` and populates `~/.claude.json` `oauthAccount`. `claude auth status` reports `"authMethod": "claude.ai"` plus `"subscriptionType": "max"` (or pro/team).

Critical: **the env token overrides on-disk login at runtime.** If `CLAUDE_CODE_OAUTH_TOKEN` is set, Claude uses it and ignores the login credentials. So any fix that relies on the login (see the Fable section) requires the env token to be **unset** first.

Quick discriminator (does not print secrets):

```bash
# with whatever is currently in the environment
claude auth status
# with the env token removed — reveals the on-disk login, if any
env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY -u CLAUDE_API_KEY claude auth status
```

If the second command shows `"subscriptionType": "max"` but the first shows `"authMethod": "oauth_token"` with no subscription, the env token is shadowing a working Max login.

## Investigation Workflow

1. Check live environment without printing values:

```bash
printf 'CLAUDE_CODE_OAUTH_TOKEN='
if [ -n "${CLAUDE_CODE_OAUTH_TOKEN+x}" ]; then echo set; else echo unset; fi
```

2. Search common shell/config sources (redact matches before showing them):

```bash
grep -nE 'CLAUDE_CODE_OAUTH_TOKEN|ANTHROPIC_API_KEY|CLAUDE_API_KEY' \
  "$HOME/.bashrc" "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bash_login" \
  "$HOME/.zshrc" "$HOME/.config/claude-code/"* 2>/dev/null \
  | sed -E 's/(sk-[A-Za-z0-9_-]+)/[REDACTED]/g'
```

3. Check Claude disk auth with env credentials removed (see the discriminator above).

4. Fingerprint the token that is actually wired in, without printing it:

```bash
# file value
grep '^export CLAUDE_CODE_OAUTH_TOKEN=' "$HOME/.config/claude-code/oauth.env" \
  | sed 's/^export CLAUDE_CODE_OAUTH_TOKEN=//' | tr -d '\n' | sha256sum | cut -c1-16
# a live shell can print: printf %s "$CLAUDE_CODE_OAUTH_TOKEN" | sha256sum | cut -c1-16
```

5. Check the subscription/entitlement view (values redacted):

```bash
jq '{authMethod:(.oauthAccount.authMethod // null), hasAvailableSubscription,
     subscriptionType:(.oauthAccount.subscriptionType // null),
     hasAccount:has("oauthAccount"), hasCompletedOnboarding}' "$HOME/.claude.json"
```

6. For a live tmux/Claude pane, identify the pane and read what it actually shows (redact `sk-*` AND URLs — the pane may be on a browser-OAuth screen):

```bash
tmux list-panes -a -F '#{pane_id} #{session_name}:#{window_index}.#{pane_index} pid=#{pane_pid} cmd=#{pane_current_command} path=#{pane_current_path}'
tmux capture-pane -p -J -S -120 -t '<target>' | sed -E 's#(sk-[A-Za-z0-9_-]+)#[REDACTED]#g; s#https?://[^ ]+#[URL]#g'
```

## Interactive TUI vs Headless Token

Symptom: `claude auth status` and `claude -p` work with the env token, but launching the interactive TUI (often `claude --resume`) drops to first-run onboarding — a **theme picker** and then **"Select login method"** — and picking "Claude account with subscription" starts a browser OAuth ("Paste code here") that ignores the env token.

Cause: `~/.claude.json` has `hasCompletedOnboarding: false` (often together with a half-cleared auth state: `userID` present, `oauthAccount` absent, no `.credentials.json`). The interactive first-run flow runs regardless of the env token.

Fix — let the env token drive the TUI by marking onboarding complete (back up first):

```bash
stamp=$(date +%Y%m%dT%H%M%S); cp -p "$HOME/.claude.json" "$HOME/.claude/auth-backup-$stamp.json"
ver=$(claude --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
jq --arg v "$ver" '.hasCompletedOnboarding=true | .theme="dark" | .lastOnboardingVersion=$v' \
  "$HOME/.claude.json" > "$HOME/.claude.json.tmp" && chmod 600 "$HOME/.claude.json.tmp" \
  && mv "$HOME/.claude.json.tmp" "$HOME/.claude.json"
```

Deciding check (the skill's rule): relaunch in the pane, accept any remaining onboarding, send a real prompt, and read the response — do not trust a headless `claude -p` for this.

Notes:
- `Ctrl-C` often does **not** dismiss the "Select login method" menu; to exit a stuck instance, kill the claude child of the pane's shell: `pkill -TERM -P "$(tmux display-message -p -t '<pane>' '#{pane_pid}')"`.
- Do NOT drive the browser OAuth to "fix" a token box — that path ignores the env token and starts a fresh login.

## Fable / Subscription "Usage Credits" on Max

Symptom: a subscription model (notably **Fable 5**) reports `Fable 5 requires usage credits` and silently downgrades to Sonnet/Opus, even on Max, and **restarting does not help**. The TUI status line shows `· Claude API`; `~/.claude.json` shows `hasAvailableSubscription: false` and no `oauthAccount`.

Root cause: a known, open Claude Code client bug (anthropics/claude-code #79337, canonical #79341; #79378 (dup); #79441 (VS Code variant); related #74562, #67650, #78622). After Fable 5 became standard on Max on 2026-07-20, the **`CLAUDE_CODE_OAUTH_TOKEN` / setup-token path does not pick up the new Fable-on-Max entitlement** — it bills as API and demands credits. Both `claude-fable-5` and `claude-fable-5[1m]` fail via the token. This was still unfixed on the latest release (v2.1.217); check for a newer version first (`npm view @anthropic-ai/claude-code dist-tags`).

Things that do **not** fix it (verify, don't repeat blindly): restarting Claude Code; deleting cached fields `hasAvailableSubscription`, `overageCreditGrantCache`, `cachedGrowthBookFeatures`, `additionalModelOptionsCache`, `modelAccessCache` from `~/.claude.json`.

Confirmed fix (from the issue threads): **interactive `/login`** (browser OAuth to the same Max account) writes `~/.claude/.credentials.json` (`authMethod:"claude.ai"`, `subscriptionType:"max"`) and Fable works. Because the env token overrides the login, `CLAUDE_CODE_OAUTH_TOKEN` must be **unset** for the login to take effect. The user performs the sign-in; never authenticate or paste an OAuth code on their behalf.

Verify the login path before removing the token anywhere (the headless probe needs no particular directory):

```bash
ls -la "$HOME/.claude/.credentials.json"
env -u CLAUDE_CODE_OAUTH_TOKEN -u ANTHROPIC_API_KEY claude auth status   # expect loggedIn:true, subscriptionType:"max"
env -u CLAUDE_CODE_OAUTH_TOKEN claude --dangerously-skip-permissions --model claude-fable-5 -p 'Reply with the single word READY'
```

## Repair Patterns

If a persisted token export exists and the user wants it removed:
- Remove only the export/comment lines that set the token; do not delete unrelated shell config.
- Re-run the startup checks above.

If a supplied long-lived OAuth token should replace the current runtime auth:
- Store it in one locked-down env file, e.g. `~/.config/claude-code/oauth.env`, directory mode `700`, file mode `600`, sourced from `~/.bashrc` and `~/.profile`.
- Transfer the value over an encrypted channel via stdin so it never lands in remote shell history or `ps`:

```bash
printf 'export CLAUDE_CODE_OAUTH_TOKEN=%s\n' "$NEW" | ssh host \
  'umask 077; d=~/.config/claude-code; mkdir -p "$d"; chmod 700 "$d"; \
   cp -p "$d/oauth.env" "$d/oauth.env.bak-$(date +%Y%m%dT%H%M%S)" 2>/dev/null; \
   cat > "$d/oauth.env.tmp"; chmod 600 "$d/oauth.env.tmp"; mv "$d/oauth.env.tmp" "$d/oauth.env"'
```

- Refresh tmux for new panes: `tmux set-environment -g CLAUDE_CODE_OAUTH_TOKEN "$CLAUDE_CODE_OAUTH_TOKEN"` (from a token-sourced shell). Caveat: passing the value as argv exposes the raw token in `ps`/`/proc/<pid>/cmdline` for an instant — acceptable on single-user boxes, but on shared/multi-user hosts prefer letting new panes inherit the token from the sourced `oauth.env` (already loaded by `~/.bashrc`/`~/.profile`) and skip seeding the tmux global. The same caveat applies to the rollback re-set below.
- Confirm by comparing the SHA-256 fingerprint prefix of the file, the tmux global, and a login shell — never by printing the value.

To switch a headless box from env-token auth to on-disk login credentials (so subscription models like Fable work) — see the Fable section for why:
1. Have the user run `/login` in a shell where `CLAUDE_CODE_OAUTH_TOKEN` is unset (they do the sign-in). Verify the login path (commands above) **before** removing the token.
2. Stop new shells from exporting the token — disable the env file reversibly, keeping the value:

```bash
mv ~/.config/claude-code/oauth.env ~/.config/claude-code/oauth.env.disabled
```

3. Clear it for new tmux panes: `tmux set-environment -gu CLAUDE_CODE_OAUTH_TOKEN`.
4. Unset it in already-running shells (see tmux fan-out below). Running processes keep the old token until restarted.
5. Verify a fresh login shell defaults to the login creds and runs Fable:

```bash
bash -lc 'if [ -n "${CLAUDE_CODE_OAUTH_TOKEN+x}" ]; then echo set; else echo unset; fi'
bash -lc 'claude auth status'                       # expect claude.ai / subscriptionType:"max"
bash -lc 'claude --model claude-fable-5 -p "Reply READY"'
```

Rollback: `mv oauth.env.disabled oauth.env` and re-set the tmux global from a token-sourced shell (mind the `ps` caveat above).

If Claude disk auth should be cleared (only when explicitly requested), back up first:

```bash
stamp=$(date +%Y%m%dT%H%M%S); backup_dir="$HOME/.claude/auth-backup-$stamp"
mkdir -p "$backup_dir"; chmod 700 "$backup_dir"
cp -p "$HOME/.claude.json" "$backup_dir/.claude.json"
[ -f "$HOME/.claude/.credentials.json" ] && mv "$HOME/.claude/.credentials.json" "$backup_dir/.credentials.json"
jq 'del(.oauthAccount, .userID)' "$backup_dir/.claude.json" > "$HOME/.claude.json.tmp"
chmod 600 "$HOME/.claude.json.tmp"; mv "$HOME/.claude.json.tmp" "$HOME/.claude.json"
```

Then re-check clean-env vs token-env auth, and (if a resumed pane still shows stale state) restart that pane from the intended auth and read its pane-visible response — the deciding check. A green headless `claude -p` does not prove the resumed interactive pane stopped using stale disk state.

## tmux Operational Recipes

Change env in a **live** pane (so `unset`/`export` run in the pane's own shell, not a subshell): stage a tiny script and `source` it.

```bash
# local -> remote: stage, then have each target pane source it
cat rollout.sh | ssh host 'mkdir -p ~/.cache; cat > ~/.cache/rollout.sh; : > ~/.cache/rollout.log'
# rollout.sh does e.g.  unset CLAUDE_CODE_OAUTH_TOKEN
#   then logs its result:  printf '%s\n' "pane=$TMUX_PANE state=$([ -n \"${CLAUDE_CODE_OAUTH_TOKEN+x}\" ] && echo set || echo unset)" >> ~/.cache/rollout.log
```

Fan out to every idle shell pane and verify centrally (each pane self-reports via `$TMUX_PANE`):

```bash
mapfile -t t < <(tmux list-panes -a -F '#{pane_id}|#{pane_current_command}' | awk -F'|' '$2 ~ /^(-?bash|zsh)$/{print $1}')
for p in "${t[@]}"; do tmux send-keys -t "$p" 'source ~/.cache/rollout.sh' Enter; done
# poll until the log has ${#t[@]} lines, then check none report the wrong state; diff pane-ids vs log to find stragglers
```

Keep the staged script in place until the log is complete — a pane that was briefly busy will `source` it after you delete it and silently error (that is the usual cause of one missing pane). Only target panes whose `#{pane_current_command}` is a bash/zsh shell (both support `source`); never send keys into a pane running the Claude TUI (they type into the app).

Redaction for captures (use `#` as the sed delimiter so URLs don't break it):

```bash
tmux capture-pane -p -J -t '<pane>' | sed -E 's#(sk-[A-Za-z0-9_-]+)#[REDACTED]#g; s#https?://[^ ]+#[URL]#g'
```

## Known Local Threads

Use as context, not current truth; verify current files before acting. Two Codex sessions on 2026-06-12:

- **Auth Cleanup** (`~/.codex/sessions/2026/06/12/rollout-2026-06-12T10-20-30-*.jsonl`): removed a persisted `CLAUDE_CODE_OAUTH_TOKEN` export from `~/.bashrc`, removed `~/.claude/.credentials.json`, and removed `oauthAccount`/`userID` from `~/.claude.json`; verified clean-env auth was `{"loggedIn": false, "authMethod": "none"}`. (This half-cleared state is what later triggered the interactive login gate above.)
- **Warning Fix** (`~/.codex/sessions/2026/06/12/rollout-2026-06-12T10-28-42-*.jsonl`): handled the runtime warning `CLAUDE_CODE_OAUTH_TOKEN is set in your environment and will override this login token at runtime` by adding `unset CLAUDE_CODE_OAUTH_TOKEN` guards to `~/.bashrc` and `~/.profile`; noted already-running processes keep the old value until restarted.

To pull thread evidence, search those two files first for `CLAUDE_CODE_OAUTH_TOKEN|setup-token|claude auth status|--debug`.

## Debug Handling

Use debug only when the user asks or when ordinary auth/status checks are insufficient.

- Discover flags with `claude --help`; expected options include `--debug [filter]` and `--debug-file <path>`.
- Prefer a temporary debug file path; search and redact debug logs before quoting or summarizing.
- Do not assume a thread produced a debug log just because `claude --help` listed debug flags.
