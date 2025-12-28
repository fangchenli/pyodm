from __future__ import annotations

import sys
from dataclasses import dataclass, field
from functools import wraps
from importlib.metadata import PackageNotFoundError, metadata, version
from importlib.util import LazyLoader, find_spec, module_from_spec
from inspect import isclass, isfunction
from typing import Any

from packaging.requirements import Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet


def _flatten_module_info(
    module_info: dict[str, dict[str, str]]
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

    def __post_init__(self):
        meta = metadata(self.source)
        requires = meta.get_all("Requires-Dist")
        # get_all returns None if no entries found
        self.requires = [Requirement(req) for req in requires] if requires else []
        extras = meta.get_all("Provides-Extra")
        self.extras = extras if extras else []

    def get_specifier(self, target: str, extra: str | None = None) -> str:
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


@dataclass
class ModuleSpec:
    """Stores module specification without importing. Validation/import is deferred."""

    module_name: str
    from_meta: bool = False
    specifiers: str | None = field(default=None, hash=True)
    alias: str | None = field(default=None, hash=False)
    extra: str | None = field(default=None, hash=True)
    # Distribution name for packages where import name differs from package name
    # e.g., sklearn -> scikit-learn, yaml -> PyYAML
    distribution_name: str | None = field(default=None, hash=False)

    def __post_init__(self):
        if self.alias is None:
            self.alias = self.module_name

        if self.specifiers is None and not self.from_meta:
            self.specifiers = ">0.0.0,<9999.9999.9999"

    def load(self) -> tuple[object | None, str | None, str | None]:
        """
        Validate and import the module. Called at instantiation/call time.

        Returns:
            tuple of (module, installed_version, error_msg)
        """
        if self.module_name.startswith("."):
            raise ValueError(
                "Relative imports are not supported, module_name must be an absolute path"
            )

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
            return None, None, f"{package_name} is not installed\n"

        # Validate version specifier
        try:
            specifier_set = SpecifierSet(self.specifiers or "")
        except InvalidSpecifier:
            return None, installed_version, f"{self.specifiers} is not a valid specifier"

        if installed_version not in specifier_set:
            return (
                None,
                installed_version,
                f"{package_name} version {installed_version} does not meet requirement {specifier_set}\n",
            )

        # Import the module
        if self.module_name in sys.modules:
            module = sys.modules[self.module_name]
        else:
            spec = find_spec(self.module_name)
            if spec is None:
                return None, installed_version, f"Cannot find module spec for {self.module_name}\n"
            if spec.loader is None:
                return None, installed_version, f"Module {self.module_name} has no loader\n"

            loader = LazyLoader(spec.loader)
            spec.loader = loader
            module = module_from_spec(spec)
            sys.modules[self.module_name] = module
            spec.loader.exec_module(module)

        return module, installed_version, None


# Keep ModuleInfo as an alias for backwards compatibility
ModuleInfo = ModuleSpec


@dataclass
class OptionalDependencyManager:
    source: str | None = field(default=None, hash=True)
    version_register: dict[str, str] = field(
        default_factory=dict, init=False, hash=True
    )
    usage_register: dict[str, list[str]] = field(
        default_factory=dict, init=False, hash=True
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
                raise TypeError(
                    f"dependencies decorator can only be applied to classes or functions, not {type(target)}"
                )

            # At decoration time: only validate input and create specs (no import)
            modules_flattend = _flatten_module_info(modules)
            for mod in modules_flattend:
                odm._validate_input(mod)
            module_specs = [ModuleSpec(**mod) for mod in modules_flattend]

            # Register usage (but not versions yet - those come at load time)
            for spec in module_specs:
                if spec.module_name not in odm.usage_register:
                    odm.usage_register[spec.module_name] = []
                odm.usage_register[spec.module_name].append(target.__name__)

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
            _modules_loaded = False
            _modules_cache = None

            def __init__(inner_self, *args, **kwargs):
                # Pass through to parent class
                super(OptionalDependencyChecker, inner_self).__init__(*args, **kwargs)

            @property
            def modules(inner_self):
                """Lazy-load modules on first access."""
                if not OptionalDependencyChecker._modules_loaded:
                    OptionalDependencyChecker._modules_cache = {}
                    missing_modules = []

                    for spec in module_specs:
                        module, installed_version, _ = spec.load()
                        OptionalDependencyChecker._modules_cache[spec.alias] = module

                        # Register version on first successful load
                        if installed_version is not None:
                            odm.version_register[spec.module_name] = installed_version

                        if module is None:
                            missing_modules.append(spec.alias)

                    if len(missing_modules) > 0:
                        raise ImportError(f"Missing dependencies: {missing_modules}\n")

                    OptionalDependencyChecker._modules_loaded = True

                return OptionalDependencyChecker._modules_cache

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
                missing_modules = []

                for spec in module_specs:
                    module, installed_version, _ = spec.load()
                    modules_cache[spec.alias] = module

                    if installed_version is not None:
                        odm.version_register[spec.module_name] = installed_version

                    if module is None:
                        missing_modules.append(spec.alias)

                if len(missing_modules) > 0:
                    raise ImportError(f"Missing dependencies: {missing_modules}\n")

                loaded = True

            # Inject modules dict as keyword argument
            kwargs["modules"] = modules_cache
            return func(*args, **kwargs)

        # Also expose modules on wrapper for external access if needed
        setattr(wrapper, "modules", modules_cache)
        return wrapper

    def _validate_input(self, module_dict: dict[str, Any]) -> None:
        # Default from_meta to False if not provided
        if "from_meta" not in module_dict:
            module_dict["from_meta"] = False

        if "specifiers" not in module_dict:
            if module_dict["from_meta"]:
                if self.source is not None and self.metasource is not None:
                    if "extra" in module_dict:
                        module_dict["specifiers"] = self.metasource.get_specifier(
                            module_dict["module_name"], module_dict["extra"]
                        )
                    else:
                        raise KeyError(
                            "When 'from_meta' is True, the field 'extra' must be set"
                        )
                else:
                    raise ValueError(
                        "When 'from_meta' is True, a 'source' must be provided to the OptionalDependencyManager"
                    )


# Backwards compatibility alias for the typo
OptinalDependencyManager = OptionalDependencyManager
