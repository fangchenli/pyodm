from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import wraps
from importlib.metadata import PackageNotFoundError, distribution, metadata, version
from importlib.util import LazyLoader, find_spec, module_from_spec
from inspect import isclass, isfunction
from pathlib import Path
from typing import Any, Literal

# tomllib is available in Python 3.11+, use tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet

# Optional dependency for PEP 735 dependency groups support
try:
    from dependency_groups import DependencyGroupResolver

    HAS_DEPENDENCY_GROUPS = True
except ImportError:
    HAS_DEPENDENCY_GROUPS = False
    DependencyGroupResolver = None  # type: ignore[misc, assignment]


def _flatten_module_info(
    module_info: dict[str, dict[str, str]],
) -> list[dict[str, str]]:
    """
    Flatten module_info dict into a list of dicts.

    ----------
    Parameters
    ----------
    module_info : dict[str, dict[str, str]]
        Dict of module info.

    -------
    Returns
    -------
    list[dict[str, str]]
        List of module info dicts.
    """
    module_info_list = []
    for module_name, info in module_info.items():
        info["module_name"] = module_name
        module_info_list.append(info)
    return module_info_list


@dataclass
class MetaSource:
    source: str
    requires: list[Requirement] = field(init=False, repr=True, hash=True)
    extras: list[str] = field(init=False, repr=True, hash=True)
    # PEP 735 dependency groups (read from pyproject.toml)
    dependency_groups: dict[str, list] | None = field(
        init=False, repr=False, hash=False
    )
    _group_resolver: Any = field(init=False, repr=False, hash=False)

    def __post_init__(self):
        meta = metadata(self.source)
        requires = meta.get_all("Requires-Dist")
        # get_all returns None if no entries found
        self.requires = [Requirement(req) for req in requires] if requires else []
        extras = meta.get_all("Provides-Extra")
        self.extras = extras if extras else []

        # Try to load dependency groups from pyproject.toml
        self.dependency_groups = None
        self._group_resolver = None
        self._load_dependency_groups()

    def _load_dependency_groups(self) -> None:
        """Load dependency groups from source pyproject.toml if available."""
        if not HAS_DEPENDENCY_GROUPS:
            return

        try:
            import json
            from urllib.parse import unquote, urlparse

            dist = distribution(self.source)

            # Try to read direct_url.json for editable installs
            pyproject_path = None
            try:
                direct_url_text = dist.read_text("direct_url.json")
                if direct_url_text is None:
                    raise FileNotFoundError
                direct_url = json.loads(direct_url_text)
                if direct_url.get("dir_info", {}).get("editable"):
                    # Editable install - get source directory from URL
                    url = direct_url.get("url", "")
                    if url.startswith("file://"):
                        # Use urllib.parse for proper file:// URL handling
                        parsed = urlparse(url)
                        # unquote handles %20 -> space, etc.
                        file_path = unquote(parsed.path)
                        # On Windows, path is /C:/... - remove leading slash
                        if (
                            len(file_path) > 2
                            and file_path[0] == "/"
                            and file_path[2] == ":"
                        ):
                            file_path = file_path[1:]
                        source_dir = Path(file_path)
                        pyproject_path = source_dir / "pyproject.toml"
            except FileNotFoundError:
                pass

            # Fallback: try locate_file (works for some install types)
            if pyproject_path is None or not pyproject_path.exists():
                located = dist.locate_file("pyproject.toml")
                pyproject_path = Path(str(located))

            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    pyproject = tomllib.load(f)
                    if "dependency-groups" in pyproject:
                        self.dependency_groups = pyproject["dependency-groups"]
                        self._group_resolver = DependencyGroupResolver(
                            self.dependency_groups
                        )
        except (PackageNotFoundError, FileNotFoundError, KeyError):
            # Package not found or pyproject.toml not available
            pass

    def get_specifier(self, target: str, extra: str | None = None) -> str:
        """Get version specifier from optional-dependencies (extras)."""
        env = {"extra": extra} if extra is not None else None
        if extra is not None and extra not in self.extras:
            raise ValueError(f"{extra} is not a valid extra for {self.source}\n")
        for requirement in self.requires:
            if target == requirement.name:
                if requirement.marker is None or requirement.marker.evaluate(
                    environment=env
                ):
                    return str(requirement.specifier)
        raise ImportError(f"{target} is not listed as a dependency of {self.source}\n")

    def get_specifier_from_group(self, target: str, group: str) -> str:
        """Get version specifier from dependency-groups (PEP 735)."""
        if not HAS_DEPENDENCY_GROUPS:
            msg = (
                "The 'dependency-groups' package is required to use the 'group' "
                "parameter. Install it with: "
                "pip install optional-dependency-manager[groups]"
            )
            raise ImportError(msg)

        if self.dependency_groups is None or self._group_resolver is None:
            msg = (
                f"No dependency groups found for {self.source}. "
                "Dependency groups are only available when pyproject.toml is "
                "accessible (e.g., during development with editable installs)."
            )
            raise ValueError(msg)

        if group not in self.dependency_groups:
            available = ", ".join(self.dependency_groups.keys())
            raise ValueError(
                f"'{group}' is not a valid dependency group for {self.source}. "
                f"Available groups: {available}\n"
            )

        # Resolve the group and find the target package
        try:
            requirements = self._group_resolver.resolve(group)
        except Exception as e:
            raise ValueError(
                f"Failed to resolve dependency group '{group}': {e}\n"
            ) from e

        for req in requirements:
            # DependencyGroupResolver returns Requirement objects directly
            if req.name == target:
                return str(req.specifier)

        raise ImportError(
            f"{target} is not listed in dependency group '{group}' of {self.source}\n"
        )


