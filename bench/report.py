COLUMNS = (
    ("leakage", "Poisoned claims still served"),
    ("preserved", "Valid claims preserved"),
    ("precision", "Withdrawal precision"),
    ("missed", "Bad decisions missed"),
    ("labelled", "Decisions labelled correctly"),
)


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.1f}%"


def render_table(title: str, aggregated: dict[str, dict]) -> str:
    lines = [
        f"### {title}",
        "",
        "| System | " + " | ".join(label for _, label in COLUMNS) + " |",
        "|---" * (len(COLUMNS) + 1) + "|",
    ]
    for name, row in aggregated.items():
        lines.append(f"| {name} | " + " | ".join(pct(row[key]) for key, _ in COLUMNS) + " |")
    return "\n".join(lines)


def render_latency(rows: list[dict]) -> str:
    quarantine = sum(row["quarantine_ms"] for row in rows) / len(rows)
    recall = sum(row["recall_ms"] for row in rows) / len(rows)
    return "\n".join(
        [
            "### Operational cost (WYSE only, baselines are in-memory)",
            "",
            "| Operation | Mean latency |",
            "|---|---|",
            f"| Quarantine one source, including recompute and impact analysis | {quarantine:.0f} ms |",
            f"| Gateway recall over the whole tenant | {recall:.0f} ms |",
        ]
    )


def render_independence(rows: list[dict]) -> str:
    lines = [
        "### Corroboration: independent sources reported",
        "",
        "| Agents confirming | Shared origin | Truth | Vote counting | WYSE |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['agents']} | {'yes' if row['correlated'] else 'no'} | {row['truth']} "
            f"| {row['votes']} | {row['wyse']} |"
        )
    return "\n".join(lines)
