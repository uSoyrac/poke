"""D295: devam-eden turnuva autosave + resume (donma/çökme/kapanmada KAYIP YOK).
Her el-sonu temiz state diske yazılır; app açılışında 'Turnuvaya Devam Et' ile son
elden devam edilir. Kullanıcı (D294 freeze sonrası): 'turnuva bug yüzünden kaybolmamalı.'

Snapshot = {tournament: Tournament.to_dict, mtt_field: MTTField.to_dict, meta...}.
Tamamlanınca/iptal edilince clear edilir (bitmiş turnuvayı resume önerme)."""
from __future__ import annotations
import json

from app.core.config import DATA_DIR

_PATH = DATA_DIR / "tournament_resume.json"


def save_snapshot(snap: dict) -> bool:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(snap), encoding="utf-8")
        return True
    except Exception:
        return False


def load_snapshot() -> "dict | None":
    try:
        if _PATH.exists():
            return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def clear_snapshot() -> None:
    try:
        if _PATH.exists():
            _PATH.unlink()
    except Exception:
        pass


def has_snapshot() -> bool:
    try:
        return _PATH.exists()
    except Exception:
        return False
