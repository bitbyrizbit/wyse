import os

from mcp.server.fastmcp import FastMCP

from wyse.db import Store
from wyse.service import Service

INSTRUCTIONS = (
    "WYSE is evidence-aware memory. Write observations privately with remember, publish "
    "through promote, and read with recall. Claims you cannot use are listed as withheld "
    "with a reason and no text. Cite only usable claims when you record a decision."
)


def create_server(service: Service) -> FastMCP:
    mcp = FastMCP("wyse", instructions=INSTRUCTIONS)

    @mcp.tool()
    def remember(
        source_name: str, content: str, subject: str, predicate: str, object: str,
        source_kind: str = "agent", scope: str = "private",
    ) -> dict:
        """Store an observation and the claim it supports. source_kind is agent, tool, or web."""
        return service.remember(
            source_name, content, subject, predicate, object, source_kind, scope
        )

    @mcp.tool()
    def recall(
        subject: str | None = None, predicate: str | None = None, scope: str = "shared",
    ) -> dict:
        """Read claims through the gateway. Returns usable, contested, and withheld claims."""
        return service.recall(subject, predicate, scope)

    @mcp.tool()
    def explain_belief(claim_id: str, scope: str = "shared") -> dict:
        """Show the proof tree behind a claim: justifications, premises, and root evidence."""
        return service.explain_belief(claim_id, scope)

    @mcp.tool()
    def inspect_impact(
        source_id: str | None = None, observation_id: str | None = None,
        claim_id: str | None = None, scope: str = "shared",
    ) -> dict:
        """Preview which claims fall or survive, and which decisions need review."""
        return service.inspect_impact(source_id, observation_id, claim_id, scope)

    @mcp.tool()
    def retract(claim_id: str, reason: str, scope: str = "private") -> dict:
        """Withdraw a claim and report the cascade. Shared memory needs the operator role."""
        return service.retract(claim_id, reason, scope)

    @mcp.tool()
    def quarantine(source_id: str, reason: str, scope: str = "private") -> dict:
        """Block a compromised source and report the cascade. Shared memory needs the operator role."""
        return service.quarantine(source_id, reason, scope)

    @mcp.tool()
    def record_decision(
        summary: str, claim_ids: list[str], acted: bool = False, scope: str = "shared",
    ) -> dict:
        """Record a decision against usable claims. Set acted when a real action was taken."""
        return {"decision_id": service.record_decision(summary, claim_ids, acted, scope)}

    @mcp.tool()
    def reassess(decision_id: str, scope: str = "shared") -> dict:
        """Compare a past decision with current evidence and return its remediation label."""
        return service.reassess(decision_id, scope)

    @mcp.tool()
    def as_of(decision_id: str, scope: str = "shared") -> dict:
        """Return exactly what was believed when a decision was made."""
        return service.as_of(decision_id, scope)

    @mcp.tool()
    def promote(claim_ids: list[str]) -> dict:
        """Publish private claims, with their proofs, into shared memory through the gate."""
        return service.promote(claim_ids)

    @mcp.tool()
    def handoff(receiver: str, claim_ids: list[str], note: str = "") -> dict:
        """Send claims with their provenance to another agent."""
        return {"handoff_id": service.handoff(receiver, claim_ids, note)}

    @mcp.tool()
    def open_handoff(handoff_id: str) -> dict:
        """Open a handoff addressed to you and see which claims have drifted since."""
        return service.open_handoff(handoff_id)

    return mcp


def main() -> None:
    tenant = os.getenv("WYSE_TENANT")
    agent = os.getenv("WYSE_AGENT")
    if not tenant or not agent:
        raise SystemExit("set WYSE_TENANT and WYSE_AGENT")
    service = Service(Store(), tenant, agent, os.getenv("WYSE_ROLE", "agent"))
    create_server(service).run()


if __name__ == "__main__":
    main()
