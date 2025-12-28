import pytest

from optional_dependency_manager.odm import OptionalDependencyManager


@pytest.fixture
def odm():
    return OptionalDependencyManager()


@pytest.fixture
def odm_with_source():
    return OptionalDependencyManager(source="optional-dependency-manager")
