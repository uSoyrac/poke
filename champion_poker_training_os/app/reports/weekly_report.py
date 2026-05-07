def build_weekly_report(metrics: dict, leaks: list[dict]) -> str:
    return f"Weekly report: skill {metrics.get('skill_score')}, active leaks {len(leaks)}."