@dataclass
class ModuleSpec:
    """Stores module specification without importing. Validation/import is deferred."""

    module_name: str
    from_meta: bool = False
    specifiers: str | None = field(default=None, hash=True)
    alias: str | None = field(default=None, hash=False)
    extra: str | None = field(default=None, hash=True)
    # PEP 735 dependency group name (alternative to extra)
    group: str | None = field(default=None, hash=True)
    # Distribution name for packages where import name differs from package name
    # e.g., sklearn -> scikit-learn, yaml -> PyYAML
    distribution_name: str | None = field(default=None, hash=False)
    # Cache for load() result
    _load_cache: tuple[object | None, str | None, str | None] | None = field(
        default=None, init=False, repr=False, hash=False, compare=False
    )

    def __post_init__(self):
        if self.alias is None:
            self.alias = self.module_name

        if self.specifiers is None and not self.from_meta:
            self.specifiers = ">0.0.0,<9999.9999.9999"

    def load(self) -> tuple[object | None, str | None, str | None]:
        """
        Validate and import the module. Called at instantiation/call time.

        Results are cached after the first call.

        Returns:
            tuple of (module, installed_version, error_msg)
        """
        if self._load_cache is not None:
            return self._load_cache

        if self.module_name.startswith("."):
            msg = (
                "Relative imports are not supported, "
                "module_name must be an absolute path"
            )
            raise ValueError(msg)

        # Use distribution_name if provided, otherwise derive from module_name
        if self.distribution_name is not None:
            package_name = self.distribution_name
        else:
            package_name = (
                self.module_name.split(".")[0]
                if "." in self.module_name
                else self.module_name
            )

        # Check if installed and get version
        try:
            installed_version = version(package_name)
        except PackageNotFoundError:
            self._load_cache = (None, None, f"{package_name} is not installed\n")
            return self._load_cache

        # Validate version specifier
        try:
            specifier_set = SpecifierSet(self.specifiers or "")
        except InvalidSpecifier:
            msg = f"{self.specifiers} is not a valid specifier"
            self._load_cache = (None, installed_version, msg)
            return self._load_cache

        if installed_version not in specifier_set:
            msg = (
                f"{package_name} version {installed_version} "
                f"does not meet requirement {specifier_set}\n"
            )
            self._load_cache = (None, installed_version, msg)
            return self._load_cache

        # Import the module
        if self.module_name in sys.modules:
            module = sys.modules[self.module_name]
        else:
            spec = find_spec(self.module_name)
            if spec is None:
                msg = f"Cannot find module spec for {self.module_name}\n"
                self._load_cache = (None, installed_version, msg)
                return self._load_cache
            if spec.loader is None:
                msg = f"Module {self.module_name} has no loader\n"
                self._load_cache = (None, installed_version, msg)
                return self._load_cache

            loader = LazyLoader(spec.loader)
            spec.loader = loader
            module = module_from_spec(spec)
            sys.modules[self.module_name] = module
            spec.loader.exec_module(module)

        self._load_cache = (module, installed_version, None)
        return self._load_cache


