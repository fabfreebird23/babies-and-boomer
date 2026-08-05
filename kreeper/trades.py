"""Recent completed trades, pulled live from Sleeper — mirrors
kreeper-league's get_recent_trades()/render_recent_trades().

Pure data function; the caller (app.py) does the HTML rendering so this
module stays Streamlit-free like the rest of kreeper/*.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List

from . import config, sleeper


def _transactions(league_id: str, week: int) -> List[Dict[str, Any]]:
    """sleeper.get_transactions is new in this deploy, added to an already-
    imported `sleeper` module — same stale-cached-module risk as
    kreeper/lottery.py's _losers_bracket and kreeper/phase.py's _nfl_state.
    Fetch directly via sleeper's pre-existing private _get/_disk instead."""
    try:
        return sleeper._disk(  # noqa: SLF001
            f"transactions_{league_id}_{week}", 900,
            lambda: sleeper._get(f"league/{league_id}/transactions/{week}") or [],  # noqa: SLF001
        )
    except Exception:  # noqa: BLE001
        return []


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def recent_trades(player_name_fn, league_id=None, limit: int = 8) -> List[Dict[str, Any]]:
    """Completed trades from Sleeper, newest first — every asset each side
    received, players and picks alike.

    `player_name_fn(player_id) -> str` is injected rather than imported so
    this module doesn't need to know about DraftHistory/player_meta."""
    league_id = league_id or config.league()["sleeper_league_id"]
    r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in sleeper.get_rosters(league_id)}

    raw = []
    for wk in range(0, 19):
        txs = _transactions(league_id, wk)
        raw.extend(t for t in txs if t.get("type") == "trade" and t.get("status") == "complete")
    raw.sort(key=lambda t: t.get("status_updated") or 0, reverse=True)

    out = []
    for tx in raw[:limit]:
        roster_ids = tx.get("roster_ids") or []
        adds = tx.get("adds") or {}
        picks = tx.get("draft_picks") or []
        receives: Dict[int, List[str]] = {rid: [] for rid in roster_ids}
        for pid, rid in adds.items():
            if rid in receives:
                receives[rid].append(player_name_fn(pid))
        for p in picks:
            owner = p.get("owner_id")
            if owner in receives:
                receives[owner].append(f'{p.get("season")} {_ordinal(int(p.get("round", 0)))}')
        teams = [(config.manager_name(r2o.get(rid, "")), receives.get(rid, [])) for rid in roster_ids]
        ts = tx.get("status_updated")
        date = dt.datetime.fromtimestamp(ts / 1000).strftime("%b %d, %Y") if ts else ""
        out.append({"teams": teams, "date": date})
    return out
