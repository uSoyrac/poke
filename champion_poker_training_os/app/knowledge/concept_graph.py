def related_concepts(concept: str) -> list[str]:
    links = {
        "MDF": ["Alpha", "River bluff-catch", "Blockers"],
        "ICM": ["Risk premium", "Bubble factor", "cEV vs $EV"],
    }
    return links.get(concept, ["EV", "Range advantage", "Exploit adjustment"])

