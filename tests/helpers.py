from wyse.belief.ingest import remember


def fact(store, tenant, kind, name, content, subject, predicate, obj):
    return remember(
        store, tenant, source_kind=kind, source_name=name, content=content,
        subject=subject, predicate=predicate, object=obj,
    )


def belief(store, tenant, claim_id):
    rows = store.read(tenant, "MATCH (c:Claim {id: $id}) RETURN c.belief_status AS s", {"id": claim_id})
    return rows[0]["s"]
