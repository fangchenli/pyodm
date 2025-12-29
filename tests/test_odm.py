import re

import pytest

from optional_dependency_manager.odm import (
    ModuleReport,
    ModuleSpec,
    _parse_module_spec,
)

# Tests for ModuleSpec


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


# Tests for _parse_module_spec


class TestParseModuleSpec:
    """Tests for _parse_module_spec function."""

    def test_simple_module_name(self):
        """Test parsing a simple module name."""
        result = _parse_module_spec("numpy")
        assert result == {"module_name": "numpy"}

    def test_version_specifier_gte(self):
        """Test parsing with >= version specifier."""
        result = _parse_module_spec("numpy>=1.20")
        assert result == {"module_name": "numpy", "specifiers": ">=1.20"}

    def test_version_specifier_complex(self):
        """Test parsing with complex version specifier."""
        result = _parse_module_spec("numpy>=1.20,<2.0")
        assert result == {"module_name": "numpy", "specifiers": ">=1.20,<2.0"}

    def test_extra_or_group(self):
        """Test parsing with @extra_or_group syntax."""
        result = _parse_module_spec("numpy@ml")
        assert result == {
            "module_name": "numpy",
            "extra_or_group": "ml",
            "from_meta": True,
        }

    def test_alias(self):
        """Test parsing with alias."""
        result = _parse_module_spec("numpy as np")
        assert result == {"module_name": "numpy", "alias": "np"}

    def test_extra_with_alias(self):
        """Test parsing with @extra and alias."""
        result = _parse_module_spec("numpy@ml as np")
        assert result == {
            "module_name": "numpy",
            "extra_or_group": "ml",
            "from_meta": True,
            "alias": "np",
        }

    def test_distribution_name(self):
        """Test parsing with distribution name mapping."""
        result = _parse_module_spec("sklearn->scikit-learn")
        assert result == {
            "module_name": "sklearn",
            "distribution_name": "scikit-learn",
        }

    def test_extra_with_distribution_name(self):
        """Test parsing with @extra and distribution name."""
        result = _parse_module_spec("sklearn@ml->scikit-learn")
        assert result == {
            "module_name": "sklearn",
            "extra_or_group": "ml",
            "from_meta": True,
            "distribution_name": "scikit-learn",
        }

    def test_full_syntax(self):
        """Test parsing with all options."""
        result = _parse_module_spec("sklearn@ml->scikit-learn as sk")
        assert result == {
            "module_name": "sklearn",
            "extra_or_group": "ml",
            "from_meta": True,
            "distribution_name": "scikit-learn",
            "alias": "sk",
        }

    def test_version_with_alias(self):
        """Test parsing version specifier with alias."""
        result = _parse_module_spec("numpy>=1.20 as np")
        assert result == {
            "module_name": "numpy",
            "specifiers": ">=1.20",
            "alias": "np",
        }

    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        result = _parse_module_spec("  numpy@ml  as  np  ")
        assert result == {
            "module_name": "numpy",
            "extra_or_group": "ml",
            "from_meta": True,
            "alias": "np",
        }


# Tests for decorator API


class TestDecoratorClass:
    """Tests for decorator with classes."""

    def test_simple_module(self, odm):
        """Test with simple module name."""

        @odm("packaging")
        class TestClass:
            pass

        instance = TestClass()
        assert "packaging" in instance.modules
        assert instance.modules["packaging"] is not None

    def test_version_specifier(self, odm):
        """Test with version specifier."""

        @odm("packaging>=20.0,<=30.0")
        class TestClass:
            pass

        instance = TestClass()
        assert "packaging" in instance.modules

    def test_multiple_modules(self, odm):
        """Test with multiple modules."""

        @odm("packaging>=20.0", "pytest")
        class TestClass:
            pass

        instance = TestClass()
        assert "packaging" in instance.modules
        assert "pytest" in instance.modules

    def test_alias(self, odm):
        """Test with alias."""

        @odm("packaging as pkg")
        class TestClass:
            pass

        instance = TestClass()
        assert "pkg" in instance.modules
        assert "packaging" not in instance.modules

    def test_missing_dependency(self, odm):
        """Test error on missing dependency."""

        @odm("nonexistent_package>=1.0")
        class TestClass:
            pass

        instance = TestClass()
        with pytest.raises(
            ImportError, match=r"Missing or incompatible dependencies:\n.*nonexistent"
        ):
            _ = instance.modules


class TestDecoratorFunction:
    """Tests for decorator with functions."""

    def test_simple_module(self, odm):
        """Test with simple module name."""

        @odm("packaging>=20.0")
        def test_func(modules):
            assert "packaging" in modules
            return modules["packaging"]

        result = test_func()
        assert result is not None

    def test_missing_dependency(self, odm):
        """Test error on missing dependency."""

        @odm("nonexistent_package")
        def test_func(modules):
            pass

        with pytest.raises(
            ImportError, match=r"Missing or incompatible dependencies:\n.*nonexistent"
        ):
            test_func()


