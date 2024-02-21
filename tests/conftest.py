import pytest

from pyodm.odm import OptinalDependencyManager


@pytest.fixture
def odm():
    return OptinalDependencyManager()


@pytest.fixture
def odm_with_source():
    return OptinalDependencyManager(source="pyodm")