# Keep ModuleInfo as an alias for backwards compatibility
ModuleInfo = ModuleSpec


def _format_dependency_error(
    spec: ModuleSpec, installed_version: str | None, source: str | None = None
) -> str:
    """
    Format a helpful error message for a missing or incompatible dependency.

    Parameters
    ----------
    spec : ModuleSpec
        The module specification that failed to load.
    installed_version : str | None
        The installed version, or None if not installed.
    source : str | None
        The package name for install hints (e.g., "strata" for
        "pip install strata[extra]").

    Returns
    -------
    str
        A formatted error message with installation hints.
    """
    pkg_name = spec.distribution_name or spec.module_name.split(".")[0]

    # Determine install hint based on extra or group
    if spec.extra and source:
        hint = f" (install: pip install {source}[{spec.extra}])"
    elif spec.group:
        hint = f" (install: uv sync --group {spec.group})"
    else:
        hint = ""

    if installed_version is None:
        # Not installed
        if spec.specifiers and spec.specifiers != ">0.0.0,<9999.9999.9999":
            return f"  - {pkg_name}: not installed (requires {spec.specifiers}){hint}"
        return f"  - {pkg_name}: not installed{hint}"

    # Installed but version mismatch
    return (
        f"  - {pkg_name}: installed {installed_version}, "
        f"requires {spec.specifiers}{hint}"
    )


@dataclass
class ModuleReport:
    """Report for a single module registration."""

    module_name: str
    specifier: str | None
    extra: str | None
    group: str | None
    installed_version: str | None
    status: Literal["satisfied", "missing", "version_mismatch"]
    used_by: str


