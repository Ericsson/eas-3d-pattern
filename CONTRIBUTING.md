# Contributing to eas-3d-pattern

## Principles

- Every change must be correct, traceable, and reviewable.
- Small, focused changes are preferred over large, mixed-purpose commits.
- Code that cannot be tested should not be merged.
- Automation gates enforce quality.

## Before Submitting

All tests, and linting should pass locally before opening a PR.
Do not rely on CI to catch what you can catch locally.

## Commit Guidelines

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <short summary>
```

Types: `feat`, `fix`, `docs`, `ci`, `chore`, `refactor`, `test`, `perf`

Rules:
- One logical change per commit.
- The summary must describe *what* changed, not *how*.
- Commit messages are allowed to contain paragraphs for explanation
- Never rewrite published history (no rebase, no force push, no amend after push).

## Branch Workflow

1. Create a branch from `main` with a descriptive name: `feat/beam-efficiency-polar`, `fix/theta-tilt-key`.
2. Keep the branch up to date with `git merge main` (never rebase).
3. Open a PR when ready. Draft PRs are fine for early feedback.
4. CI must pass and at least one maintainer must approve before merge.
5. Branches are deleted after merge.
6. Before opening a PR, merge latest main and verify lint + tests pass.

## Code Standards

- Follow existing code style — Ruff enforces this automatically.
- Type annotations are required for all public interfaces.
- Docstrings follow [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- No dead code. No commented-out code. Remove it or don't commit it.
- Functions should do one thing. If you can't name it clearly, it's doing too much.

## Testing

- Every bug fix must include a test that reproduces the bug.
- Every new feature must include tests covering its intended behavior.
- Tests must be deterministic — no dependence on network, timing, or filesystem state.
- Prefer unit tests. Integration tests are acceptable for schema validation and I/O.

## Dependencies

- Pin exact versions for stubs and dev tools.
- Use version ranges for runtime dependencies when possible (as declared in `pyproject.toml`).
- Adding a new runtime dependency requires justification in the PR description.
- Check that packages are well-known and actively maintained before proposing them.

## Reporting Issues

- Search existing issues before opening a new one.
- Include: what you expected, what happened, minimal reproduction steps, and your environment (Python version, OS, package version).

## Review Process

- Reviewers check correctness first, style second.
- If CI fails, the PR is not ready for review.
- Address all review comments. If you disagree, explain why.
