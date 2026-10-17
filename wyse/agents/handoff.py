import json

from wyse.belief.policy import MAX_FIELD, check_text
from wyse.belief.support import analyze, load_state
from wyse.db import Store
from wyse.governance.gateway import assemble
from wyse.ids import new_id, now_ms

HANDOFF = """
MERGE (a:Agent {id: $sender})
  ON CREATE SET a.tenant = $tenant, a.role = 'agent', a.scope = 'shared'
MERGE (b:Agent {id: $receiver})
  ON CREATE SET b.tenant = $tenant, b.role = 'agent', b.scope = 'shared'
CREATE (h:Handoff {id: $hid, tenant: $tenant, sender: $sender, receiver: $receiver,
                   at: $now, note: $note, package: $package})
CREATE (a)-[:HANDED_OFF {handoff: $hid}]->(b)
RETURN h.id AS id
"""


def handoff(
    store: Store, tenant: str, sender: str, receiver: str,
    claim_ids: list[str], note: str = "",
) -> str:
    frm = check_text("sender", sender, MAX_FIELD)
    to = check_text("receiver", receiver, MAX_FIELD)
    ids = sorted(set(claim_ids))
    state = load_state(store, tenant)
    unknown = [cid for cid in ids if cid not in state.claims]
    if unknown:
        raise ValueError(f"unknown claims: {unknown}")
    analysis = analyze(state)
    recalled = assemble(state, analysis, ids, now_ms())
    package = {"claims": recalled.usable + recalled.contested, "withheld": recalled.withheld}

    handoff_id = new_id("hnd")
    store.write(
        tenant, HANDOFF,
        {
            "sender": frm, "receiver": to, "hid": handoff_id, "tenant": tenant,
            "now": now_ms(), "note": note.strip()[:MAX_FIELD], "package": json.dumps(package, sort_keys=True),
        },
    )
    return handoff_id


def open_handoff(store: Store, tenant: str, handoff_id: str, receiver: str) -> dict:
    rows = store.read(
        tenant,
        "MATCH (h:Handoff {id: $id}) RETURN h.sender AS sender, h.receiver AS receiver, "
        "h.note AS note, h.package AS package, h.at AS at",
        {"id": handoff_id},
    )
    if not rows:
        raise ValueError(f"unknown handoff: {handoff_id}")
    row = rows[0]
    if row["receiver"] != receiver:
        raise PermissionError("handoff is addressed to another agent")

    package = json.loads(row["package"])
    analysis = analyze(load_state(store, tenant))
    drift = []
    for item in package["claims"]:
        cid = item["claim_id"]
        belief = analysis.belief.get(cid, "UNKNOWN")
        evidence = sorted(analysis.roots.get(cid, ()))
        if belief != item["belief_status"] or evidence != item["evidence"] or cid not in analysis.use_ok:
            drift.append(
                {
                    "claim_id": cid,
                    "then": {"belief": item["belief_status"], "evidence": item["evidence"]},
                    "now": {"belief": belief, "evidence": evidence, "usable": cid in analysis.usable},
                }
            )
    return {
        "handoff_id": handoff_id,
        "sender": row["sender"],
        "note": row["note"],
        "at": row["at"],
        "claims": package["claims"],
        "withheld": package["withheld"],
        "drift": drift,
    }
