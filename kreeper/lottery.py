"""Next season's draft-order lottery.

Ball weights are assigned to 10 tiers (config.yaml `lottery.weights`, most to
least):

  1.   "Chase for the Pick" winner — the consolation bracket's (Sleeper
       losers_bracket) placement-1 winner.
  2-9. The remaining 8 teams, by THIS season's regular-season record,
       worst to best.
  10.  The league champion (winners_bracket placement-1 winner).

The lottery itself determines a SELECTION order, not a draft slot directly:
position 1 gets first choice of any of the 10 draft slots, position 2 chooses
next from what's left, and so on — a human choice this module doesn't (and
can't) predict, so "odds" here mean odds of landing each selection position,
not odds of ending up in any particular draft slot.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional, Tuple

from . import config, sleeper, storage

_DEFAULT_WEIGHTS = [640, 320, 160, 80, 40, 20, 8, 4, 2, 1]


def _weights() -> List[int]:
    """Read straight from config.load() rather than config.lottery_weights() —
    both this module and that function were added in the same deploy, and a
    stale cached `kreeper.config` module on Streamlit Cloud (which doesn't
    always reload on a hot rerun) can AttributeError on the newer name."""
    try:
        w = config.load().get("lottery", {}).get("weights")
        return [int(x) for x in w] if w else list(_DEFAULT_WEIGHTS)
    except (ValueError, TypeError):
        return list(_DEFAULT_WEIGHTS)


def _roster_to_owner(league_id: str) -> Dict[int, str]:
    return {int(r["roster_id"]): str(r.get("owner_id")) for r in sleeper.get_rosters(league_id)}


def _losers_bracket(league_id: str) -> List[dict]:
    """Fetch via sleeper's pre-existing private _get/_disk helpers directly,
    NOT sleeper.get_losers_bracket — that's a new public name on the existing
    `sleeper` module, and Streamlit Cloud's hot redeploy doesn't reliably
    reload new attributes onto an already-imported module (the same
    AttributeError this sidesteps hit config.lottery_weights first). _get and
    _disk predate this feature, so they're safe."""
    try:
        return sleeper._disk(  # noqa: SLF001
            f"loser_bracket_{league_id}", 86400,
            lambda: sleeper._get(f"league/{league_id}/losers_bracket") or [],  # noqa: SLF001
        )
    except Exception:  # noqa: BLE001
        return []


def _placement_winner(bracket: List[dict], r2o: Dict[int, str]) -> Optional[str]:
    """owner_id of the p==1 (placement game) winner, or None if undecided/absent."""
    for m in bracket or []:
        if m.get("p") == 1 and m.get("w") is not None:
            return r2o.get(int(m["w"]))
    return None


def season_is_complete(league_id: Optional[str] = None) -> bool:
    """True once both the championship AND the Chase-for-the-Pick game have a
    decided winner — that's everything final_tiers() needs."""
    league_id = league_id or config.league()["sleeper_league_id"]
    r2o = _roster_to_owner(league_id)
    champ = _placement_winner(sleeper.get_winners_bracket(league_id), r2o)
    chase = _placement_winner(_losers_bracket(league_id), r2o)
    return champ is not None and chase is not None


def _standings(league_id: str) -> List[Tuple[str, int, int, float]]:
    """[(owner_id, wins, losses, points_for)], as Sleeper currently has it."""
    out = []
    for r in sleeper.get_rosters(league_id):
        o = str(r.get("owner_id"))
        s = r.get("settings", {}) or {}
        w, l = int(s.get("wins", 0) or 0), int(s.get("losses", 0) or 0)
        pf = float(s.get("fpts", 0) or 0) + float(s.get("fpts_decimal", 0) or 0) / 100
        out.append((o, w, l, pf))
    return out


def final_tiers(league_id: Optional[str] = None) -> Optional[Dict[str, dict]]:
    """owner_id -> {"weight", "tier", "rank"} for a COMPLETED season, or None
    if the champion / Chase-for-the-Pick winner isn't decided yet."""
    league_id = league_id or config.league()["sleeper_league_id"]
    r2o = _roster_to_owner(league_id)
    champ = _placement_winner(sleeper.get_winners_bracket(league_id), r2o)
    chase = _placement_winner(_losers_bracket(league_id), r2o)
    if champ is None or chase is None:
        return None

    weights = _weights()
    standings = _standings(league_id)
    rest = [row for row in standings if row[0] not in (champ, chase)]
    rest.sort(key=lambda row: (row[1], row[3]))  # worst first: fewest wins, then fewest points

    out: Dict[str, dict] = {
        chase: {"weight": weights[0], "tier": "Chase for the Pick winner", "rank": 1},
        champ: {"weight": weights[-1], "tier": "League champion", "rank": len(weights)},
    }
    for i, (o, *_rest) in enumerate(rest):
        out[o] = {"weight": weights[1 + i], "tier": "Regular season standing", "rank": 2 + i}
    return out


