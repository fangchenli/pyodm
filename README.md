# optional-dependency-manager

[![Tests](https://github.com/fangchenli/optional-dependency-manager/actions/workflows/test.yaml/badge.svg)](https://github.com/fangchenli/optional-dependency-manager/actions/workflows/test.yaml)
[![Lint](https://github.com/fangchenli/optional-dependency-manager/actions/workflows/lint.yaml/badge.svg)](https://github.com/fangchenli/optional-dependency-manager/actions/workflows/lint.yaml)
[![codecov](https://codecov.io/gh/fangchenli/optional-dependency-manager/branch/main/graph/badge.svg)](https://codecov.io/gh/fangchenli/optional-dependency-manager)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

A Python library for managing optional dependencies with lazy loading and version validation.

## Features

- **Lazy Loading**: Dependencies are only imported when first accessed, reducing startup time
- **Version Validation**: Automatically validates installed versions against specifiers
- **Decorator API**: Simple decorator-based interface for classes and functions
- **Metadata Integration**: Can read version specifiers from your package's `pyproject.toml`
- **Dependency Reporting**: Generate reports of all optional dependencies and their status

## Installation

```bash
pip install optional-dependency-manager
```

## Quick Start

```python
from optional_dependency_manager import OptionalDependencyManager

odm = OptionalDependencyManager()

@odm(modules={"numpy": {"specifiers": ">=1.20.0"}})
class DataProcessor:
    def process(self, data):
        np = self.modules["numpy"]
        return np.array(data).mean()

# numpy is only imported when accessing self.modules
processor = DataProcessor()
result = processor.process([1, 2, 3, 4, 5])
```

## Usage

### Basic Usage with Classes

```python
from optional_dependency_manager import OptionalDependencyManager

odm = OptionalDependencyManager()

@odm(modules={
    "pandas": {"specifiers": ">=2.0.0"},
    "numpy": {"specifiers": ">=1.20.0", "alias": "np"},
})
class DataAnalyzer:
    def analyze(self, data):
        pd = self.modules["pandas"]
        np = self.modules["np"]  # using alias
        df = pd.DataFrame(data)
        return np.mean(df.values)
```

### Basic Usage with Functions

```python
@odm(modules={"requests": {"specifiers": ">=2.25.0"}})
def fetch_data(url, modules):
    # modules is injected as a keyword argument
    response = modules["requests"].get(url)
    return response.json()
```

### Reading Specifiers from Package Metadata

If your package defines optional dependencies in `pyproject.toml`, you can read specifiers directly from there.

#### Using optional-dependencies (extras)

```toml
# pyproject.toml
[project.optional-dependencies]
ml = ["numpy>=1.20.0", "pandas>=2.0.0"]
```

```python
odm = OptionalDependencyManager(source="my-package")

@odm(modules={
    "numpy": {"from_meta": True, "extra": "ml"},
    "pandas": {"from_meta": True, "extra": "ml"},
})
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

@odm(modules={
    "numpy": {"from_meta": True, "group": "ml"},
    "pandas": {"from_meta": True, "group": "ml"},
})
class MLModel:
    def train(self, data):
        np = self.modules["numpy"]
        pd = self.modules["pandas"]
        # ...
```

To use dependency groups, install with the `groups` extra:

```bash
pip install optional-dependency-manager[groups]
```

Note: Dependency groups are only accessible during development (editable installs) since they are not included in package metadata.

### Handling Import Errors

When a dependency is missing or has an incompatible version, an `ImportError` is raised with helpful information:

```python
@odm(modules={"nonexistent": {"specifiers": ">=1.0.0"}})
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

@odm(modules={"numpy": {"specifiers": ">=1.20.0"}})
class ClassA:
    pass

@odm(modules={"pandas": {"specifiers": ">=2.0.0"}})
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

### Module Specification Options

| Option | Type | Description |
|--------|------|-------------|
| `specifiers` | `str` | Version specifier (e.g., `">=1.0.0,<2.0.0"`) |
| `alias` | `str` | Alternative name for accessing the module |
| `from_meta` | `bool` | Read specifier from package metadata |
| `extra` | `str` | Extra name for `[project.optional-dependencies]` |
| `group` | `str` | Group name for `[dependency-groups]` (PEP 735) |
| `distribution_name` | `str` | PyPI package name if different from import name |

### Packages with Different Import Names

Some packages have different PyPI names and import names (e.g., `scikit-learn` vs `sklearn`):

```python
@odm(modules={
    "sklearn": {
        "specifiers": ">=1.0.0",
        "distribution_name": "scikit-learn",
    }
})
class Classifier:
    def fit(self, X, y):
        sklearn = self.modules["sklearn"]
        return sklearn.linear_model.LogisticRegression().fit(X, y)
```

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

    def __call__(self, modules: dict[str, dict[str, str]]):
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
