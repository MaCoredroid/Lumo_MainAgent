# Lumo Master Agent

`lumo-master-agent` is a Codex skill for running strict LumoAlpha-style implementation loops with tightly controlled sub-agent orchestration.

It is designed for workflows where the main agent must stay in control, sub-agents must operate in isolation, and progress only advances after explicit verification.

## What This Skill Does

This skill gives Codex a concrete operating model for:

- ordered LLD-driven implementation
- one sub-agent at a time
- isolated sub-agent prompts with `fork_context: false`
- implementation and live verification in the same sub-agent run
- repeated implementation loops until the declared stop condition is met
- commit-on-`main` execution without branches or worktrees
- push-to-spec-repo after verified working implementation

The main agent owns coordination. The sub-agent executes one bounded task. Verification is treated as a real gate, not a formality.

## When To Use It

Use this skill when the user wants a strict orchestration pattern rather than ad hoc delegation.

Typical cases:

- an ordered list of LLDs must be implemented in sequence
- every implementation step must be live-verified before the next step starts
- sub-agents must not inherit parent chat context
- sub-agents must commit their own fixes and push verified commits to the configured spec git repo
- only one worker may run at a time
- the loop should continue until a terminal state like `FULL_SEQUENCE_GOOD`

If the task is a normal coding request without this control model, a regular Codex workflow is usually simpler.

## Core Operating Contract

The skill enforces a narrow contract:

- main agent owns loop state
- main agent owns any tracker document
- sub-agents work on `main` only
- no branches or worktrees
- no nested sub-agents
- no tracker edits by sub-agents
- implementation prompts use explicit status vocabularies
- implementation agents must live-verify real behavior before reporting success
- verified working implementation is committed first, then pushed to the configured spec git repo

That last rule matters. The handoff is only useful when the implementation is both working locally and present in the configured spec repository.

## Execution Model

The workflow uses one prompt mode.

### Implementation Mode

The active sub-agent implements one exact LLD or task, live-verifies the real behavior, fixes any spec gaps it can resolve, commits on `main`, pushes verified commits to the configured spec git repo, and must finish with one of:

- `SPEC_LANDED_VERIFIED_AND_PUSHED`
- `BLOCKED_NEEDS_USER_HELP`
- `FULL_SEQUENCE_GOOD`

The loop only advances when the implementation agent explicitly reports that the spec landed, was live-verified, and was pushed, or when the full sequence is good.

## Default LumoAlpha Assumptions

If a user says to run "the usual Lumo loop," this skill defaults to:

- work on `main`
- one sub-agent at a time
- `fork_context: false`
- no branches or worktrees
- no nested delegation
- sub-agents commit their own fixes
- sub-agents push verified commits to the configured spec git repo and branch
- Docker-backed or repo-approved test execution when it helps verify real behavior
- explicit LLD names in implementation prompts

## Inputs The Main Agent Should Capture

Before starting the loop, the main agent should have:

- the ordered task sequence
- the implementation-plus-live-verification prompt or template
- the stop condition
- test command policy
- the spec git repo remote and branch to push verified commits to
- any hard constraints around model, reasoning, tracker editing, or branching

If the user already provided these in-thread, the skill should proceed without re-asking.

## Repository Layout

- `SKILL.md`: the full skill instructions and loop logic
- `agents/openai.yaml`: skill metadata for Codex UI integration

## Example Use

Inside Codex, a user might invoke it with a request like:

```text
Use $lumo-master-agent to run the usual Lumo loop for these LLDs in order:
1. lld_001.md
2. lld_002.md
3. lld_003.md

Use implementation agents only, live verify each implementation, push verified commits to the spec git repo, keep work on main, no branches, and stop only on FULL_SEQUENCE_GOOD.
```

The main agent should then:

1. start the first implementation worker
2. wait for terminal status
3. advance only after the worker reports `SPEC_LANDED_VERIFIED_AND_PUSHED`
4. continue until the final stop condition is reached

## Why This Skill Exists

Most delegation systems fail when the control boundary is loose. This skill is intentionally opinionated:

- prompts are operational, not conversational
- status outputs are narrow and machine-actionable
- verification is live and tied to implementation, not a detached advisory pass
- the parent agent coordinates instead of freelancing implementation details

That makes it useful for long-running, high-discipline build sequences where correctness and sequencing matter more than raw speed.
