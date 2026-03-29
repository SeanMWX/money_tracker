# Test Environment

This directory provides an isolated way to run and validate the `money_tracker` script without relying on the current working directory.

## Goals

- Run `scripts/bookkeeping.py` safely against a test-only SQLite database
- Smoke-test the core bookkeeping commands locally
- Run a broader CLI test suite that covers the behaviors promised by `SKILL.md` and implemented by `scripts/bookkeeping.py`

## Files

- `setup.ps1`: create a local virtual environment for running tests
- `run_smoke.py`: local smoke test with no external dependency
- `run_cli_tests.py`: wrapper that runs the full `unittest` suite
- `test_bookkeeping_cli.py`: comprehensive script-focused tests

## Quick Start

From the repository root:

```powershell
pwsh -ExecutionPolicy Bypass -File .\test\setup.ps1
.\test\.venv\Scripts\python.exe .\test\run_smoke.py
.\test\.venv\Scripts\python.exe .\test\run_cli_tests.py
```

The smoke test and CLI tests use databases under `test/data/` by default and do not touch the home-directory database.

## Coverage

The full suite covers these script-facing capabilities:

- Database initialization
- Default account seeding plus account listing, reset, and deactivation
- Category creation, replacement, listing, and deactivation
- Recording expense and income entries with account selection
- Strict-category validation, strict-account validation, and fallback values
- Daily, weekly, monthly, and yearly reports with category and account breakdowns
- Recent transactions, latest entry, and period detail listing with account filters
- Recurring transaction schedule creation, listing, updates, due-date filtering, and deactivation
- Entry updates and deletions
- Historical category and account snapshot behavior after deactivation
- Database path resolution precedence and legacy fallback compatibility
- Validation failures for invalid limits, ids, dates, accounts, categories, and recurring intervals

## What Is Not Covered Here

Some `SKILL.md` behavior belongs to the agent layer rather than the script itself. This test directory does not try to simulate those parts:

- Natural-language intent routing
- Semantic category mapping from free-form Chinese prompts
- Relative date resolution such as "this month" or "latest"
- User-facing wording rules for final responses

Those behaviors depend on the OpenClaw agent prompt and orchestration around the script, not on the SQLite helper itself.

## Running The Suite

```powershell
.\test\.venv\Scripts\python.exe .\test\run_cli_tests.py
python -m unittest discover -s .\test -p "test_*.py" -v
```

## Notes

- All scripts resolve the repository root from their own file location and do not depend on the current shell working directory.
- `run_smoke.py` injects `--db <test db path>` automatically, so it does not mutate your default `~/.money_tracker/bookkeeping.db`.
- The full suite uses only the Python standard library.
