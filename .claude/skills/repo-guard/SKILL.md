---
name: repo-guard
description: Keep the databus repo clean as it grows — verify new/changed backend code meets the project's docstring, type-hint, and structural conventions, and update any docs the change made stale. Invoke before committing a feature, or when asked to "check the repo stays clean" / "guard" / "compliance-check" a diff. Complements the automatic ruff PostToolUse hook (mechanical style, zero tokens); this skill covers what a linter can't judge: docstring accuracy, doc drift, and doc updates.
---

# repo-guard

Two layers keep databus release-clean:

1. **Automatic, zero-token** — the `ruff-guard.sh` PostToolUse hook lints every edited `backend/**.py` on save (docstring presence D1, imports, unused). You never invoke this; it just runs.
2. **On-demand, this skill** — dispatches ONE diff-scoped Sonnet agent for what ruff can't judge: are docstrings *accurate*, are type hints complete, did the change make a docs page or README stale. Run it before committing a chunk of work.

## Run protocol

1. **Scope to the diff — never scan the whole repo.**
   ```bash
   git -C <repo> diff --name-only main...HEAD    # committed work on the branch
   git -C <repo> diff --name-only                # unstaged, if reviewing WIP
   ```
   Keep only `backend/**.py` (skip `migrations/`, `tests/`, `gtfs-eta/`).
2. If nothing is in scope, say so and stop — spend nothing.
3. Dispatch ONE Sonnet agent (`model: sonnet`, general-purpose) with the brief below. Serialize if another agent is touching the git index.
4. Relay its result; it produces at most one style-fix commit and one docs commit.

## Conventions the agent checks (the databus bar)

| Area | Rule |
|---|---|
| Docstrings | One line, pep257, on every class/function. **Accurate — never restates the name.** ruff D1 enforces presence; you judge truth. Config ignores `tests/`, `__init__.py` (D104), nested `Meta` classes (D106). |
| Type hints | Complete signatures. mypy (docker, lenient) gates presence. |
| Redis | Never inline `redis.Redis(...)`. Always `from databus.redis_client import create_redis_client`; preserve `decode_responses` per call site (lifecycle guards/actions use bytes → `False`). |
| Secrets | No hardcoded tokens/passwords/keys, ever. Read from env / `config()`. |
| Tests | Live in a `tests/` package as `test_*.py`. A file named `tests.py` is never collected → dead. |
| Serializers | No duplicate field / `fields="__all__"` declarations. |
| Files | Small, focused; immutable patterns; no dead code. |
| Commits | Conventional (`type(scope): …`); one concern each; NO attribution footers; never push. |

## Docs discipline

When changed code touches a documented behavior, the docs must follow — docs describe **as-built reality**, never aspirational or stale claims.

- Find affected pages cheaply: `grep -rl <changed-module-or-symbol> docs/content/ backend/**/README.md` — read only the hits, not the docs tree.
- Update the page + the app README if either now reads wrong.
- Rebuild: `cd docs && uv run zensical build` → must print "No issues found". `docs/site/` is gitignored — never commit it.

## Gates (authoritative — IDE/Pyright diagnostics are noise)

- `make lint` — run on the **host** (in-container ruff can't see `.gitignore`, false-flags vendored `gtfs-django/`). Expect "All checks passed!".
- `make typecheck` — mypy in docker; only acceptable errors are in vendored `gtfs-django/`.
- `docker compose -f compose.dev.yml run --rm orchestrator uv run pytest -q` — full suite stays green; the count must not drop.

## Sub-agent brief (paste, substituting REPO and FILES)

> You are a databus repo-cleanliness guard. Work only within these changed files: FILES (all under REPO/backend). Do NOT read the rest of the repo except the specific `docs/content/**` pages or `README.md` files that `grep` shows reference a symbol you changed. Read each file once.
>
> Check each changed file against the databus conventions: docstring accuracy (one line, pep257, never merely restating the name — fix wrong/tautological ones), complete type hints, Redis via `create_redis_client` only, no hardcoded secrets, no `tests.py` (must be `tests/test_*.py`), no duplicate serializer declarations. Fix violations in place — behavior-neutral only; never alter logic to satisfy a linter.
>
> Then check docs drift: for each changed module / public symbol, `grep -rl <name> docs/content/ **/README.md`; read only hits; update any page/README that now reads wrong so it matches the code. Rebuild docs with `cd docs && uv run zensical build` (must say "No issues found"; do not commit `docs/site/`).
>
> Produce up to two commits, staged with explicit `git add`: `style/fix(<scope>): …` for code, `docs(<scope>): …` for docs. Conventional messages, NO attribution footers, do NOT push. Gates before reporting: `make lint` (host) clean, `make typecheck` only gtfs-django errors, `pytest -q` green with no count drop. Report commit hashes, `git show --stat`, gate output, and anything you fixed or found unfixable.

## Efficiency contract (why this stays cheap)

- Mechanical style costs **zero** tokens (the ruff hook, not an agent).
- The agent reads **only the diff + grep-matched doc pages** — never the tree.
- One agent, at most two commits, one pass. No speculative exploration.
