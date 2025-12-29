# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

optional-dependency-manager is a library for managing optional dependencies in Python projects. It provides a string-based decorator API for lazy loading modules with version constraint validation.

## Development Commands

```bash
# Install dependencies (creates .venv automatically)
uv sync --group dev

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_odm.py::test_name

# Run tests with coverage
uv run pytest --cov=optional_dependency_manager

# Type checking
uv run mypy src/

# Linting
uv run ruff check .

# Formatting
uv run ruff format .

# Update dependencies
uv lock --upgrade
```

## Architecture

The library is implemented in a single module (`src/optional_dependency_manager/odm.py`) with three main dataclasses:

1. **MetaSource** - Extracts package metadata from installed distributions using `importlib.metadata`. Retrieves dependency specifications from extras and PEP 735 dependency groups from `pyproject.toml`.

2. **ModuleSpec** - Manages individual module information. Validates module installations and version constraints against specifiers. Handles lazy loading via `importlib.util.LazyLoader`. Supports module aliasing.

3. **OptionalDependencyManager** - Main API, used as a decorator on classes/functions. Registers module usage and versions. Creates an `OptionalDependencyChecker` mixin for classes that validates dependencies at instantiation time.

### Usage Pattern

```python
from optional_dependency_manager import OptionalDependencyManager

odm = OptionalDependencyManager(source="my-package")

# String-based syntax
@odm("numpy@ml")                    # from extra or group "ml"
@odm("numpy>=1.20")                 # version specifier
@odm("numpy@ml as np")              # with alias
@odm("sklearn@ml->scikit-learn")    # distribution name differs
@odm("numpy", "pandas@ml")          # multiple modules

# Example class
@odm("numpy@ml", "pandas@ml")
class MyClass:
    def compute(self):
        np = self.modules["numpy"]
        pd = self.modules["pandas"]
        # use numpy and pandas...
```

## Commit Message Convention

Use semantic prefixes: `BUG:`, `TST:`, `DOC:`, `ENH:`, `PERF:`, etc.
