# Python Best Practices: A Practical Guide

**Audience:** Python developers shipping real code -- from juniors on their first project to seniors reviewing PRs.  
**Goal:** Actionable practices that reduce bugs, improve readability, and save review cycles.  
**Tone:** Direct, operator-style. No hype, no filler.

---

## 1. Name Things for What They Do

- `calculate_monthly_revenue()` beats `process_data()`.
- `user_email` is clear. `data` is not.
- If a function needs a comment explaining what it does, the name is wrong.

**Concrete example:** Refactor a 50-line function called `handle_stuff()` into three focused functions with descriptive names. Show before/after.

---

## 2. Add Type Hints to Every Function Signature

- Type annotations serve as documentation that never goes stale.
- Run `mypy` or `pyright` in CI to catch type errors before they ship.
- Use `TypedDict` or `dataclass` for structured data instead of raw dicts.

**Concrete example:** A function signature with and without type hints. Show how the typed version catches a bug at call site.

---

## 3. Catch Specific Exceptions, Never Bare `except:`

- Catch `FileNotFoundError`, `json.JSONDecodeError`, or custom domain exceptions.
- Log the exception. Do not swallow it.
- Use custom exception classes for business logic errors.

**Concrete example:** A file parser with three specific `except` blocks vs. a bare `except:` that hides a `TypeError`.

---

## 4. Write Tests That Catch Real Bugs

- Test behavior, not implementation details.
- Use `pytest` fixtures for setup, not copy-pasted boilerplate.
- Cover edge cases: empty input, `None`, boundary values.

**Concrete example:** A test suite for a CSV parser that handles malformed rows, encoding issues, and empty files. Three tests, each catching a different failure mode.

---

## 5. Pin Dependencies and Audit Them

- Pin versions in `requirements.txt` or use `pyproject.toml` with a lockfile.
- Separate dev dependencies (`pytest`, `ruff`) from production ones.
- Run `pip-audit` or `safety check` in CI to catch known vulnerabilities.

**Concrete example:** A `pyproject.toml` with `[project.dependencies]` and `[project.optional-dependencies]` sections.

---

## 6. Use Built-in Tools Before Reaching for Libraries

- `pathlib` over `os.path` for file operations.
- `dataclasses` over raw dicts for structured data.
- `itertools` and `collections` for common patterns (`Counter`, `defaultdict`, `chain`).
- `argparse` or `click` for CLI tools.

**Concrete example:** Replace a manual dictionary accumulation loop with `collections.Counter`. Show both versions.

---

## 7. Format and Lint Automatically

- Use `ruff` for linting and formatting (replaces `flake8` + `black` + `isort`).
- Add a pre-commit hook so code is clean before it hits CI.
- Configure `ruff` in `pyproject.toml` to match your team's style.

**Concrete example:** A `.pre-commit-config.yaml` with a single `ruff` hook. Five lines of config.

---

## 8. Separate Logic From I/O

- Pure functions do the work. Callers handle files, network, and user input.
- This makes functions testable without mocking the filesystem.
- Keep modules focused: one responsibility per file.

**Concrete example:** A function that parses JSON from a file string vs. one that opens the file, parses, and prints. Show how the first is testable; the second is not.

---

## 9. Document With Docstrings, Not Comments

- Write docstrings for public functions and classes.
- Include one usage example in the docstring (or as a doctest).
- Keep a README with setup instructions. Not a 50-page wiki.

**Concrete example:** A function with a Google-style docstring including Args, Returns, and Raises sections.

---

## 10. Profile Before Optimizing

- Use `cProfile` or `py-spy` to find actual bottlenecks.
- Do not optimize what does not matter.
- Prefer algorithmic improvements over micro-optimizations.

**Concrete example:** A loop that looked slow but was actually blocked by I/O. Profiled with `py-spy`, found the real bottleneck was a network call inside the loop.

---

## Takeaway

Good Python code is readable, tested, and boring. These practices are not about cleverness -- they are about making your code easy for the next person (including future you) to understand and change.
