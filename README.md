# Lumo Master Agent

`lumo-master-agent` is a Codex skill for running strict LumoAlpha-style implementation loops with tightly controlled sub-agent orchestration.

It is designed for workflows where the main agent must stay in control, sub-agents must operate in isolation, and progress only advances after explicit verification.

## What This Skill Does

This skill gives Codex a concrete operating model for:

- ordered LLD-driven implementation
- one sub-agent at a time
- isolated sub-agent prompts with `fork_context: false`
- implementation and red-team phases with different terminal statuses
- repeated verification loops until the declared stop condition is met
- commit-on-`main` execution without branches or worktrees

The main agent owns coordination. The sub-agent executes one bounded task. Verification is treated as a real gate, not a formality.

## When To Use It

Use this skill when the user wants a strict orchestration pattern rather than ad hoc delegation.

Typical cases:

- an ordered list of LLDs must be implemented in sequence
- every implementation step must be red-teamed before the next step starts
- sub-agents must not inherit parent chat context
- sub-agents must commit their own fixes
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
- implementation and verification prompts use explicit status vocabularies
- a verifier that makes code changes must be replaced with a fresh verifier

That last rule matters. Once a verifier edits code, it is no longer just verifying the state it started from.

## Execution Model

The workflow alternates between two prompt modes.

### 1. Implementation Mode

The active sub-agent implements one exact LLD or task and must finish with one of:

- `IMPLEMENTED_AND_COMMITTED`
- `BLOCKED_NEEDS_USER_HELP`

### 2. Red-Team Mode

The verifier checks the explicitly named completed scope and must finish with one of:

- `FOUND_GAPS_FIXED_AND_COMMITTED`
- `GOOD_TO_START_<NEXT_STEP>`
- `FULL_SEQUENCE_GOOD`
- `BLOCKED_NEEDS_USER_HELP`

If the verifier fixes anything, the main agent launches a fresh verifier on the same scope. The loop only advances when the verifier explicitly clears it.

## Default LumoAlpha Assumptions

If a user says to run "the usual Lumo loop," this skill defaults to:

- work on `main`
- one sub-agent at a time
- `fork_context: false`
- no branches or worktrees
- no nested delegation
- sub-agents commit their own fixes
- Docker-backed or repo-approved test execution
- explicit LLD names in verification prompts

## Inputs The Main Agent Should Capture

Before starting the loop, the main agent should have:

- the ordered task sequence
- the implementation prompt or template
- the red-team prompt or template
- the stop condition
- test command policy
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

Use implementation and red-team prompts, keep work on main, no branches, and stop only on FULL_SEQUENCE_GOOD.
```

The main agent should then:

1. start the first implementation worker
2. wait for terminal status
3. launch a red-team worker on the completed scope
4. repeat verification until the verifier clears the next step
5. continue until the final stop condition is reached

## Why This Skill Exists

Most delegation systems fail when the control boundary is loose. This skill is intentionally opinionated:

- prompts are operational, not conversational
- status outputs are narrow and machine-actionable
- verification is looped, not one-shot
- the parent agent coordinates instead of freelancing implementation details

That makes it useful for long-running, high-discipline build sequences where correctness and sequencing matter more than raw speed.
