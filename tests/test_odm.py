import re

import pytest

from pyodm.odm import ModuleSpec, _flatten_module_info


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
            "specifiers": ">=20.9, <=30.0",
            "alias": "pkg",
        },
    ],
)
def test_module_spec_constructor(module_info_dict):
    spec = ModuleSpec(**module_info_dict)
    assert spec.module_name == "packaging"
    assert spec.specifiers == ">=20.9, <=30.0"
    assert spec.alias == "pkg"
    assert spec.from_meta is False


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "module_name": "packaging",
        },
    ],
)
def test_module_spec_default(module_info_dict):
    spec = ModuleSpec(**module_info_dict)
    assert spec.module_name == "packaging"
    assert spec.specifiers == ">0.0.0,<9999.9999.9999"
    assert spec.alias == "packaging"
    assert spec.from_meta is False
    # load() should return the module
    module, version, error = spec.load()
    assert module is not None
    assert version is not None
    assert error is None


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "module_name": ".packaging",
        },
    ],
)
def test_module_spec_relative_import(module_info_dict):
    spec = ModuleSpec(**module_info_dict)
    # Relative import error is raised at load() time, not construction
    with pytest.raises(
        ValueError,
        match=r"Relative imports are not supported",
    ):
        spec.load()


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
def test_module_spec_errors(module_info_dict, error_msg):
    spec = ModuleSpec(**module_info_dict)
    # Errors are returned from load(), not raised at construction
    module, _, error = spec.load()
    assert module is None
    assert re.match(error_msg, error)


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "numpy": {
                "specifiers": ">=1.26.4",
            }
        },
    ],
)
def test_dependencies_decorator_function(module_info_dict, odm):
    @odm(modules=module_info_dict)
    def test_func(modules):
        # modules is injected as a keyword argument
        assert "numpy" in modules
        assert modules["numpy"] is not None

    # Modules are loaded on first call and injected as kwarg
    test_func()


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
def test_dependencies_decorator_function_invalid(module_info_dict, odm):
    @odm(modules=module_info_dict)
    def test_func(modules):
        pass

    # Missing dependency raises ImportError on first call
    with pytest.raises(ImportError, match=r"Missing dependencies: \['dummy'\]\n"):
        test_func()


@pytest.mark.parametrize(
    "module_info_dict",
    [
        {
            "packaging": {
                "specifiers": ">=20.9, <=30.0",
            }
        },
    ],
)
def test_dependencies_decorator_class(module_info_dict, odm):
    @odm(modules=module_info_dict)
    class TestClass:
        def __init__(self):
            super().__init__()

    # modules is an instance attribute, set at instantiation
    instance = TestClass()
    assert hasattr(instance, "modules")
    assert "packaging" in instance.modules


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
    class TestClass:
        def __init__(self):
            super().__init__()

    # Instantiation succeeds - error only on accessing modules
    instance = TestClass()
    with pytest.raises(ImportError, match=r"Missing dependencies: \['dummy'\]\n"):
        _ = instance.modules


def test_specifiers_from_meta(odm_with_source):
    @odm_with_source(modules={"pandas": {"from_meta": True, "extra": "dev"}})
    class TestClass:
        def __init__(self):
            super().__init__()

    # modules is an instance attribute, set at instantiation
    instance = TestClass()
    assert hasattr(instance, "modules")
    assert "pandas" in instance.modules


def test_distribution_name():
    """Test that distribution_name allows import name to differ from package name."""
    # numpy's import name matches its distribution name, so this should work
    spec = ModuleSpec(
        module_name="numpy",
        from_meta=False,
        specifiers=">=1.0.0",
        distribution_name="numpy",
    )
    module, version, error = spec.load()
    assert module is not None
    assert version is not None
    assert error is None


def test_register(odm_with_source):
    @odm_with_source(
        modules={
            "numpy": {"from_meta": True, "extra": "dev"},
            "pandas": {"from_meta": True, "extra": "dev"},
        }
    )
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
    def test_func1(modules): ...

    @odm_with_source(modules={"pandas": {"from_meta": True, "extra": "dev"}})
    def test_func2(modules): ...

    # Usage is registered at decoration time
    assert "numpy" in odm_with_source.usage_register
    assert "pandas" in odm_with_source.usage_register
    assert "TestClass1" in odm_with_source.usage_register["numpy"]
    assert "TestClass1" in odm_with_source.usage_register["pandas"]
    assert "TestClass2" in odm_with_source.usage_register["numpy"]
    assert "TestClass3" in odm_with_source.usage_register["pandas"]
    assert "test_func1" in odm_with_source.usage_register["numpy"]
    assert "test_func2" in odm_with_source.usage_register["pandas"]

    # Version register is empty until modules are actually loaded
    assert "numpy" not in odm_with_source.version_register
    assert "pandas" not in odm_with_source.version_register

    # Instantiate to trigger loading
    TestClass1()
    TestClass2()
    TestClass3()
    test_func1()
    test_func2()

    # Now versions should be registered
    assert "numpy" in odm_with_source.version_register
    assert "pandas" in odm_with_source.version_register
    assert odm_with_source.version_register["numpy"] is not None
    assert odm_with_source.version_register["pandas"] is not None
