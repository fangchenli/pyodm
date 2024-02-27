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
            "from_meta": False,
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
            "from_meta": False,
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
                "from_meta": False,
            },
            "dummy is not installed\n",
        ),
        (
            {
                "module_name": "packaging",
                "specifiers": ">=9999.9999.9999",
                "from_meta": False,
            },
            r"packaging version .* does not meet requirement .*\n",
        ),
        (
            {
                "module_name": "packaging",
                "specifiers": "<=0.0.0",
                "from_meta": False,
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
                "from_meta": False,
            }
        },
    ],
)
def test_dependencies_decorator_function(module_info_dict, odm):
    @odm(modules=module_info_dict)
    def test_func():
        assert "packaging" in test_func.modules
        assert test_func.modules["packaging"] is not None

    test_func()


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "dummy": {
                "specifiers": ">=20.9, <=23.2",
                "from_meta": False,
            }
        },
    ],
)
def test_dependencies_decorator_function_invalid(module_info_dict, odm):
    @odm(modules=module_info_dict)
    def test_func():
        assert "modules" in test_func.__dict__
        assert "dummy" in test_func.modules
        assert test_func.modules["dummy"] is None

    test_func()


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "packaging": {
                "specifiers": ">=20.9, <=23.2",
                "from_meta": False,
            }
        },
    ],
)
def test_dependencies_decorator_class(module_info_dict, odm):
    @odm(modules=module_info_dict)
    class TestClass():
        ...

    assert hasattr(TestClass, "modules")
    assert "packaging" in TestClass.modules


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "dummy": {
                "specifiers": ">=20.9, <=23.2",
                "from_meta": False,
            }
        },
    ],
)
def test_missing_dependency(module_info_dict, odm):
    @odm(modules=module_info_dict)
    class TestClass():
        def __init__(self):
            super().__init__()

    with pytest.raises(ImportError, match=r"Missing dependencies: \['dummy'\]\n"):
        TestClass()


def test_specifiers_from_meta(odm_with_source):
    @odm_with_source(modules={"pandas": {"from_meta": True, "extra": "dev"}})
    class TestClass():
        def __init__(self):
            super().__init__()
    
    assert hasattr(TestClass, "modules")
    assert "pandas" in TestClass.modules



def test_register(odm_with_source):

    @odm_with_source(modules={"numpy": {"from_meta": True, "extra": "dev"}, "pandas": {"from_meta": True, "extra": "dev"}})
    class TestClass1:
        def __init__(self):
            super().__init__()

    @odm_with_source(modules={"numpy": {"from_meta": True, "extra": "dev"}})
    class TestClass2:
        def __init__(self):
            super().__init__()

    @odm_with_source(modules={"pandas": {"from_meta": True, "extra": "dev"}})
    class TestClass3:
        def __init__(self):
            super().__init__()

    @odm_with_source(modules={"numpy": {"from_meta": True, "extra": "dev"}})
    def test_func1():
        ...

    @odm_with_source(modules={"pandas": {"from_meta": True, "extra": "dev"}})
    def test_func2():
        ...

    assert "numpy" in odm_with_source.usage_register
    assert "pandas" in odm_with_source.usage_register
    assert "TestClass1" in odm_with_source.usage_register["numpy"]
    assert "TestClass1" in odm_with_source.usage_register["pandas"]
    assert "TestClass2" in odm_with_source.usage_register["numpy"]
    assert "TestClass3" in odm_with_source.usage_register["pandas"]
    assert "test_func1" in odm_with_source.usage_register["numpy"]
    assert "test_func2" in odm_with_source.usage_register["pandas"]
    assert "numpy" in odm_with_source.version_register
    assert "pandas" in odm_with_source.version_register
    assert odm_with_source.version_register["numpy"] == "1.25.2"
    assert odm_with_source.version_register["pandas"] == "2.1.4"
