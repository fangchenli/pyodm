# optional-dependency-manager

[![Tests](https://github.com/forge-labs-dev/optional-dependency-manager/actions/workflows/test.yaml/badge.svg)](https://github.com/forge-labs-dev/optional-dependency-manager/actions/workflows/test.yaml)
[![pre-commit](https://github.com/forge-labs-dev/optional-dependency-manager/actions/workflows/pre-commit.yaml/badge.svg)](https://github.com/forge-labs-dev/optional-dependency-manager/actions/workflows/pre-commit.yaml)
[![codecov](https://codecov.io/gh/forge-labs-dev/optional-dependency-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/forge-labs-dev/optional-dependency-manager)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/optional-dependency-manager)](https://pypi.org/project/optional-dependency-manager/)

A Python library for managing optional dependencies with lazy loading and version validation.

## Features

- **Lazy Loading**: Dependencies are only imported when first accessed, reducing startup time
- **Version Validation**: Automatically validates installed versions against specifiers
- **Decorator API**: Simple string-based decorator interface for classes and functions
- **Metadata Integration**: Can read version specifiers from your package's `pyproject.toml` extras or dependency groups
- **Dependency Reporting**: Generate reports of all optional dependencies and their status

## Installation

```bash
pip install optional-dependency-manager
```

## Quick Start

```python
from optional_dependency_manager import OptionalDependencyManager

odm = OptionalDependencyManager()

@odm("numpy>=1.20.0")
class DataProcessor:
    def process(self, data):
        np = self.modules["numpy"]
        return np.array(data).mean()

# numpy is only imported when accessing self.modules
processor = DataProcessor()
result = processor.process([1, 2, 3, 4, 5])
```

## Usage

### String Syntax

The decorator accepts module specifications as strings with a concise syntax:

```python
@odm("numpy")                    # any version
@odm("numpy>=1.20.0")            # version specifier
@odm("numpy@ml")                 # from extra or dependency group "ml"
@odm("numpy>=1.20 as np")        # with alias
@odm("sklearn->scikit-learn")    # distribution name differs from import
@odm("numpy", "pandas>=2.0")     # multiple modules
```

### Basic Usage with Classes

```python
from optional_dependency_manager import OptionalDependencyManager

odm = OptionalDependencyManager()

@odm("pandas>=2.0.0", "numpy>=1.20.0 as np")
class DataAnalyzer:
    def analyze(self, data):
        pd = self.modules["pandas"]
        np = self.modules["np"]  # using alias
        df = pd.DataFrame(data)
        return np.mean(df.values)
```

### Basic Usage with Functions

```python
@odm("requests>=2.25.0")
def fetch_data(url, modules):
    # modules is injected as a keyword argument
    response = modules["requests"].get(url)
    return response.json()
```

### Reading Specifiers from Package Metadata

If your package defines optional dependencies in `pyproject.toml`, you can read specifiers directly using the `@` syntax.

#### Using optional-dependencies (extras)

```toml
# pyproject.toml
[project.optional-dependencies]
ml = ["numpy>=1.20.0", "pandas>=2.0.0"]
```

```python
odm = OptionalDependencyManager(source="my-package")

@odm("numpy@ml", "pandas@ml")
class MLModel:
    def train(self, data):
        np = self.modules["numpy"]
        pd = self.modules["pandas"]
        # ...
```

#### Using dependency-groups (PEP 735)

For packages using uv or other tools supporting PEP 735 dependency groups:

```toml
# pyproject.toml
[dependency-groups]
ml = ["numpy>=1.20.0", "pandas>=2.0.0"]
```

```python
odm = OptionalDependencyManager(source="my-package")

# Same syntax - automatically resolves to group if not found in extras
@odm("numpy@ml", "pandas@ml")
class MLModel:
    def train(self, data):
        np = self.modules["numpy"]
        pd = self.modules["pandas"]
        # ...
```

The `@` syntax automatically checks both extras and dependency groups. If a name exists in both, an error is raised asking you to disambiguate.

To use dependency groups, install with the `groups` extra:

```bash
pip install optional-dependency-manager[groups]
```

Note: Dependency groups are only accessible during development (editable installs) since they are not included in package metadata.

### Handling Import Errors

When a dependency is missing or has an incompatible version, an `ImportError` is raised with helpful information:

```python
@odm("nonexistent>=1.0.0")
class MyClass:
    pass

instance = MyClass()
instance.modules  # Raises ImportError
```

```
ImportError: Missing or incompatible dependencies:
  - nonexistent: not installed (requires >=1.0.0)
```

### Generating Dependency Reports

You can generate a report of all registered optional dependencies:

```python
odm = OptionalDependencyManager()

@odm("numpy>=1.20.0")
class ClassA:
    pass

@odm("pandas>=2.0.0")
class ClassB:
    pass

# Generate report (triggers loading to check versions)
reports = odm.report()

for r in reports:
    print(f"{r.module_name}: {r.status} (used by {r.used_by})")
    if r.installed_version:
        print(f"  Installed: {r.installed_version}")
    if r.specifier:
        print(f"  Required: {r.specifier}")
```

### Packages with Different Import Names

Some packages have different PyPI names and import names (e.g., `scikit-learn` vs `sklearn`). Use the `->` syntax:

```python
@odm("sklearn>=1.0.0->scikit-learn")
class Classifier:
    def fit(self, X, y):
        sklearn = self.modules["sklearn"]
        return sklearn.linear_model.LogisticRegression().fit(X, y)
```

### Full Syntax Reference

| Syntax | Description |
|--------|-------------|
| `"numpy"` | Any version of numpy |
| `"numpy>=1.20"` | numpy with version constraint |
| `"numpy@ml"` | numpy from extra or group "ml" (auto-resolved) |
| `"numpy as np"` | numpy with alias "np" |
| `"numpy->numpy-pkg"` | import as numpy, but package name is numpy-pkg |
| `"numpy@ml as np"` | from extra/group with alias |
| `"sklearn@ml->scikit-learn as sk"` | full syntax with all options |

## API Reference

### OptionalDependencyManager

```python
class OptionalDependencyManager:
    def __init__(self, source: str | None = None):
        """
        Initialize the manager.

        Args:
            source: Package name for reading metadata (optional)
        """

    def __call__(self, *args: str):
        """Decorator for classes or functions."""

    def report(self) -> list[ModuleReport]:
        """Generate a report of all registered dependencies."""
```

### ModuleReport

```python
@dataclass
class ModuleReport:
    module_name: str
    specifier: str | None
    extra: str | None
    group: str | None
    installed_version: str | None
    status: Literal["satisfied", "missing", "version_mismatch"]
    used_by: str
```

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=optional_dependency_manager

# Type checking
uv run mypy src/

# Linting
uv run ruff check .

# Formatting
uv run ruff format .
```

## License

MIT License - see [LICENSE](LICENSE) for details.
