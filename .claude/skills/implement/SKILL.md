---
name: implement
description: Implement one approved phase from a PRD and plan using feedback loops.
argument-hint: "@prd/<feature>.md @plans/<feature>.md implement phase <N>"
disable-model-invocation: true
---

# Implement

## 1. Understand the Phase

Read the referenced PRD and plan. Explore the codebase to understand the relevant files,
patterns, and conventions. If the request does not identify a phase, ask which one.

Implement only that phase. Do not begin the next one.

## 2. Implement the Phase

Run the `tdd` skill and follow its instructions to implement key behaviors test-first. Implement the remaining requirements using the project's normal process, as TDD will only pick a few important behaviors to test.

## 3. Run Feedback Loops

Run the project's test suite, linter, formatter, and any additional feedback loops according to existing project conventions. Ensure all checks pass cleanly and resolve any failures or violations before proceeding.

## 4. Manual Verification

Answer this question with clear steps for the user: "How do I verify this phase or feature manually in the browser?" Then stop and wait for the user. The phase is not finished until the user confirms that manual verification passed.

## 5. Finish the Phase

1. Update `PROMPTS.md` using the format specified in that file.
2. Commit the completed phase.
3. Push the commit to GitHub.