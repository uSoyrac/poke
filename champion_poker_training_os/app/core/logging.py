from __future__ import annotations

import logging
import os

# Yutulan (swallow edilen) istisnalar için ayrı logger. Normalde sessiz;
# CPT_DEBUG=1 ile DEBUG seviyesinde görünür hale gelir → gerçek bug'lar
# kontrol akışını bozmadan yüzeye çıkar.
_swallow_logger = logging.getLogger("cpt.swallowed")


def configure_logging() -> None:
    level = logging.DEBUG if os.environ.get("CPT_DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def log_swallowed(context: str, exc: BaseException) -> None:
    """Bir except bloğunda yutulan istisnayı DEBUG'da kaydet.

    Kontrol akışını DEĞİŞTİRMEZ — çağıran kendi fallback'ine devam eder.
    Amaç: 'except: pass' ile sessizce kaybolan gerçek hataları, hata
    ayıklarken (CPT_DEBUG=1) görünür kılmak. UI'ı asla çökertmez.
    """
    _swallow_logger.debug(
        "swallowed in %s: %s: %s", context, type(exc).__name__, exc
    )
