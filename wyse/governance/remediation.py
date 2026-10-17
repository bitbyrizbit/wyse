from wyse.models import Remediation


def classify(
    decision: dict, fallen: set[str], touched: set[str], dead_evidence: set[str]
) -> Remediation:
    used = set(decision["claims"])
    if used & fallen:
        if decision["acted"]:
            return Remediation.COMPENSATING_ACTION_REQUIRED
        return Remediation.CORRECTION_REQUIRED

    snapshot = decision.get("snapshot")
    if snapshot is None:
        return Remediation.UNRESOLVED if used & touched else Remediation.NO_ACTION_REQUIRED

    recorded = {root for entry in snapshot["claims"].values() for root in entry["evidence"]}
    if used & touched or recorded & dead_evidence:
        return Remediation.REVIEW_REQUIRED
    return Remediation.NO_ACTION_REQUIRED
