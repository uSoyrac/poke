"""log_swallowed — yutulan istisnaları kontrol akışını bozmadan kaydeder."""
from __future__ import annotations

import logging


def test_log_swallowed_records_at_debug(caplog):
    from app.core.logging import log_swallowed
    with caplog.at_level(logging.DEBUG, logger="cpt.swallowed"):
        try:
            raise ValueError("boom")
        except Exception as e:  # noqa: BLE001
            log_swallowed("test.context", e)
    assert any("test.context" in r.message and "boom" in r.message
               for r in caplog.records), caplog.records


def test_log_swallowed_never_raises():
    """Logger içeride patlasa bile çağıran asla istisna almamalı."""
    from app.core.logging import log_swallowed
    # Tuhaf bir nesne ver — yine de sessizce loglamalı, raise etmemeli
    log_swallowed("ctx", RuntimeError("x"))   # raise etmemeli
