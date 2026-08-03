"""Unit tests for the draft-order lottery (kreeper/lottery.py)."""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kreeper import lottery  # noqa: E402


WEIGHTS = {"A": 640, "B": 320, "C": 160, "D": 80, "E": 40, "F": 20, "G": 8, "H": 4, "I": 2, "J": 1}


# --------------------------------------------------------- position_probabilities
def test_each_teams_distribution_sums_to_one():
    probs = lottery.position_probabilities(WEIGHTS)
    for o, dist in probs.items():
        assert abs(sum(dist) - 1.0) < 1e-9, o


def test_each_position_total_sums_to_one():
    probs = lottery.position_probabilities(WEIGHTS)
    n = len(WEIGHTS)
    for pos in range(n):
        assert abs(sum(probs[o][pos] for o in probs) - 1.0) < 1e-9


def test_first_choice_probability_matches_weight_share():
    probs = lottery.position_probabilities(WEIGHTS)
    total = sum(WEIGHTS.values())
    for o, w in WEIGHTS.items():
        assert abs(probs[o][0] - w / total) < 1e-9


def test_last_place_team_still_has_a_shot_at_first_choice():
    # Weight 1 out of 1275 total -> small but strictly positive.
    probs = lottery.position_probabilities(WEIGHTS)
    assert probs["J"][0] > 0


def test_heaviest_team_is_most_likely_to_pick_last():
    # Team A (640 balls) should have the LOWEST chance of ending up picking last,
    # and team J (1 ball) the highest.
    probs = lottery.position_probabilities(WEIGHTS)
    assert probs["J"][-1] > probs["A"][-1]


# ---------------------------------------------------------------------- draw_order
def test_draw_order_is_a_permutation_of_all_teams():
    import random
    order = lottery.draw_order(WEIGHTS, rng=random.Random(1))
    assert sorted(order) == sorted(WEIGHTS)
    assert len(order) == len(WEIGHTS)


def test_draw_order_is_reproducible_with_a_seeded_rng():
    import random
    a = lottery.draw_order(WEIGHTS, rng=random.Random(7))
    b = lottery.draw_order(WEIGHTS, rng=random.Random(7))
    assert a == b


def test_heavier_weight_wins_first_choice_more_often_over_many_draws():
    import random
    rng = random.Random(0)
    firsts = {o: 0 for o in WEIGHTS}
    for _ in range(2000):
        firsts[lottery.draw_order(WEIGHTS, rng=rng)[0]] += 1
    # Team A (640/1275 ~ 50%) should win first choice far more than team J (1/1275).
    assert firsts["A"] > firsts["J"] * 20


# --------------------------------------------------------------------- final_tiers
def _bracket(winner_roster, loser_roster, placement=1):
    return [{"p": placement, "m": 3, "r": 2, "w": winner_roster, "l": loser_roster}]


def _rosters():
    # 4 teams: 1=champ, 2=runner-up, 3=chase winner, 4=chase loser.
    return [
        {"roster_id": 1, "owner_id": "champ", "settings": {"wins": 12, "losses": 2, "fpts": 1500}},
        {"roster_id": 2, "owner_id": "runner", "settings": {"wins": 10, "losses": 4, "fpts": 1400}},
        {"roster_id": 3, "owner_id": "chase", "settings": {"wins": 3, "losses": 11, "fpts": 1000}},
        {"roster_id": 4, "owner_id": "chaseloser", "settings": {"wins": 2, "losses": 12, "fpts": 900}},
    ]


def test_final_tiers_assigns_highest_weight_to_chase_winner_and_lowest_to_champion():
    with patch.object(lottery.sleeper, "get_rosters", return_value=_rosters()), \
         patch.object(lottery.sleeper, "get_winners_bracket", return_value=_bracket(1, 2)), \
         patch.object(lottery, "_losers_bracket", return_value=_bracket(3, 4)), \
         patch.object(lottery, "_weights", return_value=[640, 320, 160, 80]):
        tiers = lottery.final_tiers("fake_league")

    assert tiers["chase"]["weight"] == 640
    assert tiers["chase"]["tier"] == "Chase for the Pick winner"
    assert tiers["champ"]["weight"] == 80
    assert tiers["champ"]["tier"] == "League champion"
    # The remaining 2 (runner, chaseloser) split the middle weights, worst record first.
    assert tiers["chaseloser"]["weight"] == 320  # 2-12, worse than runner's 10-4
    assert tiers["runner"]["weight"] == 160


def test_final_tiers_none_when_brackets_are_undecided():
    with patch.object(lottery.sleeper, "get_rosters", return_value=_rosters()), \
         patch.object(lottery.sleeper, "get_winners_bracket", return_value=[]), \
         patch.object(lottery, "_losers_bracket", return_value=[]):
        assert lottery.final_tiers("fake_league") is None


def test_season_is_complete_requires_both_brackets_decided():
    with patch.object(lottery.sleeper, "get_rosters", return_value=_rosters()), \
         patch.object(lottery.sleeper, "get_winners_bracket", return_value=_bracket(1, 2)), \
         patch.object(lottery, "_losers_bracket", return_value=[]):
        assert lottery.season_is_complete("fake_league") is False

    with patch.object(lottery.sleeper, "get_rosters", return_value=_rosters()), \
         patch.object(lottery.sleeper, "get_winners_bracket", return_value=_bracket(1, 2)), \
         patch.object(lottery, "_losers_bracket", return_value=_bracket(3, 4)):
        assert lottery.season_is_complete("fake_league") is True
