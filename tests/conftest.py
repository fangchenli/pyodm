import pytest

from pyodm.odm import OptinalDependencyManager


@pytest.fixture
def odm():
    return OptinalDependencyManager()
