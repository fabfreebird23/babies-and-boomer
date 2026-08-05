"""Home-page phase detection, mirroring kreeper-league's kreeper/phase.py.

Phase is inferred from data already on hand — no manual dates to remember to
flip each year:

  keepers_open  — keeper_deadline is set and hasn't passed yet
  pre_draft     — keepers are locked but the Sleeper draft isn't complete
  pre_season    — draft is complete, NFL games haven't started
  in_season     — NFL is in its regular season or postseason
  offseason     — the Sleeper league itself is marked complete

Pure logic module — no Streamlit here.
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from . import config, sleeper

PHASES = ["keepers_open", "pre_draft", "pre_season", "in_season", "offseason"]


def _nfl_state() -> dict:
    """sleeper.get_nfl_state is new in this deploy, added to an already-
    imported `sleeper` module — Streamlit Cloud's hot redeploy doesn't
    reliably reload new attributes onto a module that predates the deploy
    (see kreeper/lottery.py's _losers_bracket for the same fix). Fetch
    directly via sleeper's pre-existing private _get/_disk instead."""
    try:
        return sleeper._disk("nfl_state", 3600, lambda: sleeper._get("state/nfl") or {})  # noqa: SLF001
    except Exception:  # noqa: BLE001
        return {}


def current_phase(league_id: Optional[str] = None) -> str:
    league_id = league_id or config.league()["sleeper_league_id"]

    deadline = config.keeper_deadline()
    if deadline is not None and dt.datetime.now(deadline.tzinfo) < deadline:
        return "keepers_open"

    lg = sleeper.get_league(league_id)
    if lg.get("status") == "complete":
        return "offseason"

    draft_id = lg.get("draft_id")
    if draft_id:
        try:
            if sleeper.get_draft(draft_id).get("status") != "complete":
                return "pre_draft"
        except Exception:  # noqa: BLE001 — a flaky Sleeper call shouldn't crash the home page
            return "pre_draft"

    season_type = _nfl_state().get("season_type")
    if season_type in ("regular", "post"):
        return "in_season"
    return "pre_season"


def draft_date_label(league_id: Optional[str] = None) -> str:
    """The real draft start_time from Sleeper, formatted ('Aug 13') — unlike
    kreeper's hardcoded label, this stays correct without a yearly edit."""
    league_id = league_id or config.league()["sleeper_league_id"]
    try:
        lg = sleeper.get_league(league_id)
        draft_id = lg.get("draft_id")
        if not draft_id:
            return ""
        ts = sleeper.get_draft(draft_id).get("start_time")
        if not ts:
            return ""
        return dt.datetime.fromtimestamp(ts / 1000).strftime("%b %-d")
    except Exception:  # noqa: BLE001
        return ""
