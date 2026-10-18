import os
import argparse

from wyse.db import Store
from wyse.governance.audit import list_incidents, observation_nodes
from wyse.service import Service

TENANT = "demo"


def banner(text: str, auto: bool) -> None:
    if not auto:
        os.system("cls" if os.name == "nt" else "clear")
    print("\n" + "=" * 74)
    print(text)
    print("=" * 74)
    if not auto:
        input("press enter ")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true")
    auto = parser.parse_args().auto

    store = Store()
    for name in store.list_tenants():
        if name.startswith(TENANT):
            store.drop(name)

    alice = Service(store, TENANT, "alice")
    bob = Service(store, TENANT, "bob")
    ops = Service(store, TENANT, "ops", "operator")
    names: dict[str, str] = {}

    def label(claim_id: str) -> str:
        return names.get(claim_id, claim_id)

    banner("1. alice, a research agent, reads two sources about invoice 104", auto)
    page = alice.remember(
        "fake-invoices.example", "invoice 104 is paid", "invoice 104", "status", "paid", source_kind="web",
    )
    alice.remember(
        "payment-provider", "settlement confirmed for invoice 104", "invoice 104", "status", "paid",
        source_kind="tool",
    )
    orphan = alice.remember(
        "fake-invoices.example", "invoice 9 is paid", "invoice 9", "status", "paid", source_kind="web",
    )
    names[page["claim_id"]] = "invoice 104 is paid"
    names[orphan["claim_id"]] = "invoice 9 is paid"
    print("  invoice 104 is paid  <- a web page AND the payment provider")
    print("  invoice 9 is paid    <- the web page alone")

    banner("2. alice publishes both claims to shared memory through the promotion gate", auto)
    promoted = alice.promote([page["claim_id"], orphan["claim_id"]])
    print("  promoted:", [label(c) for c in promoted["promoted"]])
    print("  held back:", promoted["held"])

    banner("3. bob, a billing agent, closes both invoices on that evidence", auto)
    decisions = {
        bob.record_decision("closed invoice 104", [page["claim_id"]], acted=True): "closed invoice 104",
        bob.record_decision("closed invoice 9", [orphan["claim_id"]], acted=True): "closed invoice 9",
    }
    for title in decisions.values():
        print("  recorded decision:", title)

    banner("4. the web page turns out to be forged. preview the damage before acting", auto)
    preview = ops.inspect_impact(source_id=page["source_id"], scope="shared")
    print("  would fall:    ", [label(c) for c in preview["fell"]])
    print("  would survive: ", [label(c) for c in preview["survived"]])
    for did, tag in preview["decisions"].items():
        print(f"  decision '{decisions[did]}' -> {tag}")
    print(f"  blast radius by graph traversal: {len(preview['blast_radius']['claims'])} claims, "
          f"{len(preview['blast_radius']['decisions'])} decisions")

    banner("5. quarantine the source", auto)
    result = ops.quarantine(page["source_id"], "page was forged", scope="shared")
    print("  incident:", result["incident_id"])
    print("  fell:    ", [label(c) for c in result["impact"]["fell"]])
    print("  survived:", [label(c) for c in result["impact"]["survived"]])

    banner("6. what can bob read now?", auto)
    shared = bob.recall()
    for item in shared["usable"]:
        s = item["statement"]
        print(f"  usable   {s['subject']} is {s['object']}  (independent sources: {item['independent_sources']})")
    for item in shared["withheld"]:
        print(f"  withheld {label(item['claim_id'])}  reason: {item['reason']}  (text hidden)")

    banner("7. why does the surviving claim still stand? the proof, with poisoned text hidden", auto)
    report = bob.explain_belief(page["claim_id"])
    for node in observation_nodes(report["tree"]):
        state = "valid" if node["valid"] else "INVALID"
        text = node.get("content", "(hidden)")
        print(f"  {node.get('source_name')}: {state}: {text}")

    banner("8. what did each decision believe at the time, and what do we say now?", auto)
    for did, title in decisions.items():
        frozen = bob.as_of(did)["claims"][0]
        now = bob.reassess(did)["remediation"]
        print(f"  '{title}'")
        print(f"     then: belief {frozen['belief']}, {len(frozen['evidence'])} observation(s) of evidence")
        print(f"     now:  {now}")

    banner("9. the audit trail", auto)
    for entry in list_incidents(store, TENANT):
        print(f"  {entry['kind']}: {entry['reason']}  (fell {len(entry['result']['fell'])}, "
              f"survived {len(entry['result']['survived'])})")

    for name in store.list_tenants():
        if name.startswith(TENANT):
            store.drop(name)


if __name__ == "__main__":
    main()
