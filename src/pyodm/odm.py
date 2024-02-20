from __future__ import annotations

import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, metadata, version
from importlib.util import LazyLoader, find_spec, module_from_spec
from inspect import isclass, isfunction
import re

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
class ModuleInfo:
    module_name: str
    from_meta: bool
    specifiers: str | None = field(default=None, hash=True)
    alias: str | None = field(default=None, hash=False)
    module: object | None = field(default=None, init=False, repr=False, hash=False)
    installed_version: str | None = field(
        default=None, init=False, repr=False, hash=False
    )
    error_msg: str | None = field(default=None, init=False, repr=False, hash=False)

    def __post_init__(self):
        self._handle_missing_info()
        self._validate()
        self._import_module()

    def _handle_missing_info(self):
        if self.alias is None:
            self.alias = self.module_name

        if self.specifiers is None and not self.from_meta:
            self.specifiers = ">0.0.0,<9999.9999.9999"

    def _validate(self):
        module_name = (
            self.module_name.split(".")[0]
            if "." in self.module_name
            else self.module_name
        )
        try:
            self.installed_version = version(module_name)
        except PackageNotFoundError:
            self.error_msg = f"{module_name} is not installed\n"
        else:
            try:
                specifiers = SpecifierSet(self.specifiers)
            except InvalidSpecifier:
                self.error_msg = f"{self.specifiers} is not a valid specifier"
            else:
                if self.installed_version not in specifiers:
                    self.error_msg = f"{module_name} version {self.installed_version} does not meet requirement {specifiers}\n"

    def _import_module(self):
        if self.error_msg is None:
            spec = find_spec(self.module_name)
            loader = LazyLoader(spec.loader)
            spec.loader = loader
            module = module_from_spec(spec)
            sys.modules[self.module_name] = module
            spec.loader.exec_module(module)
            self.module = module


@dataclass
class OptinalDependencyManager:
    source: str | None = field(default=None, hash=True)
    version_register: dict[str, str] = field(
        default_factory=dict, init=False, hash=True
    )
    usage_register: dict[str, list[str]] = field(
        default_factory=dict, init=False, hash=True
    )
    requirements: list[Requirement] = field(init=False, hash=True, repr=False)
    extra: str | None = field(init=False, default=None, hash=True)

    def __post_init__(self):
        if self.source is not None:
            try:
                if "[" in self.source:
                    self.source, extra = self._parse_extra_from_module_name(self.source)
                    meta = metadata(self.source)
            except PackageNotFoundError as e:
                raise ImportError(f"{self.source} is not installed\n") from e
            else:
                self.extra = extra
                requires = meta.get_all("Requires-Dist")
                self.requirements = [Requirement(req) for req in requires]
                if self.extra is not None:
                    extras = meta.get_all("Provides-Extra")
                    if self.extra in extras:
                        self.requirements = [
                            req
                            for req in self.requirements
                            if req.marker is None
                            or req.marker.evaluate({"extra": self.extra})
                        ]
                    else:
                        raise ImportError(
                            f"{self.source} does not provide extra {self.extra}\n"
                        )

    def __call__(self, modules: dict[str, dict[str, str]]):
        def dependencies_decorator(target):
            if isclass(target) or isfunction(target):
                modules_flattend = _flatten_module_info(modules)
                if self.source is not None:
                    for mod in modules_flattend:
                        if "from_meta" not in mod:
                            raise ValueError("from_meta key is required")
                        if "specifiers" not in mod and mod["from_meta"]:
                            mod["specifiers"] = self._retrive_specifier_from_meta(
                                mod["module_name"]
                            )
                modules_obj = [ModuleInfo(**mod) for mod in modules_flattend]
                target.modules = {mod.alias: mod.module for mod in modules_obj}

                # register imported modules and the class/function that used them
                for mod in modules_obj:
                    self.version_register[mod.module_name] = mod.installed_version
                    if mod.module_name not in self.usage_register:
                        self.usage_register[mod.module_name] = []
                    self.usage_register[mod.module_name].append(target.__name__)
            else:
                raise TypeError(
                    f"dependencies decorator can only be applied to classes or functions, not {type(target)}"
                )
            if isclass(target):
                target_with_checker = type(
                    target.__name__,
                    (self.OptionalDependencyChecker, target),
                    {},
                )
                return target_with_checker
            else:
                return target

        return dependencies_decorator

    @property
    def OptionalDependencyChecker(self):
        class OptionalDependencyChecker:
            def __init__(self):
                missing_modules = []
                for module_name, module in self.modules.items():
                    if module is None:
                        missing_modules.append(module_name)
                if len(missing_modules) > 0:
                    raise ImportError(f"Missing dependencies: {missing_modules}\n")

        return OptionalDependencyChecker

    def _parse_extra_from_module_name(self, module_name: str) -> tuple[str, str | None]:
        regex = re.compile(r"(\w+)(?:\[([\w,\s]+)\])?")
        match = regex.match(module_name)
        if match:
            module = match.group(1)
            extras = match.group(2)
            if extras is not None:
                extras = extras.replace(" ", "").split(",")
                if len(extras) > 1:
                    raise ValueError(f"Only one extra is allowed, not {extras}\n")
            return module, extras[0]  # type: ignore
        else:
            raise ValueError(f"{module_name} is not a valid module name\n")

    def _retrive_specifier_from_meta(self, target: str) -> str:
        fulfilled = []
        unfulfilled = []
        env = {"extra": self.extra} if self.extra is not None else None
        for requirement in self.requirements:
            if target == requirement.name:
                if requirement.marker is None or requirement.marker.evaluate(
                    environment=env
                ):
                    fulfilled.append(requirement)
                if requirement.marker is not None and not requirement.marker.evaluate(
                    environment=env
                ):
                    unfulfilled.append(requirement)

        if len(fulfilled) == 0:
            if len(unfulfilled) > 0:
                markers = [req.marker for req in unfulfilled]
                raise ImportError(
                    f"{target} is listed as a dependency of {self.source} but none of the markers {markers} is fulfilled\n"
                )
            else:
                raise ImportError(
                    f"{target} is not listed as a dependency of {self.source}\n"
                )
        else:
            unique = set(fulfilled)
            if len(unique) > 1:
                raise ImportError(
                    f"{target} is listed as a dependency of {self.source} multiple times\n"
                )
            else:
                return str(unique.pop().specifier)
