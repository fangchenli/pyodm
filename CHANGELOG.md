# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New string-based decorator API for declaring dependencies
- `@` syntax for auto-resolving extras and dependency groups
- `as` syntax for module aliasing
- `->` syntax for specifying distribution names
- `resolve_extra_or_group()` method on `MetaSource` for auto-resolution

### Changed
- **BREAKING**: Removed dict-based `modules={}` syntax from decorator
- **BREAKING**: Removed `_flatten_module_info` function
- **BREAKING**: Removed `ModuleInfo` alias (use `ModuleSpec`)
- **BREAKING**: Removed `OptinalDependencyManager` typo alias

## [0.1.0] - 2024-12-28

### Added
- Initial release
- `OptionalDependencyManager` decorator for classes and functions
- Lazy loading of optional dependencies
- Version validation against specifiers
- Support for reading specifiers from package metadata (extras)
- Support for PEP 735 dependency groups
- `ModuleSpec` for managing module specifications
- `ModuleReport` for dependency status reporting
- `report()` method for generating dependency reports
- `py.typed` marker for PEP 561 typing support
- Pre-commit configuration with ruff and mypy

[Unreleased]: https://github.com/forge-labs-dev/optional-dependency-manager/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/forge-labs-dev/optional-dependency-manager/releases/tag/v0.1.0
