import re

import pytest

from pyodm.odm import ModuleInfo, _flatten_module_info


@pytest.mark.parametrize(
    "module_info, expected",
    [
        (
            {
                "packaging": {
                    "specifiers": ">=20.9, <=21.0",
                    "alias": "pkg",
                },
                "black": {
                    "specifiers": ">=20.8b1, <=21.0",
                    "alias": "blk",
                },
            },
            [
                {
                    "module_name": "packaging",
                    "specifiers": ">=20.9, <=21.0",
                    "alias": "pkg",
                },
                {
                    "module_name": "black",
                    "specifiers": ">=20.8b1, <=21.0",
                    "alias": "blk",
                },
            ],
        )
    ],
)
def test_flatten_module_info(module_info, expected):
    assert _flatten_module_info(module_info) == expected


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "module_name": "packaging",
            "specifiers": ">=20.9, <=23.2",
            "alias": "pkg",
        },
    ],
)
def test_module_info_constructor(module_info_dict):
    module_info = ModuleInfo(**module_info_dict)
    assert module_info.module_name == "packaging"
    assert module_info.specifiers == ">=20.9, <=23.2"
    assert module_info.alias == "pkg"


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "module_name": "packaging",
        },
    ],
)
def test_module_info_default(module_info_dict):
    module_info = ModuleInfo(**module_info_dict)
    assert module_info.module_name == "packaging"
    assert module_info.specifiers == ">0.0.0,<9999.9999.9999"
    assert module_info.alias == "packaging"
    assert module_info.module is not None


@pytest.mark.parametrize(
    "module_info_dict, error_msg",
    [
        (
            {
                "module_name": "dummy",
            },
            "dummy is not installed\n",
        ),
        (
            {
                "module_name": "packaging",
                "specifiers": ">=9999.9999.9999",
            },
            r"packaging version .* does not meet requirement .*\n",
        ),
        (
            {
                "module_name": "packaging",
                "specifiers": "<=0.0.0",
            },
            r"packaging version .* does not meet requirement .*\n",
        ),
    ],
)
def test_module_errors(module_info_dict, error_msg):
    module = ModuleInfo(**module_info_dict)
    assert re.match(error_msg, module.error_msg)


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "packaging": {
                "specifiers": ">=20.9, <=23.2",
            }
        },
    ],
)
def test_dependencies_decorator_non_class(module_info_dict, odm):
    @odm(modules=module_info_dict)
    def test_func():
        assert "packaging" in test_func.modules

    test_func()


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "packaging": {
                "specifiers": ">=20.9, <=23.2",
            }
        },
    ],
)
def test_dependencies_decorator_class(module_info_dict, odm):
    @odm(modules=module_info_dict)
    class TestClass(odm.OptionalDependencyChecker):
        ...

    assert hasattr(TestClass, "modules")
    assert "packaging" in TestClass.modules


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "dummy": {
                "specifiers": ">=20.9, <=23.2",
            }
        },
    ],
)
def test_missing_dependency(module_info_dict, odm):
    @odm(modules=module_info_dict)
    class TestClass(odm.OptionalDependencyChecker):
        def __init__(self):
            super().__init__()

    with pytest.raises(ImportError, match=r"Missing dependencies: \['dummy'\]\n"):
        TestClass()


def test_missing_decorator(odm):
    class TestClass(odm.OptionalDependencyChecker):
        def __init__(self):
            super().__init__()

    error_msg = "The class inheriting from OptionalDependencyChecker must have a `modules` attribute, which is inserted by the decorator OptinalDependencyManager"
    with pytest.raises(RuntimeError, match=error_msg):
        TestClass()
