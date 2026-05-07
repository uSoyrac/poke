def import_manual_solution(rows: list[dict]) -> list[dict]:
    return [{**row, "source_confidence": "Pre-solved library"} for row in rows]

