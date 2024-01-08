import sys
from dataclasses import dataclass, field
from importlib.metadata import PackageNotFoundError, metadata, version
from importlib.util import LazyLoader, find_spec, module_from_spec
from inspect import isclass, isfunction

from packaging.requirements import InvalidRequirement, Requirement
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


def _retrive_module_specifier_from_meta(
    parent_module: str, target_module: str
) -> SpecifierSet:
    """
    Retrive module specifier from parent module's metadata.

    ----------
    Parameters
    ----------
    parent_module : str
        Parent module name.
    target_module : str
        Target module name.

    -------
    Returns
    -------
    SpecifierSet
        Module specifier.
    """
    try:
        meta = metadata(parent_module)
    except PackageNotFoundError as e:
        raise ImportError(f"{parent_module} is not installed\n") from e
    else:
        requirements = []
        requirements_unfulfilled = []
        for meta_type, module_info in meta.items():
            if meta_type == "Requires-Dist":
                try:
                    requirement = Requirement(module_info)
                except InvalidRequirement as e:
                    raise ImportError(
                        f"{module_info} is not a valid requirement\n"
                    ) from e
                else:
                    if target_module == requirement.name:
                        if requirement.marker is None or requirement.marker.evaluate():
                            requirements.append(requirement)
                        if (
                            requirement.marker is not None
                            and not requirement.marker.evaluate()
                        ):
                            requirements_unfulfilled.append(requirement)
        if len(requirements) == 0:
            if len(requirements_unfulfilled) > 0:
                markers = [req.marker for req in requirements_unfulfilled]
                raise ImportError(
                    f"{target_module} is listed as a dependency of {parent_module} but none of the markers {markers} is fulfilled\n"
                )
            else:
                raise ImportError(
                    f"{target_module} is not listed as a dependency of {parent_module}\n"
                )
        else:
            unique_requirements = set(requirements)
            if len(unique_requirements) > 1:
                raise ImportError(
                    f"{target_module} is listed as a dependency of {parent_module} multiple times\n"
                )
            else:
                return unique_requirements.pop().specifier


@dataclass
class ModuleInfo:
    module_name: str
    specifiers: str | None = field(default=None, hash=True)
    alias: str | None = field(default=None, hash=False)
    source: str | None = field(default=None, hash=True)
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

        if self.specifiers is None:
            if self.source is None:
                self.specifiers = ">0.0.0,<9999.9999.9999"
            else:
                self.specifiers = _retrive_module_specifier_from_meta(
                    self.source, self.module_name
                )

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
        else:
            module = None
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

    def __call__(self, modules: dict[str, dict[str, str]]):
        def dependencies_decorator(target):
            if isclass(target) or isfunction(target):
                modules_flattend = _flatten_module_info(modules)
                for mod in modules_flattend:
                    mod["source"] = self.source
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
            return target

        return dependencies_decorator

    @property
    def OptionalDependencyChecker(self):
        class OptionalDependencyChecker:
            def __init__(self):
                if not hasattr(self, "modules"):
                    raise RuntimeError(
                        "The class inheriting from OptionalDependencyChecker must have a `modules` attribute, which is inserted by the decorator OptinalDependencyManager"
                    )
                if len(self.modules) == 0:
                    raise RuntimeError(
                        "The class inheriting from OptionalDependencyChecker must have at least one dependency"
                    )
                missing_modules = []
                for module_name, module in self.modules.items():
                    if module is None:
                        missing_modules.append(module_name)
                if len(missing_modules) > 0:
                    raise ImportError(f"Missing dependencies: {missing_modules}\n")

        return OptionalDependencyChecker
