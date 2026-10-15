import pytest
from redis.exceptions import ResponseError

from wyse.schema import ensure_schema, wait_for_constraints


def prepare(store, tenant):
    store.write(tenant, "CREATE (:Seed)")
    ensure_schema(store, tenant)
    wait_for_constraints(store, tenant)


def test_unsafe_tenant_ids_are_rejected(store):
    for bad in ("", "Acme", "a-b", "a b", "a;b", "x" * 41):
        with pytest.raises(ValueError):
            store.graph_name(bad)


def test_tenants_cannot_see_each_other(store, tenant, other_tenant):
    store.write(tenant, "CREATE (:Claim {id: 'c1', tenant: $t})", {"t": tenant})
    store.write(other_tenant, "CREATE (:Seed)")
    mine = store.read(tenant, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"]
    theirs = store.read(other_tenant, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"]
    assert (mine, theirs) == (1, 0)


def test_schema_setup_is_repeatable(store, tenant):
    prepare(store, tenant)
    ensure_schema(store, tenant)
    wait_for_constraints(store, tenant)


def test_duplicate_id_is_rejected(store, tenant):
    prepare(store, tenant)
    store.write(tenant, "CREATE (:Claim {id: 'c1', tenant: $t})", {"t": tenant})
    with pytest.raises(ResponseError):
        store.write(tenant, "CREATE (:Claim {id: 'c1', tenant: $t})", {"t": tenant})


def test_missing_tenant_property_is_rejected(store, tenant):
    prepare(store, tenant)
    with pytest.raises(ResponseError):
        store.write(tenant, "CREATE (:Claim {id: 'c9'})")


def test_failed_query_leaves_nothing_behind(store, tenant):
    prepare(store, tenant)
    with pytest.raises(ResponseError):
        store.write(
            tenant,
            "CREATE (:Claim {id: 'x', tenant: $t}), (:Claim {id: 'x', tenant: $t})",
            {"t": tenant},
        )
    count = store.read(tenant, "MATCH (c:Claim) RETURN count(c) AS n")[0]["n"]
    assert count == 0
