import uuid

import pytest

from wyse.db import Store


@pytest.fixture(scope="session")
def store():
    return Store()


def _scratch_tenant(store):
    name = f"t_{uuid.uuid4().hex[:10]}"
    yield name
    store.drop(name)


@pytest.fixture
def tenant(store):
    yield from _scratch_tenant(store)


@pytest.fixture
def other_tenant(store):
    yield from _scratch_tenant(store)
