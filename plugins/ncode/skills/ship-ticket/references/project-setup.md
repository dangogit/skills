# Ticket workflow section for a project

When a repo's `CLAUDE.md` or `AGENTS.md` says nothing about how tickets move, offer to add this section, filled in from what the repo actually has. Write it only after the user agrees. Keep only the lines that apply.

```markdown
## Ticket workflow

Tickets are worked with the `ship-ticket` skill.

- Tracker: GitHub issues in [owner/repo]. Board: [GitHub Project link, or "none"].
- Ready to pick: label `[ready-for-agent]`, no assignee, no open blocker.
- Claim: [command, or "assign yourself and set Status to In progress"].
- Blocked: [command, or "Status Blocked and a comment naming who and what"].
- Branch: `issue-<N>-<slug>` from `[main]`, one worktree per ticket when working in parallel.
- Checks before a PR: `[lint]`, `[typecheck]`, `[test]`, `[build]`.
- PR: body starts with `Closes #N`. [Who merges: "the user" or "the orchestrator session"].
- After merge: [refresh command, or "move newly unblocked tickets to Ready"].
```

The values in square brackets are what the repo uses. If a value is unknown, ask rather than guess.
