from wyse.belief.support import load_state


def test_load_state_pages_past_the_result_cap(store, ready):
    store.write(
        ready,
        "CREATE (s:Source {id: 'src_bulk', tenant: $t, kind: 'tool', name: 'bulk', "
        "trust_tier: 'TOOL', incident_state: 'CLEAR'}) "
        "WITH s UNWIND range(0, 10499) AS i "
        "CREATE (o:Observation {id: 'obs_' + toString(i), tenant: $t, content: 'x', "
        "content_hash: 'h', observed_at: 0, recorded_at: 0}) "
        "CREATE (s)-[:CAPTURED_AS]->(o)",
        {"t": ready},
    )
    assert len(load_state(store, ready).observations) == 10500
