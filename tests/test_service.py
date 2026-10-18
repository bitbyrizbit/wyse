import asyncio

import pytest

from wyse.mcp_server import create_server
from wyse.service import Service

TOOLS = {
    "remember", "recall", "explain_belief", "inspect_impact", "retract", "quarantine",
    "record_decision", "reassess", "as_of", "promote", "handoff", "open_handoff",
}
HIDDEN = {"tenant", "agent", "agent_id", "sender", "trust_tier", "tier"}


@pytest.fixture
def make_service(store, tenant):
    made = []

    def build(agent, role="agent"):
        service = Service(store, tenant, agent, role)
        made.append(service)
        return service

    yield build
    for service in made:
        for name in service.prepared:
            store.drop(name)


def test_tool_surface_hides_identity_and_trust(make_service):
    server = create_server(make_service("alice"))
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == TOOLS
    for tool in tools:
        assert not HIDDEN & set(tool.inputSchema.get("properties", {}))


def test_agents_cannot_claim_system_authority(make_service):
    alice = make_service("alice")
    with pytest.raises(ValueError):
        alice.remember("ledger", "paid", "inv-1", "status", "paid", source_kind="system")
    ops = make_service("ops", "operator")
    saved = ops.remember("ledger", "paid", "inv-1", "status", "paid", source_kind="system")
    assert saved["claim_id"]


def test_agents_cannot_edit_shared_memory_directly(make_service):
    alice = make_service("alice")
    with pytest.raises(PermissionError):
        alice.remember("ledger", "paid", "inv-1", "status", "paid", scope="shared")
    saved = alice.remember("ledger", "paid", "inv-1", "status", "paid")
    with pytest.raises(PermissionError):
        alice.quarantine(saved["source_id"], "no", scope="shared")
    alice.retract(saved["claim_id"], "my mistake", scope="private")
    withheld = alice.recall(scope="private")["withheld"]
    assert [item["claim_id"] for item in withheld] == [saved["claim_id"]]


def test_unknown_scope_is_rejected(make_service):
    with pytest.raises(ValueError):
        make_service("alice").recall(scope="everywhere")


def test_poisoned_page_story(make_service):
    alice = make_service("alice")
    bob = make_service("bob")
    ops = make_service("ops", "operator")

    page = alice.remember(
        "fake-invoices", "invoice 104 is paid", "inv-104", "status", "paid", source_kind="web"
    )
    alice.remember(
        "provider", "settlement confirmed", "inv-104", "status", "paid", source_kind="tool"
    )
    orphan = alice.remember(
        "fake-invoices", "invoice 9 is paid", "inv-9", "status", "paid", source_kind="web"
    )

    promoted = alice.promote([page["claim_id"], orphan["claim_id"]])
    both = sorted([page["claim_id"], orphan["claim_id"]])
    assert promoted["promoted"] == both
    assert sorted(i["claim_id"] for i in bob.recall()["usable"]) == both

    decision = bob.record_decision("closed invoice 104", [page["claim_id"]], acted=True)
    preview = ops.inspect_impact(source_id=page["source_id"], scope="shared")
    radius = preview["blast_radius"]
    assert set(preview["fell"]) | set(preview["survived"]) <= set(radius["claims"])
    assert set(preview["decisions"]) <= set(radius["decisions"])
    assert radius["truncated"] is False
    impact = ops.quarantine(page["source_id"], "page was forged", scope="shared")["impact"]
    assert impact["fell"] == [orphan["claim_id"]]
    assert impact["survived"] == [page["claim_id"]]
    assert impact["decisions"] == {decision: "REVIEW_REQUIRED"}

    shared = bob.recall()
    assert [i["claim_id"] for i in shared["usable"]] == [page["claim_id"]]
    assert shared["withheld"][0]["claim_id"] == orphan["claim_id"]
    assert "statement" not in shared["withheld"][0]
    assert bob.reassess(decision)["remediation"] == "REVIEW_REQUIRED"
    assert bob.as_of(decision)["claims"][0]["belief"] == "SUPPORTED"
