# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PyODM (Python Optional Dependency Manager) is a library for managing optional dependencies in Python projects. It provides a decorator-based API for lazy loading modules with version constraint validation.

## Development Commands

```bash
# Install dependencies (creates .venv automatically)
uv sync --all-extras

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_odm.py::test_name

# Run tests with coverage
uv run pytest --cov=pyodm

# Type checking
uv run mypy src/

# Linting
uv run ruff check .

# Formatting
uv run black .
uv run isort .

# Update dependencies
uv lock --upgrade
```

## Architecture

The library is implemented in a single module (`src/pyodm/odm.py`) with three main dataclasses:

1. **MetaSource** - Extracts package metadata from installed distributions using `importlib.metadata`. Retrieves dependency specifications and extras, evaluates version requirements and markers.

2. **ModuleInfo** - Manages individual module information. Validates module installations and version constraints against specifiers. Handles lazy loading via `importlib.util.LazyLoader`. Supports module aliasing.

3. **OptionalDependencyManager** - Main API, used as a decorator on classes/functions. Registers module usage and versions. Creates an `OptionalDependencyChecker` mixin for classes that validates dependencies at instantiation time.

### Usage Pattern

```python
odm = OptionalDependencyManager(source="my-package")

@odm({"numpy": {"from_meta": True, "extra": "math"}})
class MyClass:
    def compute(self):
        np = self.modules["numpy"]
        # use numpy...
```

## Commit Message Convention

Use semantic prefixes: `BUG:`, `TST:`, `DOC:`, etc.
