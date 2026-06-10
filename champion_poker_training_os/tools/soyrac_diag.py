"""Soyrac cash sızıntı teşhisi — parayı NEREDE kaybediyor (street/aksiyon bazlı)."""
from __future__ import annotations
import random
from collections import defaultdict
from app.engine.game_loop import PokerGame
from app.engine.bot_brain import BOT_ARCHETYPES
from app.engine.hand_state import ActionType, Street
import tools.soyrac_bot_sim as S

REC = []   # (street, action, amount, eq, to_call, pot)

class DiagBrain(S.SoyracBrain):
    def decide(self, state, idx):
        before_street = state.street
        to_call = state.to_call(idx); pot = state.pot
        eq = self._equity(state.players[idx], state) if state.community else None
        act = super().decide(state, idx)
        REC.append((str(before_street).split('.')[-1], act[0].name, round(act[1],1),
                    round(eq,2) if eq is not None else None, round(to_call,1), round(pot,1)))
        return act

def run(hands=500, seed=7):
    names=['Soyrac','GTO Expert','Solver Bot','ICM Expert','Fish','Calling Station']
    net=defaultdict(float); button=0
    bucket=defaultdict(lambda:[0,0.0])   # tag -> [count, net]
    for h in range(hands):
        REC.clear()
        ss=[100.0]*6
        gl=PokerGame(num_players=6,starting_stack=100.0,small_blind=0.5,big_blind=1.0,
                     ante=0,hero_seat=0,bot_archetypes=names[1:],
                     player_names=[f'a{i}' for i in range(1,6)],paced_bots=True)
        for i in range(6): gl.players[i].stack=100.0
        gl.dealer_idx=button%6
        soyrac=DiagBrain()
        for b in gl.bots.values(): b.tournament_mode=True
        gl.start_hand(); guard=0
        while guard<800:
            guard+=1; hh=gl.current_hand
            if hh and hh.is_complete: break
            prog=gl.step_action()
            if gl.is_waiting_for_hero:
                at,amt=soyrac.decide(gl.current_hand, gl.current_hand.hero_idx)
                gl.hero_act(at,amt)
            elif not prog: break
        delta=gl.players[0].stack-100.0
        net['Soyrac']+=delta
        for i in range(6): net[names[i]]+=gl.players[i].stack-100.0
        # bucketle: Soyrac hangi street'e kadar gitti + agresör müydü + allin?
        streets=set(r[0] for r in REC)
        saw_flop='FLOP' in streets or 'TURN' in streets or 'RIVER' in streets
        was_aggr=any(r[1] in ('BET','RAISE','ALL_IN') for r in REC)
        allin=any(r[1]=='ALL_IN' for r in REC)
        pre_raise=any(r[0]=='PREFLOP' and r[1] in ('BET','RAISE') for r in REC)
        tag = ('ALLIN' if allin else 'POSTFLOP-AGGR' if (saw_flop and was_aggr) else
               'POSTFLOP-PASSIVE' if saw_flop else 'PREFLOP-RAISE' if pre_raise else 'PREFLOP-FOLD')
        bucket[tag][0]+=1; bucket[tag][1]+=delta
        button=(button+1)%6
    print(f'=== {hands} el · Soyrac net {net["Soyrac"]:.0f} chip = {100*net["Soyrac"]/hands:.1f}bb/100 ===')
    print('PARA NEREDE GİDİYOR (Soyrac hand-tipi bazlı):')
    for tag,(c,nt) in sorted(bucket.items(), key=lambda x:x[1][1]):
        print(f'  {tag:<18} {c:>4} el · net {nt:>8.0f} chip · {nt/max(c,1):>6.1f}/el')
    # en büyük kayıp eli örneği (son hand REC'i değil; toplamı yeter)
    print('\nDiğer profiller bb/100:', {k:round(100*net[k]/hands,1) for k in names if k!='Soyrac'})

if __name__=='__main__':
    import random as _r; _r.seed(1234); run(20000)
