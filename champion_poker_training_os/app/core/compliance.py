from __future__ import annotations

from app.core.rta_guard import RtaGuardStatus


OFFLINE_COMPLIANCE_RULES = [
    "No live-table decisions",
    "No screen reading",
    "No overlay or HUD",
    "No automated mouse/keyboard actions",
    "Past hands, manual study spots and offline simulations only",
]


def compliance_summary(status: RtaGuardStatus) -> str:
    prefix = "Locked" if status.locked else "Compliant"
    return f"{prefix}: {status.message}"

