"""TexasSolver adapter — arms-length subprocess entegrasyonu.

TexasSolver (https://github.com/bupticybee/TexasSolver) açık kaynak,
AGPL-3.0, Discounted CFR — PioSolver'ı flop'ta yener. Ama AGPL viral.

LİSANS YAKLAŞIMI (arms-length / mere aggregation):
  - TexasSolver binary'sini PAKETLEMİYORUZ.
  - Kullanıcı binary'yi kendisi indirir/derler ve path'ini verir.
  - Biz sadece subprocess ile çağırırız (input dosyası yaz → çalıştır →
    JSON output oku). git/ffmpeg çağırmak gibi. FSF'e göre ayrı programları
    CLI ile çağırmak türev eser değil → bizim kod AGPL olmak zorunda kalmaz.
  - Binary yoksa → kullanılamaz, built-in nested_solver fallback olur.

Kullanım:
    eng = TexasSolverEngine(binary_path="/path/to/console_solver")
    if eng.available:
        result = eng.solve(
            board="Qs,Jh,2h", pot=10, effective_stack=100,
            range_oop="AA,KK,...", range_ip="...",
            bet_sizes=[50], iterations=100,
        )
        # result: {hand: {action: freq}} (OOP strategy)

NOT: TexasSolver console komut formatı sürüme göre değişebilir. Komutlar
console_solver'ın dokümante ettiği standart sete dayanır; uyumsuzluk
olursa _build_input_commands() güncellenebilir.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


def find_texassolver_binary() -> Optional[str]:
    """Binary path'ini bul: env var → yaygın konumlar → None."""
    # 1) Açık env var
    p = os.environ.get("TEXASSOLVER_PATH", "").strip()
    if p and Path(p).exists():
        return p
    # 2) Yaygın konumlar
    candidates = [
        "console_solver", "console_solver.exe",
        os.path.expanduser("~/TexasSolver/console_solver"),
        os.path.expanduser("~/TexasSolver/console_solver.exe"),
        "/usr/local/bin/console_solver",
        "/Applications/TexasSolver/console_solver",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    # 3) PATH üzerinde mi
    from shutil import which
    w = which("console_solver")
    return w


@dataclass
class TexasSolverResult:
    ok: bool
    oop_strategy: Dict[str, Dict[str, float]] = field(default_factory=dict)
    ip_strategy: Dict[str, Dict[str, float]] = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    elapsed_ms: int = 0
    error: str = ""


class TexasSolverEngine:
    """TexasSolver console binary'sini subprocess ile süren adapter."""

    def __init__(self, binary_path: Optional[str] = None):
        self.binary = binary_path or find_texassolver_binary()

    @property
    def available(self) -> bool:
        return bool(self.binary) and Path(self.binary).exists()

    # ── INPUT COMMAND FILE ────────────────────────────────────────────
    def _build_input_commands(
        self,
        board: str,
        pot: float,
        effective_stack: float,
        range_oop: str,
        range_ip: str,
        bet_sizes: List[int],
        iterations: int,
        accuracy: float,
        threads: int,
        output_path: str,
        use_isomorphism: bool = True,
        dump_rounds: int = 1,
    ) -> str:
        """TexasSolver console komut script'i üret."""
        bet_str = ",".join(str(b) for b in bet_sizes) or "50"
        lines = [
            f"set_pot {pot}",
            f"set_effective_stack {effective_stack}",
            f"set_board {board}",
            f"set_range_oop {range_oop}",
            f"set_range_ip {range_ip}",
            # Bet/raise size'lar (her oyuncu × her street)
        ]
        for player in ("oop", "ip"):
            for street in ("flop", "turn", "river"):
                lines.append(f"set_bet_sizes {player},{street},bet,{bet_str}")
                lines.append(f"set_bet_sizes {player},{street},raise,60")
            lines.append(f"set_bet_sizes {player},flop,allin")
        lines += [
            "build_tree",
            f"set_thread_num {threads}",
            f"set_accuracy {accuracy}",
            f"set_max_iteration {iterations}",
            "set_print_interval 10",
            f"set_use_isomorphism {1 if use_isomorphism else 0}",
            "start_solve",
            f"set_dump_rounds {dump_rounds}",
            f"dump_result {output_path}",
        ]
        return "\n".join(lines) + "\n"

    # ── SOLVE ─────────────────────────────────────────────────────────
    def solve(
        self,
        board: str,
        pot: float = 10.0,
        effective_stack: float = 100.0,
        range_oop: str = "",
        range_ip: str = "",
        bet_sizes: Optional[List[int]] = None,
        iterations: int = 100,
        accuracy: float = 0.5,
        threads: int = 4,
        timeout_sec: int = 300,
    ) -> TexasSolverResult:
        """TexasSolver'ı çalıştır ve OOP/IP stratejilerini döndür."""
        import time
        if not self.available:
            return TexasSolverResult(ok=False, error="TexasSolver binary bulunamadı")

        bet_sizes = bet_sizes or [50]
        t0 = time.time()
        tmpdir = Path(tempfile.mkdtemp(prefix="texassolver_"))
        input_file = tmpdir / "input.txt"
        output_file = tmpdir / "output.json"

        cmds = self._build_input_commands(
            board=board, pot=pot, effective_stack=effective_stack,
            range_oop=range_oop, range_ip=range_ip, bet_sizes=bet_sizes,
            iterations=iterations, accuracy=accuracy, threads=threads,
            output_path=str(output_file),
        )
        input_file.write_text(cmds, encoding="utf-8")

        try:
            proc = subprocess.run(
                [self.binary, "-i", str(input_file)],
                capture_output=True, text=True, timeout=timeout_sec,
                cwd=str(Path(self.binary).parent),
            )
        except subprocess.TimeoutExpired:
            return TexasSolverResult(ok=False,
                                     error=f"Timeout ({timeout_sec}s)")
        except Exception as e:
            return TexasSolverResult(ok=False, error=f"Subprocess hatası: {e}")

        elapsed = int((time.time() - t0) * 1000)

        if not output_file.exists():
            return TexasSolverResult(
                ok=False, elapsed_ms=elapsed,
                error=(f"Output dosyası oluşmadı. stderr: "
                       f"{proc.stderr[:300] if proc.stderr else '(yok)'}"),
            )

        try:
            raw = json.loads(output_file.read_text(encoding="utf-8"))
        except Exception as e:
            return TexasSolverResult(ok=False, elapsed_ms=elapsed,
                                     error=f"JSON parse hatası: {e}")

        oop, ip = self._parse_strategy(raw)
        return TexasSolverResult(
            ok=True, oop_strategy=oop, ip_strategy=ip,
            raw=raw, elapsed_ms=elapsed,
        )

    # ── OUTPUT PARSE ──────────────────────────────────────────────────
    def _parse_strategy(self, raw: dict):
        """TexasSolver JSON çıktısından root node stratejilerini çıkar.

        TexasSolver output ağaç yapısında: her node 'strategy' içerir
        ({actions: [...], strategy: {hand: [freq_per_action]}}).
        Root node'un (ilk decision) stratejisini OOP olarak alırız.
        Format sürüme göre değişebilir → esnek parse.
        """
        oop: Dict[str, Dict[str, float]] = {}
        ip: Dict[str, Dict[str, float]] = {}

        # Root strategy bul — yaygın anahtarlar
        node = raw
        # Bazı sürümler {"strategy": {...}, "childrens": {...}} kullanır
        strat_node = self._find_first_strategy(node)
        if strat_node:
            actions = strat_node.get("actions", [])
            hand_strats = strat_node.get("strategy", {})
            for hand, freqs in hand_strats.items():
                if isinstance(freqs, list) and len(freqs) == len(actions):
                    oop[hand] = {actions[i]: round(100 * freqs[i], 1)
                                 for i in range(len(actions))}
        return oop, ip

    def _find_first_strategy(self, node, depth=0):
        """Ağaçta ilk 'strategy' + 'actions' içeren node'u bul (DFS)."""
        if depth > 6 or not isinstance(node, dict):
            return None
        if "strategy" in node and "actions" in node:
            return node
        # childrens / children içinde ara
        for key in ("childrens", "children", "dealcards"):
            child = node.get(key)
            if isinstance(child, dict):
                for v in child.values():
                    found = self._find_first_strategy(v, depth + 1)
                    if found:
                        return found
            elif isinstance(child, list):
                for v in child:
                    found = self._find_first_strategy(v, depth + 1)
                    if found:
                        return found
        return None


# ── PUBLIC HELPER ─────────────────────────────────────────────────────

def texassolver_status() -> dict:
    """UI için: TexasSolver mevcut mu, path nerede?"""
    eng = TexasSolverEngine()
    return {
        "available": eng.available,
        "binary": eng.binary or "",
        "hint": ("TEXASSOLVER_PATH env var ile veya Settings'ten "
                 "console_solver binary path'ini ver."),
    }
