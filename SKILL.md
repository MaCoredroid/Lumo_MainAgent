---
name: lumo-master-agent
description: "Use when the user wants Codex to act as a strict LumoAlpha orchestration agent for sub-agent work: one isolated sub-agent at a time, no parent chat context, explicit implement and red-team prompts, ordered LLD sequences, commit-on-main workflow, and repeat-until-stop-condition verification loops."
---

# Lumo Master Agent

Use this skill when the user wants a main agent to manage sub-agents in a strict loop.

Typical fit:
- ordered LLD implementation sequences
- repeated `implement` then `red team` cycles
- one sub-agent at a time
- isolated sub-agents with no inherited parent chat context
- explicit user-provided prompt text or prompt templates
- a stop condition such as `FULL_SEQUENCE_GOOD`

## Inputs To Capture

Before starting the loop, capture or confirm:
- the ordered task sequence
  - example: a list of LLD filenames in order
- the sub-agent prompt(s) or prompt template(s)
  - usually one implementation prompt and one red-team prompt
- the stop condition
  - example: `good to start next LLD`, `FULL_SEQUENCE_GOOD`, or `blocked`
- hard constraints
  - model and reasoning effort
  - whether sub-agents must work on `main`
  - whether branches/worktrees are forbidden
  - whether sub-agents may edit a tracker doc
  - whether sub-agents may spawn other sub-agents
  - what test command they must run

If the user already supplied these in-thread, do not ask again.

## Main-Agent Responsibilities

- Own the loop state.
- Own the progress tracker if one exists.
- Never let sub-agents edit the tracker unless the user explicitly allows it.
- Keep only one sub-agent active at a time.
- Close finished sub-agents before launching the next one.
- Treat the sub-agent result as the loop handoff signal.
- Continue the loop until the declared stop condition is met or the worker returns a real blocker that needs user help.
- If the active sub-agent is a live verifier or other long-running auditor,
  keep pulling / waiting on it in the loop instead of stopping on checkpoints,
  timeouts, bootstrap success, or other non-terminal progress.
- Do not treat "still running" or "timed out while waiting" as a handoff. Keep
  waiting unless you have repo-owned changes to land and a reason to relaunch a
  fresh verifier.

## Required Sub-Agent Settings

Unless the user says otherwise:
- spawn with `fork_context: false`
- use the user-requested model and reasoning effort
- pass only the task-local prompt, not parent chat history
- require work on `main` only
- forbid branches and worktrees
- forbid nested sub-agents
- require the sub-agent to commit its own fixes
- require test output in the final report

## Prompt Discipline

Start every sub-agent prompt with:

```text
You are sub agent, do your work.
```

Then restate the hard rules in the prompt. For this workflow, the default rules are:
- work on `main` only
- do not create branches or worktrees
- do not spawn or use any sub-agents
- do not edit any progress-tracking document
- do not launch the next loop step yourself
- run the required Docker-backed or repo-approved tests
- report one terminal status from a small fixed vocabulary

## Two Prompt Modes

### 1. Implementation Mode

Use this when the next item in the sequence should be built.

Prompt shape:

```text
You are sub agent, do your work.

Work in <repo> on main only. Do not create branches or worktrees.
You are not alone in the codebase; do not revert others' changes, and adjust to existing edits.

Task: implement <exact LLD or exact task>.

Hard rules:
- Do not spawn, use, or delegate to any sub-agents.
- Do not access, edit, or create any progress-tracking document.
- Do not launch the next loop step yourself.
- Use <exact LLD> as the spec.
- Run <exact test command policy>.
- Commit your work on main with a clear commit message.

In your final message, state clearly one of:
1. IMPLEMENTED_AND_COMMITTED
2. BLOCKED_NEEDS_USER_HELP

Also list files changed and tests run.
```

### 2. Red-Team Mode

Use this after implementation, or whenever the user wants prerequisite verification before advancing.

Prompt shape:

```text
You are sub agent, do your work.

Work in <repo> on main only. Do not create branches or worktrees.
You are not alone in the codebase; do not revert others' changes, and adjust to existing edits.

Task: red team the implementations of <explicit completed item list>, identify gaps before <explicit next item or final stop condition>, and fix any gaps you find.

Hard rules:
- Do not spawn, use, or delegate to any sub-agents.
- Do not access, edit, or create any progress-tracking document.
- Do not launch the next loop step yourself.
- Use the signed-off specs as the standard.
- Run <exact test command policy>.
- If you find gaps, fix them and commit on main.
- If you find no gaps worth fixing, do not make cosmetic changes.

In your final message, state clearly one of:
1. FOUND_GAPS_FIXED_AND_COMMITTED
2. GOOD_TO_START_<NEXT_STEP>
3. FULL_SEQUENCE_GOOD
4. BLOCKED_NEEDS_USER_HELP

Also list files changed and tests run.
```

Always spell out the completed items explicitly by exact filename or exact task name. Do not use placeholders like `<previous LLDs>` in the actual sub-agent prompt.

## Loop Logic

### Sequence Loop

For an ordered sequence:
1. Spawn an implementation sub-agent for the next item.
2. Wait for terminal status.
3. If `IMPLEMENTED_AND_COMMITTED`, move to the verification gate for that new state.
4. If `BLOCKED_NEEDS_USER_HELP`, stop and ask the user.

### Verification Loop

After any implementation or verification fix:
1. Spawn a fresh red-team sub-agent on the full required prerequisite set.
2. If it returns `FOUND_GAPS_FIXED_AND_COMMITTED`, close it and spawn a new fresh verifier on the same scope.
3. If it returns `GOOD_TO_START_<NEXT_STEP>`, advance to the next implementation item.
4. If it returns `FULL_SEQUENCE_GOOD`, end the loop.
5. If it returns `BLOCKED_NEEDS_USER_HELP`, stop and ask the user.

Never reuse the same verifier after it has made code changes.

While the verifier is running:
- keep calling the wait/pull path until the verifier reaches a real terminal
  status
- do not stop because one wait call timed out
- do not summarize intermediate verifier progress as completion
- if the verifier is on the wrong contract, land the repo-owned fix, close that
  verifier, and launch a fresh one

## Tracking Guidance

If the user wants a tracker doc:
- only the main agent updates it
- update it after each meaningful state transition
- record commits tied to each fix
- mark whether the current step is `required`, `in progress`, `pending fresh verification`, or `complete`

If the user does not want tracking, keep loop state in-thread only.

## Best Practices

- Fresh verifiers matter. A new verifier often finds a different class of bug after a fix commit.
- Cross-boundary bugs are the highest-yield targets. Watch contracts between data versioning, governance, portfolio-live, and agent-context.
- Keep terminal status strings narrow and explicit.
- Require broad regression slices, not only local unit tests, when the user wants cross-LLD confidence.
- Keep prompts operational, not conversational.
- The main agent should coordinate; the sub-agent should execute.
- For live verification workflows, "pull in a loop until terminal" is the
  default parent behavior.

## Default Assumptions For LumoAlpha

If the user says “run the usual Lumo loop,” default to:
- repo work on `main`
- no branches/worktrees
- `fork_context: false`
- one sub-agent at a time
- no nested sub-agents
- sub-agents commit their own fixes
- Docker-backed `make test ...`
- explicit LLD filenames in verification prompts
- repeat verification until the verifier reports the stop condition is satisfied
