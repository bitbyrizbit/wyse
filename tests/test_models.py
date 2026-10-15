from wyse.models import Claim, Source, TrustTier


def test_claim_props_flatten_enums():
    claim = Claim(id="c1", tenant="t", subject="inv-1", predicate="status", object="paid", created_at=1)
    props = claim.props()
    assert props["belief_status"] == "UNSUPPORTED"
    assert props["use_status"] == "ELIGIBLE"
    assert props["revision"] == 1


def test_source_starts_clear():
    source = Source(id="s1", tenant="t", kind="web", name="example", trust_tier=TrustTier.WEB)
    assert source.props()["incident_state"] == "CLEAR"