def position_probabilities(weights: Dict[str, float]) -> Dict[str, List[float]]:
    """Exact P(team gets selection position k) for k = 1..n, via DP over the
    2^n possible "teams remaining" states — fast for n=10 (1024 states) and
    exact, unlike a Monte Carlo estimate.

    owner_id -> [P(1st choice), P(2nd choice), ..., P(nth choice)].
    """
    owners = list(weights)
    n = len(owners)
    full = (1 << n) - 1
    result = {o: [0.0] * n for o in owners}

    # DP over "which teams still remain" (2^n states), processed in
    # decreasing order of remaining-team count so every predecessor state is
    # finalized before it's needed.
    states_by_count: Dict[int, List[int]] = {}
    for mask in range(full + 1):
        states_by_count.setdefault(bin(mask).count("1"), []).append(mask)

    prob = {full: 1.0}
    for count in range(n, 0, -1):
        for mask in states_by_count.get(count, []):
            p_here = prob.get(mask, 0.0)
            if p_here <= 0:
                continue
            total_w = sum(weights[owners[i]] for i in range(n) if mask & (1 << i))
            if total_w <= 0:
                continue
            position = n - count  # 0-indexed: this draw fills position `position`
            for i in range(n):
                bit = 1 << i
                if not (mask & bit):
                    continue
                p_pick = p_here * weights[owners[i]] / total_w
                result[owners[i]][position] += p_pick
                prob[mask & ~bit] = prob.get(mask & ~bit, 0.0) + p_pick
    return result


def draw_order(weights: Dict[str, float], rng: Optional[random.Random] = None) -> List[str]:
    """One real weighted draw without replacement. Returns owner_ids in
    SELECTION order: index 0 chooses first, index -1 chooses last."""
    rng = rng or random.Random()
    remaining = dict(weights)
    order: List[str] = []
    while remaining:
        total = sum(remaining.values())
        r = rng.uniform(0, total)
        upto = 0.0
        for o, w in remaining.items():
            upto += w
            if r <= upto:
                order.append(o)
                del remaining[o]
                break
        else:  # floating-point edge case: last item
            o = next(iter(remaining))
            order.append(o)
            del remaining[o]
    return order


def live_projection(league_id: Optional[str] = None, playoff_teams: int = 4) -> Dict[str, Any]:
    """A live, in-progress-season estimate: "if the season ended today, then
    the playoffs/consolation played out by relative strength, here's roughly
    where each team would land." Clearly an approximation — real outcomes
    depend on games not yet played and a single-elim bracket's randomness.

    Model: seed by CURRENT record (wins, then points-for) into a top group
    (playoff_teams, champion-eligible) and the next playoff_teams (Chase-for-
    -the-Pick-eligible); everyone else can only land in the standings tier.
    Within each seed group, win probability is a softmax on THIS SEASON's
    win% and points-for (no cross-season history — that's a different model,
    used for Title Odds) — simple and self-contained, not a full bracket
    Monte Carlo.
    """
    league_id = league_id or config.league()["sleeper_league_id"]
    standings = _standings(league_id)
    standings.sort(key=lambda row: (-row[1], -row[3]))  # best first

    top = standings[:playoff_teams]
    mid = standings[playoff_teams:2 * playoff_teams]

    def _group_win_probs(group: List[Tuple[str, int, int, float]]) -> Dict[str, float]:
        if not group:
            return {}
        import math
        pf_vals = [row[3] for row in group]
        pf_mean = sum(pf_vals) / len(pf_vals)
        pf_sd = (sum((v - pf_mean) ** 2 for v in pf_vals) / len(pf_vals)) ** 0.5 or 1.0
        scores = {}
        for o, w, l, pf in group:
            win_pct = w / max(1, w + l)
            pf_z = (pf - pf_mean) / pf_sd
            scores[o] = 1.4 * win_pct + 0.5 * pf_z
        exps = {o: math.exp(s) for o, s in scores.items()}
        tot = sum(exps.values()) or 1.0
        return {o: v / tot for o, v in exps.items()}

    champ_probs = _group_win_probs(top)
    chase_probs = _group_win_probs(mid)

    weights = _weights()
    # If a team doesn't win its own bracket, it lands in the standings tier —
    # at a rank we can't know yet (that depends on who else avoids winning
    # their bracket too). As a clearly-approximate stand-in, use the weight
    # for the standings tier at this team's OWN current overall rank (worst
    # overall = the highest standings-tier weight if they land there). Exact
    # once the season and both brackets are decided; a reasonable, honestly
    # labeled preview until then.
    standings_weights = weights[1:-1]  # the 8 middle tiers, worst to best
    n_teams = len(standings)

    rows = []
    for rank, (o, w, l, pf) in enumerate(standings):
        worst_first_rank = n_teams - 1 - rank  # 0 = worst record overall
        idx = min(worst_first_rank, len(standings_weights) - 1) if standings_weights else 0
        standings_wt = standings_weights[idx] if standings_weights else 1
        p_c = champ_probs.get(o, 0.0)
        p_h = chase_probs.get(o, 0.0)
        p_neither = max(0.0, 1 - p_c - p_h)
        rows.append({
            "owner": o, "wins": w, "losses": l, "pf": round(pf, 1),
            "current_rank": rank + 1,
            "p_champion": round(p_c, 4),
            "p_chase_winner": round(p_h, 4),
            "expected_weight": round(p_c * weights[-1] + p_h * weights[0] + p_neither * standings_wt, 1),
        })

    rows.sort(key=lambda r: -r["expected_weight"])
    return {"season": config.current_season(), "rows": rows,
            "playoff_teams": playoff_teams}


