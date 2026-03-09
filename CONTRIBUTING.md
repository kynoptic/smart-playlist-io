# Contributing to smart-playlist-io

Thanks for contributing! This guide covers setup, testing, and the PR process.

## Development setup

> [!IMPORTANT]
> Requires Python 3.12+.

```bash
make init    # Create .venv, install dev dependencies, and install pre-commit hooks
make test    # Run the full test suite (pytest + mypy baseline check)
make typecheck  # Run mypy type checks only (src + tests)
make clean   # Remove .venv and caches
```

`make init` installs pre-commit hooks that enforce commit message conventions locally. If you skip `make init` and commit directly, the CI check will catch violations on push.

## Testing

Follow TDD: write a failing test first, make it pass, then refactor.

```bash
make test    # pytest + mypy type checks
```

All new behaviour and bug fixes must have test coverage. Tests live in `tests/` and mirror the source module they cover.

## Commit conventions

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>: <description>
```

- **Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`
- **Subject line**: 50 characters max, imperative mood, no trailing period
- One logical change per commit — don't bundle unrelated changes

Examples:
```
feat: add between operator for integer fields
fix: correct skip-length for nested OR nodes
docs: update field table in README
```

## Pull request process

1. Branch from `main`. If there's a linked issue, use `issue-<id>-<slug>` (e.g. `issue-42-date-field-fix`); otherwise use a descriptive slug (e.g. `add-between-operator`). Creating an issue first is preferred
2. Open a PR that links the relevant issue (`Closes #<N>`) when one exists
3. Ensure `make test` passes locally before requesting review
4. Keep PRs focused — one feature or fix per PR

> [!NOTE]
> PRs are squash-merged. Your branch history doesn't need to be perfect, but each commit in the branch should be coherent.
