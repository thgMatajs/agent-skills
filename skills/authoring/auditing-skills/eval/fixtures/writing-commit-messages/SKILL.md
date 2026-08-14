---
name: writing-commit-messages
description: Use when the user asks for help writing or improving a git commit message, or wants staged changes summarized into a Conventional Commits message.
---

# Writing Commit Messages

Produce a Conventional Commits message from the staged diff.

## Inputs / output

- **Input:** the staged changes (`git diff --cached`). If nothing is staged, say so and stop.
- **Output:** a commit message in this exact shape:

```
<type>(<scope>): <subject>

<body: what changed and why, wrapped at 72 cols>
```

`type` ∈ feat, fix, refactor, docs, test, chore. `scope` is the affected area (omit if
unclear). Subject ≤ 50 chars, imperative mood.

## Steps

1. Read the staged diff.
2. Pick the single `type` that dominates the change; if two are equal, split the commit.
3. Write subject + body per the shape above.
4. **Check before returning:** subject ≤ 50 chars, imperative, one type. If it fails,
   revise and re-check.

## Examples

Input: added JWT login endpoint + token middleware
```
feat(auth): add JWT login and token validation

Add the login endpoint and middleware that validates bearer tokens on
protected routes.
```

Input: dates rendered in local time instead of UTC in reports
```
fix(reports): use UTC timestamps in date formatting

Report dates were rendered in local time, shifting them across timezones.
```
