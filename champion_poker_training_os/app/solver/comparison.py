from __future__ import annotations

from app.solver.mock_solver import compare_action


def solver_comparison_summary(spot: dict, action: str) -> str:
    comparison = compare_action(spot, action)
    return (
        f"Hero {action}; solver baseline {comparison['best_action']} "
        f"({comparison['best_frequency']:.0%}). EV loss: {comparison['ev_loss']:.2f}bb."
    )

