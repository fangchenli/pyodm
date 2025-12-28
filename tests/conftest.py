import pytest

from pyodm.odm import OptionalDependencyManager


@pytest.fixture
def odm():
    return OptionalDependencyManager()


@pytest.fixture
def odm_with_source():
    return OptionalDependencyManager(source="pyodm")
