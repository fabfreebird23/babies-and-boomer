#!/usr/bin/env python
"""Seed the keeper ledger (2023-2025) from the league spreadsheet.

Sleeper's `is_keeper` flag is blank/unreliable for this league, so keeper-YEAR
counting and rookie-keeper detection need an authoritative ledger. This writes
data/keepers_<yr>.json in the app's storage format (the same files the app reads
for prior-season keepers), so history.build_history picks them up automatically:
keep-year continuity, rookie-keeper exemptions, and rookie->regular conversions
all flow from here.

Re-run after editing the ledger below. Names are resolved to Sleeper player_ids;
any that don't resolve are printed so you can fix the spelling.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kreeper import sleeper, config  # noqa: E402
from kreeper.names import normalize_name  # noqa: E402

# Manager full name -> current Sleeper owner_id.
MGR = {
    "Brandon Clifton": "964703051971887104",
    "Devin Hussey":    "964742665126432768",
    "Ian Keller":      "964742534272446464",
    "Jordan Keller":   "599073863350927360",
    "Joey Strelow":    "952088015260774400",
    "Alex Haney":      "964746446002077696",
    "Grant Kenny":     "964742545727098880",
    "Jacob Butler":    "964725862010503168",
    "Sean Meenagh":    "731597672364015616",
    "Trevor Weldy":    "964873449275473920",
}

# Per year: manager -> {"reg": [(player, cost_round), ...], "rook": [(player, round_or_None), ...]}
# `reg` = Keeper 1/2/3 (regular keepers); `rook` = Rookie Keeper slots.
LEDGER = {
    2023: {
        "Brandon Clifton": {"reg": [("Travis Etienne", 4), ("Tee Higgins", 4), ("Jaylen Waddle", 5)],
                            "rook": [("Breece Hall", None), ("Kenneth Walker", None)]},
        "Devin Hussey":   {"reg": [("Tyreek Hill", 3), ("Patrick Mahomes", 6), ("Rhamondre Stevenson", 10)],
                           "rook": []},
        "Ian Keller":     {"reg": [("Saquon Barkley", 3), ("Chris Godwin", 7), ("Pat Freiermuth", 15)],
                           "rook": [("Chris Olave", None)]},
        "Jordan Keller":  {"reg": [("Austin Ekeler", 1), ("Jalen Hurts", 11), ("Alexander Mattison", 10)],
                           "rook": [("George Pickens", None)]},
        "Joey Strelow":   {"reg": [("Ja'Marr Chase", 1), ("A.J. Brown", 3), ("Justin Fields", 14)],
                           "rook": [("Brian Robinson", None), ("Treylon Burks", None)]},
        "Alex Haney":     {"reg": [("Stefon Diggs", 2), ("Tony Pollard", 6), ("Calvin Ridley", 11)],
                           "rook": [("Dameon Pierce", None), ("Rachaad White", None)]},
        "Grant Kenny":    {"reg": [("Justin Jefferson", 1), ("Tyler Lockett", 8), ("Kirk Cousins", 15)],
                           "rook": [("Garrett Wilson", None)]},
        "Jacob Butler":   {"reg": [("Amon-Ra St. Brown", 6), ("DeVonta Smith", 8), ("Lamar Jackson", 9)],
                           "rook": [("Jahan Dotson", None)]},
        "Sean Meenagh":   {"reg": [("Travis Kelce", 2), ("CeeDee Lamb", 3), ("Miles Sanders", 7)],
                           "rook": [("Alec Pierce", None)]},
        "Trevor Weldy":   {"reg": [("Christian McCaffrey", 1), ("T.J. Hockenson", 9), ("Joe Burrow", 13)],
                           "rook": []},
    },
    2024: {
        "Brandon Clifton": {"reg": [("DeVonta Smith", 5), ("De'Von Achane", 12), ("Tank Dell", 16)],
                            "rook": [("Bijan Robinson", 16), ("Breece Hall", 16)]},
        "Devin Hussey":   {"reg": [("Tyreek Hill", 1), ("Rhamondre Stevenson", 7), ("Isiah Pacheco", 7)],
                           "rook": [("Sam LaPorta", 16), ("Zay Flowers", 16)]},
        "Ian Keller":     {"reg": [("Drake London", 4), ("Dalton Kincaid", 12), ("Kyler Murray", 16)],
                           "rook": [("Chris Olave", 16)]},
        "Jordan Keller":  {"reg": [("Mike Evans", 6), ("Jalen Hurts", 8), ("Nico Collins", 9)],
                           "rook": [("George Pickens", 16), ("Zach Charbonnet", 16)]},
        "Joey Strelow":   {"reg": [("Ja'Marr Chase", 1), ("Jonathan Taylor", 2), ("Kyren Williams", 16)],
                           "rook": [("Josh Downs", 16)]},
        "Alex Haney":     {"reg": [("CeeDee Lamb", 1), ("Kyle Pitts", 9), ("Rachaad White", 13)],
                           "rook": [("Jahmyr Gibbs", 16), ("Jordan Addison", 16)]},
        "Grant Kenny":    {"reg": [("Justin Jefferson", 1), ("James Cook", 5)],
                           "rook": [("Jayden Reed", 16), ("Garrett Wilson", 16)]},
        "Jacob Butler":   {"reg": [("Amon-Ra St. Brown", 3), ("Trey McBride", 16), ("Puka Nacua", 16)],
                           "rook": [("Jahan Dotson", 16), ("Tyjae Spears", 16)]},
        "Sean Meenagh":   {"reg": [("Kenneth Walker", 8), ("C.J. Stroud", 16), ("Gus Edwards", 16)],
                           "rook": [("Anthony Richardson", 16), ("Jaxon Smith-Njigba", 16)]},
        "Trevor Weldy":   {"reg": [("Joe Mixon", 3), ("Michael Pittman", 6), ("Joe Burrow", 10)],
                           "rook": [("Rashee Rice", 16)]},
    },
    2025: {
        "Brandon Clifton": {"reg": [("Lamar Jackson", 5), ("De'Von Achane", 9), ("DeVonta Smith", 6)],
                            "rook": [("Breece Hall", 16), ("Bijan Robinson", 16)]},
        "Devin Hussey":   {"reg": [("Josh Allen", 4), ("Chase Brown", 9), ("Chuba Hubbard", 10)],
                           "rook": [("Ladd McConkey", 16), ("Sam LaPorta", 16)]},
        "Ian Keller":     {"reg": [("Drake London", 4), ("Kyler Murray", 13), ("J.K. Dobbins", 10)],
                           "rook": [("Jonathon Brooks", 16), ("Chris Olave", 16)]},
        "Jordan Keller":  {"reg": [("Nico Collins", 6), ("George Pickens", 10), ("T.J. Hockenson", 10)],
                           "rook": [("Jayden Daniels", 16), ("Rome Odunze", 16)]},
        "Joey Strelow":   {"reg": [("Ja'Marr Chase", 1), ("Terry McLaurin", 4), ("Kyren Williams", 13)],
                           "rook": [("Keon Coleman", 16), ("Brock Bowers", 16)]},
        "Alex Haney":     {"reg": [("CeeDee Lamb", 1), ("J.J. McCarthy", 15), ("Bucky Irving", 14)],
                           "rook": [("Jahmyr Gibbs", 16), ("Brian Thomas", 16)]},
        "Grant Kenny":    {"reg": [("Justin Jefferson", 1), ("Jameson Williams", 10), ("Jayden Reed", 13)],
                           "rook": [("Caleb Williams", 16), ("Garrett Wilson", 16)]},
        "Jacob Butler":   {"reg": [("A.J. Brown", 2), ("Puka Nacua", 13), ("Trey McBride", 13)],
                           "rook": [("Malik Nabers", 16), ("Xavier Legette", 16)]},
        "Sean Meenagh":   {"reg": [("Saquon Barkley", 1), ("Derrick Henry", 2), ("George Kittle", 4)],
                           "rook": [("Jaxon Smith-Njigba", 16), ("Marvin Harrison", 16)]},
        "Trevor Weldy":   {"reg": [("Joe Burrow", 4), ("Tee Higgins", 4), ("Jerry Jeudy", 11)],
                           "rook": [("Rashee Rice", 16)]},
    },
}


def build_index(players):
    idx = {}
    for pid, p in players.items():
        nm = normalize_name(p.get("full_name") or "")
        if not nm:
            continue
        score = (1 if p.get("position") in ("QB", "RB", "WR", "TE") else 0,
                 1 if p.get("active") else 0, 1 if p.get("team") else 0)
        if nm not in idx or score > idx[nm][1]:
            idx[nm] = (pid, score)
    return {k: v[0] for k, v in idx.items()}


def main():
    players = sleeper.get_players()
    idx = build_index(players)
    unresolved = []

    for year, by_mgr in LEDGER.items():
        out = {}
        for mgr, slots in by_mgr.items():
            owner = MGR[mgr]
            picks = []
            for is_rookie, key in ((False, "reg"), (True, "rook")):
                for name, rnd in slots.get(key, []):
                    pid = idx.get(normalize_name(name))
                    if not pid:
                        unresolved.append(f"{year} {mgr}: {name}")
                        continue
                    picks.append({
                        "player_id": pid,
                        "player_name": name,
                        "is_rookie_keeper": is_rookie,
                        "cost_round": rnd,
                    })
            out[owner] = picks
        path = config.DATA_DIR / f"keepers_{year}.json"
        path.write_text(json.dumps(out, indent=2))
        total = sum(len(v) for v in out.values())
        print(f"wrote {path.name}: {total} keepers across {len(out)} managers")

    if unresolved:
        print("\nUNRESOLVED (fix the spelling in LEDGER):")
        for u in unresolved:
            print("  -", u)
    else:
        print("\nAll names resolved.")


if __name__ == "__main__":
    main()