@dataclass
class OptionalDependencyManager:
    source: str | None = field(default=None, hash=True)
    version_register: dict[str, str] = field(
        default_factory=dict, init=False, hash=True
    )
    usage_register: dict[str, list[str]] = field(
        default_factory=dict, init=False, hash=True
    )
    spec_register: list[tuple[ModuleSpec, str]] = field(
        default_factory=list, init=False, hash=False
    )
    requirements: list[Requirement] = field(init=False, hash=True, repr=False)
    metasource: MetaSource | None = field(init=False, repr=False, hash=False)

    def __post_init__(self):
        if self.source is not None:
            self.metasource = MetaSource(self.source)

    def __call__(self, modules: dict[str, dict[str, str]]):
        odm = self  # capture reference for use in checker

        def dependencies_decorator(target):
            if not (isclass(target) or isfunction(target)):
                msg = (
                    "dependencies decorator can only be applied to "
                    f"classes or functions, not {type(target)}"
                )
                raise TypeError(msg)

            # At decoration time: only validate input and create specs (no import)
            modules_flattend = _flatten_module_info(modules)
            for mod in modules_flattend:
                odm._validate_input(mod)
            module_specs = [ModuleSpec(**mod) for mod in modules_flattend]

            # Register usage and specs (but not versions yet - those come at load time)
            for spec in module_specs:
                if spec.module_name not in odm.usage_register:
                    odm.usage_register[spec.module_name] = []
                odm.usage_register[spec.module_name].append(target.__name__)
                # Track each spec with its target for reporting
                odm.spec_register.append((spec, target.__name__))

            if isclass(target):
                target_with_checker = type(
                    target.__name__,
                    (odm._make_checker(module_specs), target),
                    {},
                )
                return target_with_checker
            else:
                # For functions, wrap to load modules on first call
                return odm._make_function_wrapper(target, module_specs)

        return dependencies_decorator

    def _make_checker(self, module_specs: list[ModuleSpec]):
        odm = self

        class OptionalDependencyChecker:
            def __init__(inner_self, *args, **kwargs):  # noqa: N805
                inner_self._odm_modules_loaded = False
                inner_self._odm_modules_cache: dict[str, object | None] = {}
                # Pass through to parent class
                super(OptionalDependencyChecker, inner_self).__init__(*args, **kwargs)  # noqa: UP008

            @property
            def modules(inner_self):
                """Lazy-load modules on first access."""
                if not inner_self._odm_modules_loaded:
                    errors: list[str] = []

                    for spec in module_specs:
                        module, installed_version, _ = spec.load()
                        inner_self._odm_modules_cache[spec.alias] = module

                        # Register version on first successful load
                        if installed_version is not None:
                            odm.version_register[spec.module_name] = installed_version

                        if module is None:
                            errors.append(
                                _format_dependency_error(
                                    spec, installed_version, odm.source
                                )
                            )

                    if errors:
                        msg = "Missing or incompatible dependencies:\n" + "\n".join(
                            errors
                        )
                        raise ImportError(msg)

                    inner_self._odm_modules_loaded = True

                return inner_self._odm_modules_cache

        return OptionalDependencyChecker

    def _make_function_wrapper(self, func, module_specs: list[ModuleSpec]):
        odm = self
        modules_cache: dict[str, object | None] = {}
        loaded = False

        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal loaded
            if not loaded:
                # Load modules on first call
                errors: list[str] = []

                for spec in module_specs:
                    module, installed_version, _ = spec.load()
                    modules_cache[spec.alias] = module

                    if installed_version is not None:
                        odm.version_register[spec.module_name] = installed_version

                    if module is None:
                        errors.append(
                            _format_dependency_error(
                                spec, installed_version, odm.source
                            )
                        )

                if errors:
                    msg = "Missing or incompatible dependencies:\n" + "\n".join(errors)
                    raise ImportError(msg)

                loaded = True

            # Inject modules dict as keyword argument
            kwargs["modules"] = modules_cache
            return func(*args, **kwargs)

        # Also expose modules on wrapper for external access if needed
        wrapper.modules = modules_cache  # type: ignore[attr-defined]
        return wrapper

    def _validate_input(self, module_dict: dict[str, Any]) -> None:
        # Default from_meta to False if not provided
        if "from_meta" not in module_dict:
            module_dict["from_meta"] = False

        # Check for mutually exclusive extra and group
        has_extra = "extra" in module_dict
        has_group = "group" in module_dict

        if has_extra and has_group:
            raise ValueError(
                "Cannot specify both 'extra' and 'group'. "
                "Use 'extra' for optional-dependencies or "
                "'group' for dependency-groups."
            )

        if "specifiers" not in module_dict:
            if module_dict["from_meta"]:
                if self.source is not None and self.metasource is not None:
                    # Use distribution_name for metadata lookup if provided,
                    # otherwise derive from module_name
                    if "distribution_name" in module_dict:
                        target = module_dict["distribution_name"]
                    else:
                        target = module_dict["module_name"].split(".")[0]

                    if has_extra:
                        # Read from optional-dependencies (extras)
                        module_dict["specifiers"] = self.metasource.get_specifier(
                            target, module_dict["extra"]
                        )
                    elif has_group:
                        # Read from dependency-groups (PEP 735)
                        module_dict["specifiers"] = (
                            self.metasource.get_specifier_from_group(
                                target, module_dict["group"]
                            )
                        )
                    else:
                        raise KeyError(
                            "When 'from_meta' is True, "
                            "either 'extra' or 'group' must be set"
                        )
                else:
                    msg = (
                        "When 'from_meta' is True, a 'source' must be provided "
                        "to the OptionalDependencyManager"
                    )
                    raise ValueError(msg)

    def report(self) -> list[ModuleReport]:
        """
        Generate a report of all registered optional dependencies.

        This method triggers loading of all modules to determine their status.

        Returns
        -------
        list[ModuleReport]
            List of reports for each module registration.
        """
        reports: list[ModuleReport] = []

        for spec, used_by in self.spec_register:
            module, installed_version, _ = spec.load()

            # Register version if available
            if installed_version is not None:
                self.version_register[spec.module_name] = installed_version

            # Determine status
            if module is not None:
                status: Literal["satisfied", "missing", "version_mismatch"] = (
                    "satisfied"
                )
            elif installed_version is None:
                status = "missing"
            else:
                status = "version_mismatch"

            reports.append(
                ModuleReport(
                    module_name=spec.module_name,
                    specifier=spec.specifiers,
                    extra=spec.extra,
                    group=spec.group,
                    installed_version=installed_version,
                    status=status,
                    used_by=used_by,
                )
            )

        return reports


# Backwards compatibility alias for the typo
OptinalDependencyManager = OptionalDependencyManager
