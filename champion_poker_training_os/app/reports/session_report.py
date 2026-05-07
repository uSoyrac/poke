def build_session_report(metrics: dict) -> str:
    return f"Session report: {metrics.get('drills_today', 0)} drills, EV loss/100 {metrics.get('ev_loss_per_100', 0)}."