class TestExtraAndGroup:
    """Tests for @extra and @group syntax."""

    def test_resolves_to_group(self, odm_with_source):
        """Test @ syntax resolves to group when only in groups."""

        @odm_with_source("pandas@test")
        class TestClass:
            pass

        instance = TestClass()
        assert "pandas" in instance.modules
        assert instance.modules["pandas"] is not None

    def test_resolves_to_extra(self, odm_with_source):
        """Test @ syntax resolves to extra when only in extras."""

        @odm_with_source("dependency_groups@groups->dependency-groups")
        class TestClass:
            pass

        instance = TestClass()
        assert "dependency_groups" in instance.modules

    def test_invalid_extra_or_group(self, odm_with_source):
        """Test @ syntax with invalid name raises error."""
        with pytest.raises(
            ValueError,
            match=r"'nonexistent' is not a valid extra or dependency group",
        ):

            @odm_with_source("numpy@nonexistent")
            class TestClass:
                pass

    def test_at_syntax_requires_source(self, odm):
        """Test @ syntax requires source to be set."""
        with pytest.raises(
            ValueError,
            match=r"When using '@' syntax, a 'source' must be provided",
        ):

            @odm("numpy@ml")
            class TestClass:
                pass


class TestRegister:
    """Tests for usage and version registers."""

    def test_usage_register(self, odm_with_source):
        """Test usage_register tracks decorated targets."""

        @odm_with_source("pandas@test", "numpy@test")
        class TestClass1:
            pass

        @odm_with_source("numpy@test")
        class TestClass2:
            pass

        @odm_with_source("pandas@test")
        def test_func(modules):
            pass

        assert "pandas" in odm_with_source.usage_register
        assert "numpy" in odm_with_source.usage_register
        assert "TestClass1" in odm_with_source.usage_register["pandas"]
        assert "TestClass1" in odm_with_source.usage_register["numpy"]
        assert "TestClass2" in odm_with_source.usage_register["numpy"]
        assert "test_func" in odm_with_source.usage_register["pandas"]

    def test_version_register(self, odm_with_source):
        """Test version_register is populated after loading."""

        @odm_with_source("pandas@test", "numpy@test")
        class TestClass:
            pass

        # Before instantiation
        assert "numpy" not in odm_with_source.version_register
        assert "pandas" not in odm_with_source.version_register

        # After accessing modules (triggers loading)
        instance = TestClass()
        _ = instance.modules  # Access modules to trigger lazy loading

        assert "numpy" in odm_with_source.version_register
        assert "pandas" in odm_with_source.version_register


class TestReport:
    """Tests for report() method."""

    def test_report_satisfied(self, odm):
        """Test report() with satisfied dependencies."""

        @odm("packaging>=20.0")
        class TestClass1:
            pass

        @odm("packaging>=20.0")
        def test_func(modules):
            pass

        reports = odm.report()

        assert len(reports) == 2
        assert all(isinstance(r, ModuleReport) for r in reports)

        assert reports[0].module_name == "packaging"
        assert reports[0].specifier == ">=20.0"
        assert reports[0].status == "satisfied"
        assert reports[0].used_by == "TestClass1"

        assert reports[1].used_by == "test_func"
        assert reports[1].status == "satisfied"

    def test_report_missing(self, odm):
        """Test report() with missing dependencies."""

        @odm("nonexistent_package>=1.0")
        class TestClass:
            pass

        reports = odm.report()

        assert len(reports) == 1
        assert reports[0].module_name == "nonexistent_package"
        assert reports[0].installed_version is None
        assert reports[0].status == "missing"
        assert reports[0].used_by == "TestClass"

    def test_report_version_mismatch(self, odm):
        """Test report() with version mismatch."""

        @odm("packaging>=9999.0")
        class TestClass:
            pass

        reports = odm.report()

        assert len(reports) == 1
        assert reports[0].module_name == "packaging"
        assert reports[0].installed_version is not None
        assert reports[0].status == "version_mismatch"

    def test_report_with_group(self, odm_with_source):
        """Test report() includes group field."""

        @odm_with_source("pandas@test")
        class TestClass:
            pass

        reports = odm_with_source.report()

        assert len(reports) == 1
        assert reports[0].module_name == "pandas"
        assert reports[0].group == "test"
        assert reports[0].extra is None
        assert reports[0].status == "satisfied"

    def test_report_with_extra(self, odm_with_source):
        """Test report() includes extra field."""

        @odm_with_source("dependency_groups@groups->dependency-groups")
        class TestClass:
            pass

        reports = odm_with_source.report()

        assert len(reports) == 1
        assert reports[0].module_name == "dependency_groups"
        assert reports[0].extra == "groups"
        assert reports[0].status == "satisfied"


class TestResolveExtraOrGroup:
    """Tests for MetaSource.resolve_extra_or_group method."""

    def test_resolves_to_group(self, odm_with_source):
        """Test resolution when name exists only in groups."""
        specifier, resolved_type = odm_with_source.metasource.resolve_extra_or_group(
            "pandas", "test"
        )
        assert resolved_type == "group"
        assert specifier == ">=2.1.4"

    def test_resolves_to_extra(self, odm_with_source):
        """Test resolution when name exists only in extras."""
        specifier, resolved_type = odm_with_source.metasource.resolve_extra_or_group(
            "dependency-groups", "groups"
        )
        assert resolved_type == "extra"
        assert ">=1.0" in specifier

    def test_not_found_error(self, odm_with_source):
        """Test error when name not found in either."""
        with pytest.raises(
            ValueError,
            match=r"'nonexistent' is not a valid extra or dependency group",
        ):
            odm_with_source.metasource.resolve_extra_or_group("numpy", "nonexistent")


class TestErrorMessages:
    """Tests for helpful error messages."""

    def test_no_args_error(self, odm):
        """Test error when no arguments provided."""
        with pytest.raises(
            ValueError,
            match=r"At least one module specification is required",
        ):

            @odm()
            class TestClass:
                pass
