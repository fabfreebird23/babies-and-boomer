"""Unit tests for the keeper cost engine (Babies and Boomer rules)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kreeper import engine  # noqa: E402

# This league's house rules: ADP may LOWER a keeper's cost ("use a lesser ADP
# value if you want"), and a rookie->regular conversion costs the player's
# original rookie draft round (not a last-round pick).
RULES = {"max_keep_years": 3, "year2_bump_rounds": 3,
         "rookie_keeper_cost": "last_rounds", "rookie_fixed_round": 16,
         "rookie_conversion_cost": "original_round", "allow_adp_discount": True}
NT = 8
ROUNDS = 16


def prof(next_year, original_round, acquired="draft"):
    return {"next_keep_year": next_year, "original_round": original_round,
            "consecutive_keeper_years": next_year - 1, "acquired_via": acquired}


def test_year1_keeps_at_draft_round():
    # ADP rank 40 -> R5, EARLIER (more expensive) than the R8 draft slot, so the
    # discount doesn't apply and ADP can't raise a Year-1 cost.
    c = engine.compute(prof(1, 8), adp_rank=40, rules=RULES, num_teams=NT)
    assert c.eligible and c.keep_year == 1 and c.recommended_round == 8
    assert all("ADP" not in o.label for o in c.options)


def test_year1_adp_discount_allows_cheaper_round():
    # Drafted R3, but ADP has fallen to R10 (later/cheaper) -> may keep at ADP.
    c = engine.compute(prof(1, 3), adp_rank=80, rules=RULES, num_teams=NT)  # 80/8 -> R10
    assert c.keep_year == 1 and c.recommended_round == 10
    assert any("ADP" in o.label for o in c.options)


def test_year2_bump_is_default_but_adp_can_discount():
    # Drafted R12, bump = R9. ADP rank 24 -> R3 (earlier/more expensive): the bump
    # stays the recommended (cheaper) cost, but ADP is still offered as a choice.
    c = engine.compute(prof(2, 12), adp_rank=24, rules=RULES, num_teams=NT)
    assert c.keep_year == 2 and c.recommended_round == 9
    assert any("ADP" in o.label for o in c.options)
    # Faded player: drafted R12, ADP rank 80 -> R10 (later/cheaper than the R9
    # bump). The discount rule lets the manager keep at ADP, and we recommend it.
    c2 = engine.compute(prof(2, 12), adp_rank=80, rules=RULES, num_teams=NT)
    assert c2.recommended_round == 10
    assert any("ADP" in o.label for o in c2.options)


def test_year3_always_adp():
    p = prof(3, 12)
    p["last_season_record"] = {"round": 10}
    c = engine.compute(p, adp_rank=16, rules=RULES, num_teams=NT)   # R2
    assert c.recommended_round == 2
    c2 = engine.compute(p, adp_rank=80, rules=RULES, num_teams=NT)  # R10
    assert c2.recommended_round == 10


def test_year2_bump_floor_round_1():
    c = engine.compute(prof(2, 2), adp_rank=None, rules=RULES, num_teams=NT)
    assert c.recommended_round == 1  # max(1, 2-3)


def test_fourth_year_ineligible():
    c = engine.compute(prof(4, 5), adp_rank=16, rules=RULES, num_teams=NT)
    assert not c.eligible


def test_rookie_keeper_exempt_and_locked():
    c = engine.compute(prof(5, 14), adp_rank=10, is_rookie_keeper=True, rules=RULES, num_teams=NT)
    assert c.eligible and c.keep_year == "Rookie"


def waiver_prof(next_year=1):
    return {"next_keep_year": next_year, "original_round": None,
            "consecutive_keeper_years": next_year - 1, "acquired_via": "undrafted"}


def trade_prof(next_year, original_round):
    return {"next_keep_year": next_year, "original_round": original_round,
            "consecutive_keeper_years": next_year - 1, "acquired_via": "trade"}


def test_traded_keeper_inherits_round_and_clock():
    # JSN: kept at R10 in year 1, traded -> year 2 -> bump to R7.
    items = [
        {"player_id": "jsn", "is_rookie": False, "profile": trade_prof(2, 10),
         "adp_rank": 5, "year2_choice": None},  # ADP R1 (more expensive) -> bump R7 wins
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES)
    assert out["jsn"].keep_year == 2 and out["jsn"].recommended_round == 7
    assert out["jsn"].recommended_round != ROUNDS  # not dumped into the last rounds


def test_rookies_take_last_rounds_first():
    items = [
        {"player_id": "a", "is_rookie": True, "profile": prof(1, 5), "adp_rank": 10, "year2_choice": None},
        {"player_id": "b", "is_rookie": True, "profile": prof(1, 3), "adp_rank": 20, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES)
    assert out["a"].keep_year == "Rookie" and out["a"].recommended_round == 16
    assert out["b"].recommended_round == 15


def test_waiver_pickup_takes_latest_available_after_rookies():
    items = [
        {"player_id": "rook", "is_rookie": True, "profile": prof(1, 9), "adp_rank": 5, "year2_choice": None},
        {"player_id": "wv", "is_rookie": False, "profile": waiver_prof(1), "adp_rank": 30, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES)
    assert out["rook"].recommended_round == 16   # rookie takes the last round
    assert out["wv"].recommended_round == 15      # waiver takes next latest available


def test_drafted_keeper_keeps_normal_cost_in_allocation():
    items = [
        {"player_id": "d", "is_rookie": False, "profile": prof(1, 8), "adp_rank": 40, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES)
    assert out["d"].recommended_round == 8        # Year 1 -> drafted round (ADP R5 is more expensive)


# ----------------------------------------------------------------- conversions
def test_rookie_to_regular_costs_original_round_and_resets_clock():
    # A long-running rookie keeper converting to a regular keeper is costed at the
    # round they were originally drafted as a rookie (here R4), NOT a last round,
    # and the 3-year clock restarts at Year 1.
    items = [
        {"player_id": "c", "is_rookie": False, "from_rookie": True,
         "rookie_draft_round": 4, "profile": prof(4, 2), "adp_rank": None, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES)
    assert out["c"].eligible and out["c"].keep_year == 1
    assert out["c"].recommended_round == 4
    assert out["c"].recommended_round != ROUNDS


def test_rookie_to_regular_yields_to_current_rookie():
    items = [
        {"player_id": "rook", "is_rookie": True, "profile": prof(1, 5), "adp_rank": 9, "year2_choice": None},
        {"player_id": "conv", "is_rookie": False, "from_rookie": True, "rookie_draft_round": 6,
         "profile": prof(3, 4), "adp_rank": None, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES)
    assert out["rook"].recommended_round == 16    # current rookie takes the last round
    assert out["conv"].recommended_round == 6 and out["conv"].keep_year == 1


def test_rookie_to_regular_ineligible_without_high_pick():
    from collections import Counter
    owned = Counter({r: 1 for r in range(5, ROUNDS + 1)})  # earliest owned pick is R5
    items = [{"player_id": "c", "is_rookie": False, "from_rookie": True,
              "rookie_draft_round": 3, "profile": prof(3, 3), "adp_rank": None, "year2_choice": None}]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES, owned=owned)
    assert out["c"].eligible is False
    assert out["c"].recommended_round is None


def test_rookie_to_regular_last_rounds_mode():
    # With the other league's rule, a conversion still falls to the last rounds.
    last_rules = {**RULES, "rookie_conversion_cost": "last_rounds"}
    items = [
        {"player_id": "c", "is_rookie": False, "from_rookie": True,
         "rookie_draft_round": 4, "profile": prof(4, 2), "adp_rank": 5, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=last_rules)
    assert out["c"].keep_year == 1 and out["c"].recommended_round == 16


def test_two_waivers_take_descending_rounds():
    items = [
        {"player_id": "w1", "is_rookie": False, "profile": waiver_prof(1), "adp_rank": None, "year2_choice": None},
        {"player_id": "w2", "is_rookie": False, "profile": waiver_prof(1), "adp_rank": None, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES)
    assert {out["w1"].recommended_round, out["w2"].recommended_round} == {16, 15}


# --------------------------------------------------------------- owned snapping
def test_adjust_to_owned_bumps_to_next_highest():
    from collections import Counter
    owned = Counter({r: 1 for r in range(1, ROUNDS + 1)})
    owned[7] = 0  # traded away R7
    assert engine.adjust_to_owned(7, owned, ROUNDS) == 6
    assert engine.adjust_to_owned(5, owned, ROUNDS) == 5


def test_adjust_to_owned_none_without_high_enough_pick():
    from collections import Counter
    owned = Counter({r: 1 for r in range(4, ROUNDS + 1)})  # traded away R1-R3
    owned[5] = 0
    assert engine.adjust_to_owned(4, owned, ROUNDS) == 4
    assert engine.adjust_to_owned(5, owned, ROUNDS) == 4
    assert engine.adjust_to_owned(3, owned, ROUNDS) is None
    assert engine.adjust_to_owned(1, owned, ROUNDS) is None


def test_keeper_ineligible_without_high_enough_pick():
    from collections import Counter
    owned = Counter({r: 1 for r in range(4, ROUNDS + 1)})  # earliest pick is R4
    items = [{"player_id": "kw", "is_rookie": False, "profile": prof(1, 3),
              "adp_rank": 24, "year2_choice": None}]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES, owned=owned)
    assert out["kw"].eligible is False
    assert out["kw"].recommended_round is None
    items2 = [{"player_id": "ok", "is_rookie": False, "profile": prof(1, 4),
               "adp_rank": 24, "year2_choice": None}]
    out2 = engine.allocate_keeper_costs(items2, draft_rounds=ROUNDS, num_teams=NT, rules=RULES, owned=owned)
    assert out2["ok"].eligible and out2["ok"].recommended_round == 4


def test_allocation_snaps_to_owned_pick():
    from collections import Counter
    owned = Counter({r: 1 for r in range(1, ROUNDS + 1)})
    owned[7] = 0  # team traded away its R7 pick
    # JSN: drafted R10, kept once -> Year 2 -> bump to R7; but R7 not owned -> R6.
    items = [{"player_id": "jsn", "is_rookie": False, "profile": prof(2, 10),
              "adp_rank": 5, "year2_choice": "Round 7"}]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES, owned=owned)
    assert out["jsn"].recommended_round == 6


def test_multiple_keepers_same_round_when_multiple_picks():
    from collections import Counter
    owned = Counter({r: 1 for r in range(1, ROUNDS + 1)})
    owned[ROUNDS] = 2
    items = [
        {"player_id": "a", "is_rookie": True, "profile": prof(1, 5), "adp_rank": 10, "year2_choice": None},
        {"player_id": "b", "is_rookie": True, "profile": prof(1, 5), "adp_rank": 20, "year2_choice": None},
        {"player_id": "c", "is_rookie": True, "profile": prof(1, 5), "adp_rank": 30, "year2_choice": None},
    ]
    out = engine.allocate_keeper_costs(items, draft_rounds=ROUNDS, num_teams=NT, rules=RULES, owned=owned)
    assert out["a"].recommended_round == 16
    assert out["b"].recommended_round == 16   # second R16 pick used
    assert out["c"].recommended_round == 15   # only the third drops to R15


def test_adp_rank_to_round():
    assert engine.adp_rank_to_round(1, NT) == 1
    assert engine.adp_rank_to_round(NT, NT) == 1
    assert engine.adp_rank_to_round(NT + 1, NT) == 2
    assert engine.adp_rank_to_round(None, NT) is None


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    raise SystemExit(1 if failed else 0)
