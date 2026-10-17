import uuid

import pytest

from wyse.db import Store
from wyse.schema import ensure_schema, wait_for_constraints


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


@pytest.fixture
def ready(store, tenant):
    store.write(tenant, "CREATE (:Seed)")
    ensure_schema(store, tenant)
    wait_for_constraints(store, tenant)
    return tenant