# --------------------------------------------------------------- persistence
# Reimplemented here rather than calling storage.load_lottery/save_lottery —
# those are new public names on the existing `storage` module, same stale-
# cached-module risk as sleeper.get_losers_bracket above. Built entirely on
# storage's PRE-EXISTING private primitives (_gh_config/_headers/
# _ensure_branch/_API, all present before this feature), which are safe.
def _record_path(season: int) -> str:
    return f"data/lottery_{season}.json"


def _record_local_path(season: int):
    import os
    from pathlib import Path
    base = Path(os.environ.get("KREEPER_DATA", config.DATA_DIR))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"lottery_{season}.json"


def load_record(season: Optional[int] = None) -> Dict[str, Any]:
    """The persisted lottery record for the season whose results set the
    weights. {} if nothing has been drawn yet."""
    season = season or config.current_season()
    if season == config.current_season() and storage._gh_config() is not None:  # noqa: SLF001
        try:
            tok, repo, branch = storage._gh_config()  # noqa: SLF001
            r = storage.requests.get(
                f"{storage._API}/repos/{repo}/contents/{_record_path(season)}",  # noqa: SLF001
                headers=storage._headers(tok), params={"ref": branch}, timeout=15,  # noqa: SLF001
            )
            if r.status_code == 404:
                return {}
            r.raise_for_status()
            import base64 as _b64
            import json as _json
            content = _b64.b64decode(r.json()["content"]).decode()
            return _json.loads(content) if content.strip() else {}
        except Exception:  # noqa: BLE001
            pass
    p = _record_local_path(season)
    if not p.exists():
        return {}
    try:
        import json as _json
        return _json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_record(data: Dict[str, Any], season: Optional[int] = None) -> None:
    season = season or config.current_season()
    if season == config.current_season() and storage._gh_config() is not None:  # noqa: SLF001
        import base64 as _b64
        import json as _json
        tok, repo, branch = storage._gh_config()  # noqa: SLF001
        storage._ensure_branch(repo, branch, tok)  # noqa: SLF001
        path = _record_path(season)
        for _ in range(3):  # retry on a concurrent-write SHA conflict
            sha = None
            r = storage.requests.get(
                f"{storage._API}/repos/{repo}/contents/{path}",  # noqa: SLF001
                headers=storage._headers(tok), params={"ref": branch}, timeout=15,  # noqa: SLF001
            )
            if r.status_code == 200:
                sha = r.json()["sha"]
            body = {
                "message": f"lottery: {season} draft-order lottery",
                "content": _b64.b64encode(_json.dumps(data, indent=2).encode()).decode(),
                "branch": branch,
            }
            if sha:
                body["sha"] = sha
            put = storage.requests.put(
                f"{storage._API}/repos/{repo}/contents/{path}",  # noqa: SLF001
                headers=storage._headers(tok), json=body, timeout=20,  # noqa: SLF001
            )
            if put.status_code in (200, 201):
                return
            if put.status_code != 409:
                put.raise_for_status()
        raise RuntimeError("GitHub save failed after retries")
    import json as _json
    p = _record_local_path(season)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(_json.dumps(data, indent=2))
    tmp.replace(p)
