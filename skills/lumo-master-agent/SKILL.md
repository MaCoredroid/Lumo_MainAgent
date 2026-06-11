---
name: lumo-master-agent
description: "Use when the user wants Codex to act as a LumoAlpha main agent for dynamic subagent orchestration: recover prior context when needed, decompose live goals, spawn isolated subagents one goal at a time, monitor their progress, review completed outcomes against the user's objective, and decide the next goal until the work is verified, committed, pushed, or genuinely blocked."
---

# Lumo Master Agent

Use this skill when the user wants a main agent to coordinate LumoAlpha work through isolated implementation subagents.

Typical fit:
- open-ended goals that need dynamic decomposition
- previous Claude Code workflow/session context needs to guide current work
- one active subagent at a time
- isolated subagents with no inherited parent chat context
- main-agent monitoring while subagents run
- main-agent outcome review after each subagent finishes
- commit-on-`main` and push-after-verification workflows

## Inputs To Capture

Before spawning a subagent, identify:
- the current user goal in concrete terms
- the repo path, branch constraints, and whether work must stay on `main`
- any known prior context, handoff, workflow, or Claude Code session that matters
- the next bounded subgoal that one subagent can execute and verify
- the stop condition, such as `GOAL_VERIFIED_AND_PUSHED`, `ALL_GOALS_COMPLETE`, or `BLOCKED_NEEDS_USER_HELP`
- the test or live-verification policy
- the target remote and branch for verified commits, unless the user disables pushing

If the user already supplied these in-thread or they are available from local context, do not ask again.

## Previous Claude Workflow Context

When the user asks to resume previous Claude Code work, continue a trail, or use recent Claude sessions as context, first use the sibling `claude-session-context` skill if available.

Read the summary and any relevant memory/workflow files before spawning subagents. Previous Claude Code workflow runs are useful because they show how the main agent decomposed goals, monitored workflow outputs, verified landed work, and selected the next subgoal. Treat those records as context, not authority: verify current repo state before acting.

## Main-Agent Responsibilities

- Own the current goal stack and decide the next subgoal dynamically.
- Spawn a subagent only when there is a clear bounded goal for it.
- Keep only one subagent active at a time unless the user explicitly permits parallel work.
- Spawn subagents with isolated context; pass task-local instructions, not parent chat history.
- Monitor the active subagent until it reaches a real terminal status.
- Do not treat "still running", "waiting", "timeout", setup progress, or partial test output as completion.
- Read the subagent's final report, inspect changed files and commits, and verify the result against the original user goal.
- Challenge weak outcomes: check whether the delivered behavior actually works, whether important failure modes remain, and whether the result is truthfully committed and pushed.
- If the outcome is incomplete but fixable, launch a fresh bounded subagent with the corrected goal.
- If the outcome is complete, decide the next goal or stop with a clear completion report.
- If the same blocker persists after repeated attempts, stop and ask the user for the missing decision or external state.

## Required Subagent Defaults

Unless the user says otherwise:
- spawn with `fork_context: false`
- use the user-requested model and reasoning effort
- if the user did not specify a model, default subagents to `gpt-5.4`
- require work on `main` only
- forbid branches and worktrees
- forbid nested subagents
- require the subagent to commit its own fixes
- require the subagent to push verified commits to the configured remote and branch
- require live verification evidence in the final report

## Prompt Discipline

Start every subagent prompt with:

```text
You are sub agent, do your work.
```

Then give one bounded goal and the hard rules. Do not ask a subagent to run the whole project unless that is genuinely the next bounded goal.

Default rules to include:
- work on `main` only
- do not create branches or worktrees
- do not spawn or use subagents
- do not edit any progress-tracking document unless explicitly told
- do not choose or launch the next goal yourself
- implement the assigned goal truthfully in the product, not just in code shape
- live verify real behavior where possible
- run the specified tests or the smallest useful verification slice
- commit verified work with a clear commit message
- push verified commits to the configured remote and branch when pushing is enabled
- report one terminal status from the allowed vocabulary

## Prompt Shape

```text
You are sub agent, do your work.

Work in <repo> on main only. Do not create branches or worktrees.
You are not alone in the codebase; do not revert others' changes, and adjust to existing edits.

Goal: <one bounded implementation, verification, or investigation goal>.

Context:
- <task-local facts from user, repo, handoff, or Claude workflow context>
- <files or commands likely relevant>

Hard rules:
- Do not spawn, use, or delegate to any subagents.
- Do not launch the next goal yourself.
- Treat the goal as the contract. Make it land truthfully in the product.
- Live verify the result against real behavior where possible.
- Fix every problem you can reasonably resolve within this goal's scope.
- Run <exact test command policy> when it helps verify the goal.
- Commit your work on main with a clear commit message.
- If the implementation is working and pushing is enabled, push the verified commit(s) to <remote> <branch>.

In your final message, state clearly one of:
1. GOAL_VERIFIED_AND_PUSHED
2. GOAL_VERIFIED_COMMITTED_NOT_PUSHED
3. BLOCKED_NEEDS_USER_HELP
4. ALL_GOALS_COMPLETE

Also list files changed, live verification performed, tests run if any, commit hashes, push result, and remaining risk.
```

Always spell out the exact goal. Do not leave placeholders like `<next task>` in the actual subagent prompt.

## Dynamic Loop Logic

1. Recover context if needed, including previous Claude Code workflow context.
2. Inspect current repo state and identify the next bounded goal.
3. Spawn one isolated subagent for that goal.
4. Monitor until a terminal status is reached.
5. Review the outcome against the user's original objective and current repo state.
6. If verified and more work remains, choose the next bounded goal and repeat.
7. If verified and no meaningful work remains, stop with `ALL_GOALS_COMPLETE`.
8. If blocked, either launch a corrected bounded follow-up or stop with the specific user decision needed.

While the subagent is running:
- keep polling or waiting through non-terminal progress
- inspect task output when available
- do not summarize intermediate progress as completion
- if the subagent is clearly on the wrong contract, close it if possible and launch a corrected one

## Outcome Review

After each subagent finishes, the main agent must independently review:
- whether the reported terminal status matches the evidence
- whether changed files match the intended goal
- whether verification exercised real behavior rather than only static shape
- whether commits and pushes happened when required
- whether the next goal changed based on the result

Use previous Claude Code workflow patterns as a reference for this responsibility: the main agent observes workflow outputs, reads the produced artifacts, verifies claims, commits or pushes only verified state, and then selects the next bounded goal.

## Tracking Guidance

If the user wants a tracker doc:
- only the main agent updates it
- update it after each meaningful state transition
- record goals, status, commits, verification, and push state
- mark whether the current goal is `queued`, `running`, `reviewing`, `complete`, or `blocked`

If the user does not want tracking, keep loop state in-thread only.

## Best Practices

- Keep subagent goals small enough to review.
- Prefer real behavior checks over piling up local unit tests.
- Do not keep launching workers when the missing input is a user decision.
- Verified working implementation should be committed first, then pushed when required.
- Keep prompts operational, not conversational.
- The main agent coordinates, monitors, reviews, and selects next goals; the subagent executes one bounded goal.

## Default Assumptions For LumoAlpha

If the user says "run the usual Lumo loop," default to:
- repo work on `main`
- no branches/worktrees
- `fork_context: false`
- subagent model `gpt-5.4` unless the user specifies another model
- one active subagent at a time
- no nested subagents
- subagents commit their own fixes
- subagents push verified commits to the configured remote and branch
- Docker-backed or repo-approved test execution when it helps verify real behavior
- dynamic goal selection by the main agent
- main-agent outcome review after each subagent finishes
