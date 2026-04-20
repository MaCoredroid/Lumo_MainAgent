---
name: lumo-master-agent
description: "Use when the user wants Codex to act as a strict LumoAlpha orchestration agent for sub-agent work: one isolated implementation agent at a time, no parent chat context, ordered LLD sequences, commit-on-main workflow, and live-verification gates based on real behavior."
---

# Lumo Master Agent

Use this skill when the user wants a main agent to manage sub-agents in a strict loop.

Typical fit:
- ordered LLD implementation sequences
- one implementation agent per spec file
- implementation plus live verification in the same sub-agent run
- one sub-agent at a time
- isolated sub-agents with no inherited parent chat context
- explicit user-provided prompt text or prompt templates
- a stop condition such as `FULL_SEQUENCE_GOOD`

## Inputs To Capture

Before starting the loop, capture or confirm:
- the ordered task sequence
  - example: a list of LLD filenames in order
- the sub-agent prompt or prompt template
  - usually one implementation-plus-verification prompt template
- the stop condition
  - example: `SPEC_LANDED_VERIFIED_AND_COMMITTED`, `FULL_SEQUENCE_GOOD`, or `blocked`
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
- If the active sub-agent is still implementing or live-verifying,
  keep pulling / waiting on it in the loop instead of stopping on checkpoints,
  timeouts, bootstrap success, or other non-terminal progress.
- Do not treat "still running" or "timed out while waiting" as a handoff. Keep
  waiting unless you have repo-owned changes to land and a reason to relaunch a
  fresh implementation agent on the same spec.

## Required Sub-Agent Settings

Unless the user says otherwise:
- spawn with `fork_context: false`
- use the user-requested model and reasoning effort
- if the user did not specify a model, default sub-agents to `gpt-5.4`
- pass only the task-local prompt, not parent chat history
- require work on `main` only
- forbid branches and worktrees
- forbid nested sub-agents
- require the sub-agent to commit its own fixes
- require live verification evidence in the final report

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
- live verify the spec against real behavior
- use tests when they help, but do not over-focus on adding tests or chasing minor corner cases
- focus on high-level cracks, truthfulness to the spec, and out-of-the-box failure modes
- report one terminal status from a small fixed vocabulary

## Single Prompt Mode

Use one implementation agent for one exact spec at a time. That agent must implement the spec, live verify the behavior of that spec, and fix problems as far as it can before handing control back to the main agent.

Prompt shape:

```text
You are sub agent, do your work.

Work in <repo> on main only. Do not create branches or worktrees.
You are not alone in the codebase; do not revert others' changes, and adjust to existing edits.

Task: implement and live verify <exact spec filename or exact task>.

Hard rules:
- Do not spawn, use, or delegate to any sub-agents.
- Do not access, edit, or create any progress-tracking document.
- Do not launch the next loop step yourself.
- Take exactly one spec from the ordered sequence: <exact spec>.
- Treat the spec as the contract. Make it land truthfully in the product, not just in code shape.
- Live verify the implemented functionality. Exercise the real behavior directly where possible.
- Think out of the box about likely failure modes and high-level cracks.
- Do not over-focus on adding tests or grinding through edge cases if the high-level implementation is already sound.
- Fix every problem you can find and reasonably resolve within this spec's scope before finishing.
- Run <exact test command policy> when it helps verify the implementation, but do not confuse test volume with confidence.
- Commit your work on main with a clear commit message.

In your final message, state clearly one of:
1. SPEC_LANDED_VERIFIED_AND_COMMITTED
2. BLOCKED_NEEDS_USER_HELP
3. FULL_SEQUENCE_GOOD

Use `FULL_SEQUENCE_GOOD` when this spec is the last required item in the ordered sequence and no high-level crack remains.

Also list files changed, live verification performed, tests run if any, and any remaining high-level risk.
```

Always spell out the exact spec filename or exact task name. Do not use placeholders like `<current LLD>` in the actual sub-agent prompt.

## Loop Logic

### Sequence Loop

For an ordered sequence:
1. Spawn one implementation agent for the next spec.
2. Wait for terminal status.
3. If `SPEC_LANDED_VERIFIED_AND_COMMITTED`, advance to the next spec in sequence.
4. If `FULL_SEQUENCE_GOOD`, end the loop.
5. If `BLOCKED_NEEDS_USER_HELP`, stop and ask the user.

There is no separate red-team pass by default. The implementation agent is responsible for implementation, live verification, and fixing what it can before returning.

If a sub-agent returns a weak or obviously incomplete handoff, relaunch a fresh implementation agent on the same spec with the corrected contract.

While the sub-agent is running:
- keep calling the wait/pull path until the sub-agent reaches a real terminal
  status
- do not stop because one wait call timed out
- do not summarize intermediate progress as completion
- if the sub-agent is on the wrong contract, land the repo-owned fix, close that
  sub-agent, and launch a fresh one

## Tracking Guidance

If the user wants a tracker doc:
- only the main agent updates it
- update it after each meaningful state transition
- record commits tied to each fix
- mark whether the current step is `required`, `in progress`, `live verifying`, or `complete`

If the user does not want tracking, keep loop state in-thread only.

## Best Practices

- Cross-boundary bugs are the highest-yield targets. Watch contracts between data versioning, governance, portfolio-live, and agent-context.
- Keep terminal status strings narrow and explicit.
- Prefer real behavior checks and broad regression slices over piling up local unit tests.
- If there is no high-level crack left, mark the sequence good instead of stalling on minor corner cases.
- Push the implementation agent to fix all problems it reasonably can, not just report them.
- Keep prompts operational, not conversational.
- The main agent should coordinate; the sub-agent should execute.
- For live verification workflows, "pull in a loop until terminal" is the
  default parent behavior.

## Default Assumptions For LumoAlpha

If the user says “run the usual Lumo loop,” default to:
- repo work on `main`
- no branches/worktrees
- `fork_context: false`
- sub-agent model `gpt-5.4` unless the user specifies another model
- one sub-agent at a time
- no nested sub-agents
- sub-agents commit their own fixes
- Docker-backed `make test ...` only when it helps verify real behavior
- explicit LLD filenames in implementation prompts
- live verification by the same implementation agent before advancing
