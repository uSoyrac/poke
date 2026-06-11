"""SHCP-turnuva botu testi: koç-advice'ı (soyrac_advice tourney=True + D173 steal
+ D177 Nash push/fold) turnuvada GERÇEKTEN oynat → FT/ITM. Eski #24 (pre-fix) ve
ICM Expert (FT %10-12) ile kıyas. 'range development işe yaradı mı' = ölç."""
from __future__ import annotations
import copy, random
from collections import defaultdict
import app.engine.bot_brain as BB
import app.engine.game_loop as GL
import app.simulator.headless_mtt as H
from app.engine.bot_brain import BOT_ARCHETYPES, archetype_skill as _os
import app.engine.bot_brain as BBmod
from app.engine.hand_state import ActionType, Street
from app.poker.soyrac_advisor import advice_from_hand
from tools.soyrac_bot_sim import SoyracBrain

class SoyracSHCPTourney(SoyracBrain):
    """Turnuva PREFLOP'u da soyrac_advice (tourney=True) ile oyna (ICM Expert değil)
    → D173 steal + D177 Nash push/fold sahada test edilir. Postflop delege kalır."""
    def decide(self, state, idx):
        p = state.players[idx]
        valid = {t for (t, _, _) in state.get_valid_actions(idx)}
        to_call = state.to_call(idx)
        bb = max(state.big_blind, 0.01)
        eff = (p.stack + p.current_bet) / bb
        if self.tournament_mode and state.street == Street.PREFLOP:
            adv = advice_from_hand(state, idx, stack_bb=eff,
                                   icm=self.icm_pressure > 0, tourney=True)
            act = (adv or {}).get("action", "FOLD")
            if act == "JAM" and ActionType.ALL_IN in valid:
                return ActionType.ALL_IN, p.stack
            if act in ("RAISE (AÇ)", "3-BET", "4-BET"):
                if eff <= 12 and ActionType.ALL_IN in valid:
                    return ActionType.ALL_IN, p.stack
                to = (max(bb * 2.3, state.min_raise + p.current_bet) if act == "RAISE (AÇ)"
                      else max(min(state.current_bet * 3.0, p.stack + p.current_bet),
                               state.min_raise + p.current_bet))
                if ActionType.RAISE in valid:
                    return ActionType.RAISE, to
                if ActionType.BET in valid:
                    return ActionType.BET, to
            if act == "CALL" and ActionType.CALL in valid:
                return ActionType.CALL, to_call
            if to_call <= 0 and ActionType.CHECK in valid:
                return ActionType.CHECK, 0.0
            return (ActionType.FOLD, 0.0) if ActionType.FOLD in valid else (ActionType.CHECK, 0.0)
        return super().decide(state, idx)

# enjeksiyon (reliability deseni)
import tools.soyrac_reliability as R
R.SoyracBrain = SoyracSHCPTourney   # factory bunu kullanır mı? hayır — R._factory SoyracBrain'i import-time bağladı
# factory'yi yeniden bağla
_RealBB = BB.BotBrain
SOY = R.SOY
def _factory(profile, *a, **k):
    return SoyracSHCPTourney() if profile is SOY else _RealBB(profile, *a, **k)
GL.BotBrain = _factory; H.BotBrain = _factory

if __name__ == "__main__":
    import time; t0 = time.time()
    pl = []
    for s in range(14):
        rng = random.Random(9000 + s)
        R._FIELD = R.build_field(200, "karma", rng)
        r = H.run_mtt(200, seed=9000 + s); order = r["finish_1st_to_last"]; n = len(order)
        for rank, a in enumerate(order, 1):
            if a == "Soyrac": pl.append((rank, n))
    e = len(pl); ft = sum(1 for r, n in pl if r <= 9); itm = sum(1 for r, n in pl if r <= n*0.15)
    win = sum(1 for r, n in pl if r == 1)
    print(f"=== SHCP-TURNUVA (yeni advice D173+D177) · {e} entrant ({time.time()-t0:.0f}s) ===")
    print(f"  FT %{100*ft/e:.1f} · ITM %{100*itm/e:.0f} · şampiyon %{100*win/e:.2f}")
    print(f"  KIYAS: eski SHCP-tourney #24 (ITM ~%9) · ICM Expert delege (FT %10-12, ITM %26)")
    print(f"  → {'GELİŞTİ (eski %9 ITM çok üstü)' if 100*itm/e > 15 else 'sınırlı'}")
