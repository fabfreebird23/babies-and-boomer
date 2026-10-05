"""Babies and Boomer — Keeper Hub (Streamlit app).

Pages (sidebar nav):
  Home            — top-30 keeper-value leaderboard + per-team submitted keepers
  Set my keepers  — pick your roster's keepers, with live cost + eligibility
  Consensus ADP   — daily multi-source consensus ADP (all sources averaged)
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

def _fresh_kreeper() -> None:
    """Drop stale kreeper.* modules after a deploy, so a push never needs a
    Reboot.

    Streamlit re-executes THIS file on every run, but everything it imports
    stays in sys.modules for the life of the process — and Streamlit Cloud
    keeps the process across a push. So new app.py code ran against the last
    deploy's theme.py / sleeper.py, and anything new on them (a helper, a
    constant) raised AttributeError until someone pressed Reboot.

    Fingerprint the package's files (size + mtime, which a git checkout
    changes); if the loaded copy was built from different files — or predates
    this guard and carries no fingerprint at all — forget every kreeper
    module so the imports below load fresh. A plain rerun keeps them. Same
    fix as the Draft Room's _fresh_draftkit.
    """
    import hashlib
    import pathlib
    import sys
    root = pathlib.Path(__file__).resolve().parent / "kreeper"
    h = hashlib.sha1()
    for f in sorted(root.rglob("*.py")):
        try:
            st_ = f.stat()
        except OSError:
            continue
        h.update(f"{f.relative_to(root)}:{st_.st_size}:{st_.st_mtime_ns}".encode())
    fp = h.hexdigest()
    loaded = sys.modules.get("kreeper")
    if loaded is not None and getattr(loaded, "_fingerprint", None) != fp:
        for name in [m for m in sys.modules if m == "kreeper" or m.startswith("kreeper.")]:
            del sys.modules[name]
    import kreeper
    kreeper._fingerprint = fp


_fresh_kreeper()

from kreeper import (config, draftboard, engine, gameday, history, live_draft, phase, season,
                     sleeper, storage, theme)
from kreeper.adp import consensus as adp_consensus
from kreeper.names import normalize_name

st.set_page_config(page_title="Babies and Boomer — Keeper Hub", layout="wide")
theme.inject(st)

LEAGUE = config.league()
SEASON = config.current_season()
MANAGERS = config.managers()  # owner_id -> {handle, name, team}
# Championship-bracket size, from Sleeper's league settings.
_LG_SETTINGS = sleeper.get_league(LEAGUE["sleeper_league_id"]).get("settings", {}) or {}
PLAYOFF_TEAMS = int(_LG_SETTINGS.get("playoff_teams") or 4)
NAME_TO_ID = {m["name"]: oid for oid, m in MANAGERS.items()}
NT = int(LEAGUE["num_teams"])
DRAFT_ROUNDS = int(LEAGUE["draft_rounds"])
# Scope ADP risers/fallers + the Consensus ADP move view to the players actually
# in range of being drafted — the top 100 by consensus ADP.
DRAFT_SCOPE_RANK = 100
MAX_REG = int(LEAGUE.get("max_regular_keepers", 3))
MAX_ROOKIE = int(LEAGUE.get("max_rookie_keepers", 2))
# How a rookie keeper costs when moved into a regular slot: "original_round"
# (the round they were drafted as a rookie) or "last_rounds".
ROOKIE_CONV_MODE = str(config.rules().get("rookie_conversion_cost", "last_rounds"))
# When false, a keeper just costs its computed round (no snapping to an owned
# pick even if the cost round was traded away). See config `enforce_owned_picks`.
ENFORCE_OWNED = bool(LEAGUE.get("enforce_owned_picks", False))


def keeper_lock() -> tuple:
    """(deadline_or_None, locked_bool). Locked once now >= the deadline."""
    deadline = config.keeper_deadline()
    if deadline is None:
        return None, False
    now = dt.datetime.now(deadline.tzinfo) if deadline.tzinfo else dt.datetime.now()
    return deadline, now >= deadline


def _fmt_ts(iso: str) -> str:
    try:
        d = dt.datetime.fromisoformat(iso)
        return d.strftime("%b %d, %-I:%M %p")
    except (ValueError, TypeError):
        return iso or ""


_COUNTDOWN_TEMPLATE = """
<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Oswald:wght@500;600;700&display=swap" rel="stylesheet">
<style>
 *{margin:0;box-sizing:border-box;}
 html,body{background:transparent;overflow:hidden;font-family:'Oswald',sans-serif;}
 .cd{display:flex;flex-direction:column;align-items:center;gap:6px;
   background:#fff;border:2px solid #4b2d9f;border-radius:16px;padding:14px 18px;
   box-shadow:0 6px 22px rgba(123,92,255,.18);}
 .ttl{font-family:'Oswald',sans-serif;font-weight:600;text-transform:uppercase;letter-spacing:3px;
   font-size:15px;color:#4b2d9f;}
 .units{display:flex;gap:16px;}
 .u{display:flex;flex-direction:column;align-items:center;min-width:60px;}
 .u .n{font-family:'Oswald',sans-serif;font-weight:600;font-size:42px;line-height:1;color:#4b2d9f;
   text-shadow:0 0 12px rgba(255,79,157,.45);}
 .u .l{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#8b86a0;margin-top:5px;}
 .sub{font-size:12px;letter-spacing:1px;color:#6a6580;}
 .locked{font-family:'Oswald',sans-serif;font-weight:600;font-size:30px;color:#4b2d9f;letter-spacing:2px;}
</style></head><body>
<div class="cd">
  <div class="ttl">&#9203; Keepers Due In</div>
  <div id="units" class="units"></div>
  <div class="sub" id="when"></div>
</div>
<script>
 var target=new Date("__ISO__").getTime();
 var box=document.getElementById('units'), when=document.getElementById('when');
 when.textContent="Announce by "+new Date(target).toLocaleString('en-US',
   {timeZone:'__TZ__',weekday:'long',month:'long',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
 function pad(n){return String(n).padStart(2,'0');}
 function tick(){
   var d=target-Date.now();
   if(d<=0){box.innerHTML='<div class="locked">&#128274; KEEPERS LOCKED</div>';
            when.textContent="The deadline has passed.";return;}
   var days=Math.floor(d/86400000),h=Math.floor(d/3600000)%24,
       m=Math.floor(d/60000)%60,s=Math.floor(d/1000)%60;
   var cells=[[days,'Days'],[h,'Hrs'],[m,'Min'],[s,'Sec']];
   box.innerHTML=cells.map(function(c){
     var n=(c[1]==='Days')?c[0]:pad(c[0]);
     return '<div class="u"><div class="n">'+n+'</div><div class="l">'+c[1]+'</div></div>';
   }).join('');
 }
 tick(); setInterval(tick,1000);
</script></body></html>
"""


def render_countdown() -> None:
    deadline = config.keeper_deadline()
    if deadline is None:
        return
    html = (_COUNTDOWN_TEMPLATE
            .replace("__ISO__", deadline.isoformat())
            .replace("__TZ__", config.keeper_timezone_name()))
    components.html(html, height=150)


# ---------------------------------------------------------------- data loaders
@st.cache_resource(show_spinner="Loading league history from Sleeper…")
def get_history() -> history.DraftHistory:
    return history.build_history()


@st.cache_data(ttl=3600, show_spinner=False)
def get_candidates():
    return history.roster_candidates()


@st.cache_data(ttl=300, show_spinner=False)
def get_adp():
    return adp_consensus.load(SEASON), adp_consensus.adp_lookup(SEASON), adp_consensus.load_meta(SEASON)


@st.cache_data(ttl=600, show_spinner=False)
def get_board():
    return draftboard.build_board()


@st.cache_data(ttl=600, show_spinner=False)
def get_owned():
    """owner_id -> Counter of draft rounds the team owns (after trades)."""
    return draftboard.owned_picks_by_owner()


@st.cache_data(ttl=600, show_spinner=False)
def get_owned_for(season: int):
    """owner_id -> Counter of rounds owned for a given (incl. future) season."""
    return draftboard.owned_picks_by_owner(season=season)


def owned_for(owner_id: str):
    """The owned-pick Counter to cost keepers against, or None when the league
    doesn't enforce pick ownership (then a keeper just costs its computed round)."""
    return get_owned().get(owner_id) if ENFORCE_OWNED else None


@st.cache_data(ttl=600, show_spinner=False)
def current_draft_done() -> bool:
    """True once this season's draft has been run. After that its picks are
    spent — they're players on rosters now — so anything that trades picks
    has to start from next year's draft."""
    try:
        lg = sleeper.get_league(LEAGUE["sleeper_league_id"])
        return (sleeper.get_draft(lg["draft_id"]) or {}).get("status") == "complete"
    except Exception:
        return False


def current_pick_slots():
    """owner_id -> {round: [overall pick_no, ...]} for the CURRENT season, using
    the real snake- and trade-aware draft slots from the board (so a 1.01 and a
    1.03 are distinct picks with distinct values)."""
    board = get_board()
    r2o = {rid: o for o, rid in board["owner_to_roster"].items()}
    out: dict = {}
    for (rnd, _slot), c in board["cells"].items():
        owner = r2o.get(c["owner_roster"])
        if owner is None:
            continue
        out.setdefault(owner, {}).setdefault(rnd, []).append(c["pick_no"])
    for rounds in out.values():
        for nums in rounds.values():
            nums.sort()
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def get_name_index():
    """normalized name -> Sleeper player_id (skill positions; prefer active/with team)."""
    from kreeper import sleeper
    idx = {}
    for pid, p in sleeper.get_players().items():
        if p.get("position") not in ("QB", "RB", "WR", "TE"):
            continue
        nm = normalize_name(p.get("full_name") or "")
        if not nm:
            continue
        score = (1 if p.get("active") else 0, 1 if p.get("team") else 0)
        if nm not in idx or score > idx[nm][1]:
            idx[nm] = (pid, score)
    return {k: v[0] for k, v in idx.items()}


@st.cache_data(ttl=86400, show_spinner=False)
def get_espn_headshots():
    """sleeper_pid -> ESPN headshot id, so rookies with no Sleeper photo still
    get a real headshot. Sleeper's own espn_id wins; otherwise match by name to
    ESPN's board. Best-effort — returns {} if ESPN is unreachable."""
    from kreeper import sleeper
    from kreeper.adp import espn
    try:
        by_name = espn.headshot_ids(SEASON)
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for pid, p in sleeper.get_players().items():
        if p.get("position") not in ("QB", "RB", "WR", "TE"):
            continue
        eid = p.get("espn_id") or by_name.get(normalize_name(p.get("full_name") or ""))
        if eid:
            out[str(pid)] = str(eid)
    return out


H = get_history()
CANDS = get_candidates()
ADP_DF, ADP_LK, ADP_META = get_adp()

# player_id -> the owner who CURRENTLY rosters them (after Sleeper trades). Lets us
# drop a declared keeper from a team that has since traded the player away.
PID_OWNER = {str(p): str(o) for o, pids in CANDS.items() for p in pids}


def submitted_keepers(season=None):
    """Saved keeper selections, dropping any player no longer on that owner's
    current Sleeper roster (e.g. traded away after declaring them). Use this for
    every CURRENT-season submission display; historical reads keep storage.load(yr)."""
    season = season or SEASON
    out = {}
    for oid, picks in storage.load(season).items():
        out[str(oid)] = [s for s in picks
                         if s.get("player_id") and PID_OWNER.get(str(s["player_id"])) == str(oid)]
    return out


def manager_submitted(owner_id, season=None):
    """A single manager's still-rostered submitted keepers (post-trade aware)."""
    return submitted_keepers(season).get(str(owner_id), [])
theme.set_espn_ids(get_espn_headshots())


def adp_rank_for(name: str, position: str = "") -> float | None:
    key = f"{normalize_name(name)}|{position.lower()}" if position else None
    if key and key in ADP_LK:
        return ADP_LK[key]
    return ADP_LK.get(normalize_name(name))


def build_candidate_rows(owner_id: str) -> pd.DataFrame:
    rows = []
    owned = owned_for(owner_id)
    for pid in CANDS.get(owner_id, []):
        pm = H.player_meta(pid)
        if pm.position not in ("QB", "RB", "WR", "TE"):
            continue  # keepers are skill-position players in this league
        prof = H.keeper_profile(owner_id, pid, SEASON)
        rank = adp_rank_for(pm.name, pm.position)
        cost = engine.compute(prof, adp_rank=rank, is_rookie_keeper=False)
        from_rookie = _rookie_ledger_holds(owner_id, pid) and not ever_regular_keeper(pid)
        # A rookie->regular conversion under original_round mode is costed like a
        # Year-1 keeper anchored at the rookie draft round (snapped to a pick you own).
        conv_anchor = rookie_draft_round(pid) if (from_rookie and ROOKIE_CONV_MODE == "original_round") else None
        inherits = (not from_rookie) and prof.get("acquired_via") in ("draft", "trade") and prof.get("original_round")
        no_pick = False
        if conv_anchor:
            # Cost like a Year-1 keeper anchored at the rookie draft round — but
            # allow_adp_discount still applies, so if ADP is a later (cheaper)
            # round than the rookie round, use that instead (matches the
            # allocate_keeper_costs conversion path used when keepers are saved).
            conv_prof = {**prof, "next_keep_year": 1, "consecutive_keeper_years": 0,
                         "acquired_via": "draft", "original_round": conv_anchor}
            conv_cost = engine.compute(conv_prof, adp_rank=rank, is_rookie_keeper=False)
            target = conv_cost.recommended_round or conv_anchor
            placed = engine.adjust_to_owned(target, owned, DRAFT_ROUNDS)
            if placed is None:
                no_pick = True
                reg_cost = "No pick to keep"
            else:
                reg_cost = f"Round {placed}"
        elif inherits:
            # The pick used is the cost round, or the nearest earlier (higher)
            # pick you own. If you own nothing at the cost round or earlier, you
            # can't keep this player.
            placed = engine.adjust_to_owned(cost.recommended_round, owned, DRAFT_ROUNDS)
            if placed is None:
                no_pick = True
                reg_cost = "No pick to keep"
            else:
                reg_cost = f"Round {placed}"
        else:
            reg_cost = "Last rounds"
        if from_rookie:
            keep_year, acq = 1, "rookie→reg"
            eligible = not no_pick
            if no_pick:
                keep_year = "NO PICK"
        elif not cost.eligible:
            keep_year, acq, eligible = "DONE", prof.get("acquired_via"), False
        elif no_pick:
            keep_year, acq, eligible = "NO PICK", prof.get("acquired_via"), False
        else:
            keep_year, acq, eligible = cost.keep_year, prof.get("acquired_via"), True
        rows.append(
            {
                "player_id": pid,
                "Photo": theme.headshot(pid),
                "Player": pm.name,
                "Pos": pm.position,
                "NFL": pm.team,
                "Keep Year": keep_year,
                "Eligible": eligible,
                "Reg. Cost": reg_cost,
                "ADP Rank": int(rank) if rank else None,
                "Orig. Rd": conv_anchor if conv_anchor else (prof.get("original_round") if inherits else None),
                "Acq.": acq,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["Eligible", "ADP Rank"], ascending=[False, True], na_position="last")
    return df.reset_index(drop=True)


def _contract_card_html(row) -> str:
    """One player's keeper economics as a position-accent card — the same
    build_candidate_rows() row Set My Keepers uses, just rendered as a card
    instead of a data_editor row."""
    keep_year = row["Keep Year"]
    keep_year_int = int(keep_year) if isinstance(keep_year, (int, float)) and not isinstance(keep_year, bool) else None
    is_rookie = keep_year == 1 and row["Acq."] == "rookie→reg"
    eligible = bool(row["Eligible"])
    at_wall = eligible and keep_year_int == 3
    tier_cls = ("wall" if at_wall else "" if eligible else "ineligible")
    css_cls = f'ccard pos-{row["Pos"]} {tier_cls}'.strip()

    cost_round = None
    m = re.match(r"Round (\d+)", str(row["Reg. Cost"]))
    if m:
        cost_round = int(m.group(1))
    cost_label = row["Reg. Cost"] if isinstance(row["Reg. Cost"], str) else "—"
    cost_big, cost_small = (f"R{cost_round}", "cost") if cost_round is not None else ("—", cost_label)

    # pandas stores a missing numeric as NaN, not None or falsy — `if row["ADP
    # Rank"]` alone would let a NaN through (bool(nan) is True) and crash
    # adp_rank_to_round's math.ceil(). pd.notna() is the correct guard.
    adp_round = (engine.adp_rank_to_round(row["ADP Rank"], NT)
                 if pd.notna(row["ADP Rank"]) else None)

    pips_n = keep_year_int if keep_year_int is not None else (3 if keep_year == "DONE" else 0)
    pips = "".join(f'<span class="pip{" on" if i < pips_n else ""}"></span>' for i in range(3))

    badges = []
    if is_rookie:
        badges.append('<span class="badge rookie">Rookie Keeper</span>')
    elif keep_year_int is not None:
        badges.append(f'<span class="badge">Year {keep_year_int} of 3</span>')
    if adp_round:
        badges.append(f'<span class="badge">ADP R{adp_round}</span>')
    surplus = keeper_value(row["ADP Rank"], cost_round) if (cost_round is not None and pd.notna(row["ADP Rank"])) else None
    if surplus is not None:
        cls = "surplus-pos" if surplus > 0 else ("surplus-neg" if surplus < 0 else "")
        sign = f"+{surplus}" if surplus > 0 else str(surplus)
        badges.append(f'<span class="badge {cls}">{sign} KEEPER VALUE</span>')

    if not eligible:
        note = ("Not eligible to keep — clock's up or no pick left to use." if keep_year == "DONE"
                else "No pick available at or before this round.")
    elif surplus is not None and surplus >= 25:
        note = "Worth far more than that round's pick would land — a strong keep."
    elif surplus is not None and surplus < 0:
        note = "Underwater vs. ADP — the market's moved past this cost."
    else:
        note = ""

    return (
        f'<div class="{css_cls}">'
        f'<div class="ccard-top">'
        f'<div><h4>{row["Player"]}</h4><div class="pos">{row["Pos"]} · {row["NFL"] or "FA"}</div></div>'
        f'<div class="cost"><b>{cost_big}</b><small>{cost_small}</small></div>'
        f'</div>'
        f'<div class="pips">{pips}</div>'
        f'<div class="badges">{"".join(badges)}</div>'
        + (f'<div class="note">{note}</div>' if note else "")
        + '</div>'
    )


def _contract_cards_grid_html(df: pd.DataFrame) -> str:
    return '<div class="contract-grid">' + "".join(_contract_card_html(r) for _, r in df.iterrows()) + '</div>'


def render_contract_cards(name: str, df: pd.DataFrame, show_title: bool = True) -> None:
    eligible_n = int(df["Eligible"].sum()) if not df.empty else 0
    head = (
        f'<div class="kr-section-head"><h3>Contracts — <span class="g">{name}</span></h3>'
        f'<span class="tag">{eligible_n} eligible</span></div>'
        if show_title else ""
    )
    body = _contract_cards_grid_html(df) if not df.empty else '<p style="color:var(--muted);font-size:13px;">Nothing to show.</p>'
    st.markdown(f'<div class="kr-section">{head}{body}</div>', unsafe_allow_html=True)


def _years_exp(pid: str):
    return (H.players.get(str(pid)) or {}).get("years_exp")


def ever_regular_keeper(pid: str, hist=None) -> bool:
    """True if the player has EVER been kept as a regular (non-rookie) keeper.
    Moving a rookie keeper into a normal keeper slot is permanent — once they've
    been a regular keeper they can never go back to a rookie-keeper spot."""
    hist = hist or H
    pid = str(pid)
    return any(p == pid and (p, s) not in hist.rookie_kept_set for (p, s) in hist.kept_set)


def _rookie_ledger_holds(owner_id: str, pid: str, season: int = SEASON, hist=None) -> bool:
    """This owner kept him as a rookie keeper before AND has held him ever
    since. A rookie keeper who was traded away and later came back is a
    veteran pickup now — neither rookie-eligible nor a rookie->regular
    conversion."""
    hist = hist or H
    prior = list(storage.prior_rookie_seasons(owner_id, pid, season))
    # Asking about NEXT season: this season's rookie keepers count too (they
    # live in this season's saved selections, not the prior-season ledger).
    if season > SEASON and any(str(x.get("player_id")) == str(pid) and x.get("is_rookie_keeper")
                               for x in storage.load(SEASON).get(str(owner_id), [])):
        prior.append(SEASON)
    if not prior:
        return False
    ps = hist.player_seasons.get(str(pid), {})
    return all(not ps.get(y) or str(ps[y].get("owner")) == str(owner_id)
               for y in range(max(prior) + 1, season))


def rookie_keeper_eligible(owner_id: str, pid: str, season: int = SEASON, hist=None) -> bool:
    """A player may be kept as a ROOKIE keeper only if THIS team drafted them in
    the player's rookie season and has held them continuously since. A trade (or
    picking them up as a veteran) breaks rookie-keeper eligibility, and so does
    ever having been moved into a regular keeper slot (the conversion is permanent).
    """
    pid = str(pid)
    # Converted to a regular keeper at some point -> can't return to a rookie slot.
    hist = hist or H
    if ever_regular_keeper(pid, hist):
        return False
    # An established rookie keeper for THIS owner stays eligible (seeded ledger
    # may predate our Sleeper draft window).
    if _rookie_ledger_holds(owner_id, pid, season, hist):
        return True
    ye = _years_exp(pid)
    if ye is None:
        return False
    rookie_season = SEASON - int(ye)
    ps = hist.player_seasons.get(pid, {})
    rec = ps.get(rookie_season)
    # Must be their rookie-season DRAFT pick (not a keeper slot) by THIS owner.
    if not rec or str(rec.get("owner")) != str(owner_id) or rec.get("is_keeper"):
        return False
    # Held continuously since — any season under a different owner = traded.
    for s in range(rookie_season, season):
        r = ps.get(s)
        if r and str(r.get("owner")) != str(owner_id):
            return False
    return True


def rookie_draft_round(pid: str):
    """The round this player was drafted in their rookie year — the cost basis for
    a rookie->regular conversion under `rookie_conversion_cost: original_round`.
    Returns None if it can't be determined from draft history.
    """
    pid = str(pid)
    ps = H.player_seasons.get(pid, {})
    ye = _years_exp(pid)
    if ye is not None:
        rec = ps.get(SEASON - int(ye))
        if rec and not rec.get("is_keeper"):
            return rec.get("round")
    # Fallback: the earliest season we have a (draft) pick on record for them.
    return ps[min(ps)].get("round") if ps else None


@st.cache_data(ttl=3600, show_spinner=False)
def round_replacement_value() -> dict:
    """{round: talent value of the player a pick in that round actually lands
    once keepers are off the board}.

    A keeper league's draft is a depleted pool: an early pick doesn't land an
    early-round talent, it lands whoever's left after every team's keepers.
    Built from the league's REAL keepers (this season's, else the latest
    season that has them) — not a projection, since projected keepers are
    chosen by this value and would be circular. Keepers occupy picks too, so
    each round has fewer free picks than teams; a round is valued at its
    middle free pick.
    """
    from collections import Counter
    kept = {}
    for yr in (SEASON, SEASON - 1, SEASON - 2):
        kept = storage.load(yr)
        if any(kept.values()):
            break
    kept_names, per_round = set(), Counter()
    for picks in kept.values():
        for x in picks:
            if x.get("player_name"):
                kept_names.add(normalize_name(x["player_name"]))
            cr = x.get("cost_round")
            if str(cr).isdigit():
                per_round[int(cr)] += 1
    ranks = sorted(int(r["consensus_rank"]) for _, r in ADP_DF.iterrows()
                   if r.get("position") in ("QB", "RB", "WR", "TE") and not pd.isna(r.get("consensus_rank"))
                   and normalize_name(r["name"]) not in kept_names)
    out, cum = {}, 0
    for rnd in range(1, DRAFT_ROUNDS + 1):
        free = max(1, NT - per_round[rnd])
        i = min(int(cum + free / 2), len(ranks) - 1) if ranks else 0
        out[rnd] = _draft_value(ranks[i]) if ranks else _draft_value((rnd - 1) * NT + NT // 2)
        cum += free
    return out


def keeper_value(adp_rank, cost_round) -> int | None:
    """What keeping a player is worth: his talent (the draft-value curve at his
    ADP, pick #1 ≈ 100) minus the talent that same round's pick would actually
    land in our keeper-depleted draft (round_replacement_value). Credits an
    elite player kept early — the old "cost round minus ADP round" scored a
    1st-round star kept in the 1st as +0 — as well as the cheap late keeper.
    """
    if adp_rank is None or cost_round is None or pd.isna(adp_rank):
        return None
    return int(_draft_value(int(adp_rank)) - round_replacement_value().get(int(cost_round), 1))


def build_value_leaderboard(top_n: int = 50, hide_rookie_keepers: bool = False) -> pd.DataFrame:
    """Best keeper bargains across every roster.

    Value = keeper_value(): his talent minus what that round's pick would
    actually land in our keeper-depleted draft. (Was: cost round minus ADP
    round, i.e. how many rounds of draft
    capital you'd gain by keeping the player versus drafting them at market.
    The "Kept" column flags players a manager has already declared as a keeper.
    Real NFL rookies (years_exp == 0) are excluded — they live on the Rookies tab.
    """
    # Players already declared as keepers (match by Sleeper id and by name).
    submitted = submitted_keepers()
    kept_ids, kept_names = set(), set()
    for picks in submitted.values():
        for s in picks:
            if s.get("player_id"):
                kept_ids.add(str(s["player_id"]))
            if s.get("player_name"):
                kept_names.add(normalize_name(s["player_name"]))

    # (owner, player) pairs previously kept as a rookie keeper -> last-round cost.
    rookie_hist = set()
    for yr in range(SEASON - 1, SEASON - 7, -1):
        for oid, picks in storage.load(yr).items():
            for s in picks:
                if s.get("is_rookie_keeper") and s.get("player_id"):
                    rookie_hist.add((str(oid), str(s["player_id"])))

    rows = []
    for owner_id, pids in CANDS.items():
        mgr = config.manager_name(owner_id)
        for pid in pids:
            pm = H.player_meta(pid)
            if pm.position not in ("QB", "RB", "WR", "TE"):
                continue
            if _years_exp(pid) == 0:
                continue  # real NFL rookie -> Rookies tab
            rank = adp_rank_for(pm.name, pm.position)
            if not rank:
                continue
            prof = H.keeper_profile(owner_id, pid, SEASON)
            cost = engine.compute(prof, adp_rank=rank, is_rookie_keeper=False)
            # Current rookie keeper = still rookie-eligible (drafted by this team as
            # a rookie, held since, never converted to a regular). Using eligibility
            # rather than just the prior-rookie history INCLUDES first-time rookie
            # keepers (e.g. a 2nd-year stud kept for the first time) that were
            # otherwise mis-costed as regular keepers and dropped from the board.
            from_rookie = rookie_keeper_eligible(owner_id, str(pid))
            if from_rookie and hide_rookie_keepers:
                continue
            if from_rookie:
                # On the value board a rookie keeper is shown at their rookie-keeper
                # cost (a last-round pick) — the cheap, career-long way they'd be
                # kept. (Converting to a regular slot costs their original draft
                # round and starts the clock, a deliberate downgrade handled in
                # "Set my keepers", not the bargain board.)
                cost_round, keep_yr = DRAFT_ROUNDS, 1
            else:
                if not cost.eligible:
                    continue  # already kept 3 years
                inherits = prof.get("acquired_via") in ("draft", "trade") and prof.get("original_round")
                if inherits:
                    # Must own a pick at the cost round or earlier (a higher pick);
                    # otherwise the team can't keep this player at all -> not a
                    # keeper option, so drop them from the value board.
                    cost_round = engine.adjust_to_owned(
                        cost.recommended_round, owned_for(owner_id), DRAFT_ROUNDS)
                else:
                    cost_round = DRAFT_ROUNDS
                keep_yr = cost.keep_year
            if not cost_round:
                continue  # ineligible (no high-enough pick) or no round resolved
            adp_round = engine.adp_rank_to_round(rank, NT)
            is_kept = str(pid) in kept_ids or normalize_name(pm.name) in kept_names
            rows.append(
                {
                    "_pid": str(pid),
                    "Player": pm.name, "Pos": pm.position, "Team": mgr,
                    "Kept": is_kept, "Rookie": from_rookie, "FA": False,
                    "Keep Yr": keep_yr, "Cost Rd": cost_round,
                    "ADP": int(rank), "ADP Rd": adp_round,
                    "Value": keeper_value(rank, cost_round),
                }
            )

    # Free agents: ADP-ranked skill players not on any 2026 roster. If kept they'd
    # cost a last-round pick (the undrafted rule), so value = last round - ADP round.
    rostered_pids = {str(p) for ps in CANDS.values() for p in ps}
    rostered_names = {normalize_name(H.player_meta(p).name) for ps in CANDS.values() for p in ps}
    name_idx = get_name_index()
    for _, ar in ADP_DF.iterrows():
        pos = ar.get("position")
        rank = ar.get("consensus_rank")
        if pos not in ("QB", "RB", "WR", "TE") or pd.isna(rank):
            continue
        nm = normalize_name(ar["name"])
        fa_pid = name_idx.get(nm, "")
        if not fa_pid or fa_pid in rostered_pids or nm in rostered_names:
            continue  # unresolved (likely incoming rookie) or already on a roster
        if _years_exp(fa_pid) == 0:
            continue  # real NFL rookie -> Rookies tab
        # Drafted-then-dropped players keep at their drafted round; only the truly
        # undrafted keep at a last-round pick.
        ps = H.player_seasons.get(str(fa_pid), {})
        fa_cost = ps[max(ps)]["round"] if ps else DRAFT_ROUNDS
        adp_round = engine.adp_rank_to_round(rank, NT)
        rows.append(
            {
                "_pid": fa_pid or "0",
                "Player": ar["name"], "Pos": pos, "Team": "Free Agent",
                "Kept": False, "Rookie": False, "FA": True,
                "Keep Yr": 1, "Cost Rd": fa_cost,
                "ADP": int(rank), "ADP Rd": adp_round,
                "Value": keeper_value(rank, fa_cost),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("Value", ascending=False).head(top_n).reset_index(drop=True)
    df.insert(0, "#", range(1, len(df) + 1))
    return df


def build_trade_targets() -> pd.DataFrame:
    """Every rostered keeper's cost round — the round that carries over to a new
    team on a trade. Lets you scout, for a round you'd keep someone at, which
    players across the league you could deal for.
    """
    # (owner, player) pairs currently IN rookie-keeper status (not yet converted).
    rookie_hist = set()
    for yr in range(SEASON - 1, SEASON - 7, -1):
        for oid, picks in storage.load(yr).items():
            for s in picks:
                if s.get("is_rookie_keeper") and s.get("player_id"):
                    rookie_hist.add((str(oid), str(s["player_id"])))

    rows = []
    for owner_id, pids in CANDS.items():
        mgr = config.manager_name(owner_id)
        for pid in pids:
            pm = H.player_meta(pid)
            if pm.position not in ("QB", "RB", "WR", "TE"):
                continue
            if _years_exp(pid) == 0:
                continue  # real NFL rookie -> Rookies tab
            rank = adp_rank_for(pm.name, pm.position)
            if not rank:
                continue
            from_rookie = ((str(owner_id), str(pid)) in rookie_hist
                           and not ever_regular_keeper(pid))
            if from_rookie:
                # On a trade a rookie keeper converts to a regular keeper (the new
                # owner didn't draft them as a rookie), costing the round they were
                # originally drafted as a rookie — this league's conversion rule —
                # with the 3-year clock starting at Year 1. allow_adp_discount still
                # applies: a later (cheaper) ADP round wins over the rookie round.
                rdr = rookie_draft_round(pid)
                if rdr:
                    prof = H.keeper_profile(owner_id, pid, SEASON)
                    conv_prof = {**prof, "next_keep_year": 1, "consecutive_keeper_years": 0,
                                 "acquired_via": "draft", "original_round": rdr}
                    conv_cost = engine.compute(conv_prof, adp_rank=rank, is_rookie_keeper=False)
                    cost_round = conv_cost.recommended_round or rdr
                else:
                    cost_round = DRAFT_ROUNDS
                keep_yr = 1
            else:
                prof = H.keeper_profile(owner_id, pid, SEASON)
                cost = engine.compute(prof, adp_rank=rank, is_rookie_keeper=False)
                if not cost.eligible:
                    continue  # already kept the max years
                inherits = prof.get("acquired_via") in ("draft", "trade") and prof.get("original_round")
                # The keeper's natural round carries on a trade; undrafted/waiver
                # pickups would slot at a last-round pick for the new owner.
                cost_round = cost.recommended_round if inherits else DRAFT_ROUNDS
                keep_yr = cost.keep_year if inherits else 1
            if not cost_round:
                continue
            adp_round = engine.adp_rank_to_round(rank, NT)
            rows.append({
                "_pid": str(pid), "Player": pm.name, "Pos": pm.position,
                "Owner": mgr, "Keep Yr": keep_yr, "Rookie": from_rookie,
                "Cost Rd": int(cost_round), "ADP": int(rank), "ADP Rd": adp_round,
                "Value": keeper_value(rank, cost_round),
            })
    return pd.DataFrame(rows)


@st.cache_data(ttl=86400, show_spinner=False)
def position_keeper_caps() -> dict:
    """Max keepers a team would realistically hold at a position, from the league's
    starting lineup (you don't keep two QBs/TEs when you only start one). Positions
    not listed are uncapped (RB/WR fill flex)."""
    from collections import Counter
    from kreeper import sleeper
    rp = sleeper.get_league(LEAGUE["sleeper_league_id"]).get("roster_positions", [])
    c = Counter(rp)
    return {"QB": c.get("QB", 0) + c.get("SUPER_FLEX", 0) or 1,
            "TE": c.get("TE", 0) or 1}


def _select_keepers(team_lb, cap, pos_cap, seed_positions=None,
                    max_rookie=None, max_reg=None):
    """Pick a team's realistic keeper set: top by value, but respecting the
    league's keeper rules — at most `max_rookie` ROOKIE keepers and `max_reg`
    REGULAR keepers (defaults to the league's MAX_ROOKIE / MAX_REG), and no more
    than the positional cap at QB/TE. A rookie keeper is cheap (last-round cost),
    so without the separate rookie cap a team would over-fill rookie slots and
    starve its regular keepers. Returns a list of leaderboard rows."""
    from collections import Counter
    if max_rookie is None:
        max_rookie = MAX_ROOKIE
    if max_reg is None:
        max_reg = MAX_REG
    pcount = Counter(seed_positions or [])
    chosen, n_rook, n_reg = [], 0, 0
    for _, r in team_lb.sort_values("Value", ascending=False).iterrows():
        if len(chosen) >= cap:
            break
        is_rk = bool(r.get("Rookie"))
        if is_rk and n_rook >= max_rookie:
            continue  # rookie-keeper slots full
        if not is_rk and n_reg >= max_reg:
            continue  # regular-keeper slots full
        limit = pos_cap.get(r["Pos"])
        if limit is not None and pcount[r["Pos"]] >= limit:
            continue  # already keeping the max QBs/TEs
        chosen.append(r)
        pcount[r["Pos"]] += 1
        if is_rk:
            n_rook += 1
        else:
            n_reg += 1
    return chosen


@st.cache_data(ttl=300, show_spinner=False)
def draft_keepers() -> dict:
    """The keepers as they stood AT THE DRAFT, once it has run: every
    submitted keeper, by the team that kept him — including players traded
    or dropped since (Achane, Dart, Pacheco in 2026). Before the draft it's
    submitted_keepers(), where a keeper traded away no longer counts for the
    team that gave him up."""
    return storage.load(SEASON) if current_draft_done() else submitted_keepers()


def _projected_kept_ids() -> set:
    """player_ids likely off the draft board: everyone declared as a keeper, plus
    each team's most valuable eligible keepers (respecting roster + positional
    limits — no team keeps two QBs or two TEs)."""
    declared_pos = {}   # owner -> [positions already declared]
    kept = set()
    for oid, picks in submitted_keepers().items():
        for s in picks:
            if s.get("player_id"):
                kept.add(str(s["player_id"]))
                declared_pos.setdefault(str(oid), []).append(s.get("position"))
    lb = build_value_leaderboard(400)
    cap = MAX_REG + MAX_ROOKIE
    pos_cap = position_keeper_caps()
    for o in MANAGERS:
        seeded = declared_pos.get(str(o), [])
        team = lb[(lb["Team"] == config.manager_name(o)) & (~lb["_pid"].astype(str).isin(kept))]
        for r in _select_keepers(team, cap - len(seeded), pos_cap, seeded):
            kept.add(str(r["_pid"]))
    return kept


def starter_slots() -> list:
    """Ordered starting-lineup slots from the league settings (no bench/IR)."""
    from kreeper import sleeper
    rp = sleeper.get_league(LEAGUE["sleeper_league_id"]).get("roster_positions", [])
    starters = [p for p in rp if p not in ("BN", "IR", "TAXI")]
    return starters or ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "FLEX"]


def team_keeper_rows(owner_id) -> list:
    """A team's keeper set. Once submissions are locked, this is exactly
    what's declared — no filling remaining slots with a value-based guess,
    since there's nothing left to decide. Before the deadline it's declared
    + best-by-value fill, so the site can preview a likely keeper set while
    picks are still open."""
    lb = build_value_leaderboard(400)
    declared = manager_submitted(owner_id)
    seeded = [s.get("position") for s in declared]
    declared_ids = {str(s["player_id"]) for s in declared}
    dec_rk = sum(1 for s in declared if s.get("is_rookie_keeper"))
    # For a player a manager has DECLARED, trust the declared type — keeping a
    # rookie-eligible player in a regular slot is a valid choice the value board's
    # eligibility flag would otherwise override.
    dec_type = {str(s["player_id"]): bool(s.get("is_rookie_keeper")) for s in declared}
    team = lb[lb["Team"] == config.manager_name(owner_id)]
    out = []
    for r in team[team["_pid"].astype(str).isin(declared_ids)].to_dict("records"):
        r["Rookie"] = dec_type.get(str(r["_pid"]), r.get("Rookie"))
        out.append(r)

    _, locked = keeper_lock()
    if locked:
        return out

    dec_reg = len(declared) - dec_rk
    cap = MAX_REG + MAX_ROOKIE
    rest = team[~team["_pid"].astype(str).isin(declared_ids)]
    out += [dict(r) for r in _select_keepers(
        rest, cap - len(declared), position_keeper_caps(), seeded,
        max_rookie=MAX_ROOKIE - dec_rk, max_reg=MAX_REG - dec_reg)]
    return out


def build_rookies_table(top_n: int = 40) -> pd.DataFrame:
    """This year's NFL rookies (years_exp == 0) ranked by consensus ADP."""
    name_idx = get_name_index()
    rows = []
    for _, ar in ADP_DF.iterrows():
        pos, rank = ar.get("position"), ar.get("consensus_rank")
        if pos not in ("QB", "RB", "WR", "TE") or pd.isna(rank):
            continue
        pid = name_idx.get(normalize_name(ar["name"]), "")
        if not pid or _years_exp(pid) != 0:
            continue
        p = H.players.get(pid, {}) or {}
        cadp = ar.get("consensus_adp")
        rows.append(
            {
                "_pid": pid, "Player": ar["name"], "Pos": pos,
                "NFL": p.get("team") or "FA", "ADP": int(rank),
                "Consensus ADP": None if pd.isna(cadp) else round(float(cadp), 1),
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.sort_values("ADP").head(top_n).reset_index(drop=True)
    df.insert(0, "#", range(1, len(df) + 1))
    return df


# --------------------------------------------------------------------- pages
def _leaderboard_html(df) -> str:
    rows = []
    for _, r in df.iterrows():
        kept = bool(r["Kept"])
        is_fa = bool(r.get("FA"))
        cls = ' class="kept"' if kept else (' class="fa"' if is_fa else "")
        badge = '<span class="kept-badge">kept</span>' if kept else ""
        rk_badge = '<span class="rk-badge" title="rookie keeper">RK</span>' if r.get("Rookie") else ""
        v = int(r["Value"])
        vtxt = f"+{v}" if v >= 0 else str(v)
        team = '<span class="fa-tag">Free Agent</span>' if is_fa else r["Team"]
        rows.append(
            f'<tr{cls}><td class="rk">{r["#"]}</td>'
            f'<td class="pl">{theme.img_tag(r["_pid"])}{r["Player"]} {badge}{rk_badge}</td>'
            f'<td class="pos"><span class="posdot p-{r["Pos"]}"></span>{r["Pos"]}</td>'
            f'<td>{team}</td>'
            f'<td class="num">{r["Keep Yr"]}</td>'
            f'<td class="num">R{r["Cost Rd"]}</td>'
            f'<td class="num">{r["ADP"]}</td>'
            f'<td class="val">{vtxt}</td></tr>'
        )
    head = ('<tr><th>#</th><th>Player</th><th>Pos</th><th>Team</th>'
            '<th>Keep&nbsp;Yr</th><th>Cost</th><th>ADP</th><th>Value</th></tr>')
    return ('<div class="neonwrap" style="max-height:660px;overflow:auto;">'
            '<table class="lb lb-value"><thead>' + head + '</thead><tbody>'
            + "".join(rows) + '</tbody></table></div>')


def _biggest_adp_mover(top_n: int = 50, window_days: int = 30):
    """The single largest ADP-rank move among currently top-`top_n` players
    over the last `window_days`, or None if there's not enough history yet."""
    mv = adp_consensus.adp_movement(SEASON, window_days=window_days)
    moves = [m for m in mv.get("moves", []) if abs(m["delta"]) >= 1 and m["now"] <= top_n]
    if not moves:
        return None
    return max(moves, key=lambda m: abs(m["delta"]))


def render_home_glance() -> None:
    """Quick-glance liquid-fill stats: this year's title favorite and the
    biggest ADP mover inside the realistic draft pool."""
    stats = []

    try:
        odds = build_championship_odds()
    except Exception:  # noqa: BLE001
        odds = []
    if odds:
        top = odds[0]
        stats.append(theme.liquid_stat_html(
            top["Win %"] / 100, f'{top["Win %"]:g}%', "Win",
            "Title Favorite", top["Team"],
        ))

    mover = _biggest_adp_mover()
    if mover:
        arrow = "▲" if mover["delta"] > 0 else "▼"
        stats.append(theme.liquid_stat_html(
            0.65, f'{arrow}{abs(mover["delta"])}', f'#{mover["now"]}',
            "Biggest ADP Move", f'{mover["name"]} ({mover["pos"]})',
            accent=theme.GOLD_D if mover["delta"] > 0 else theme.RED,
        ))

    if not stats:
        return
    st.markdown(
        '<div class="glance"><div class="glance-stats">' + "".join(stats) + '</div></div>',
        unsafe_allow_html=True,
    )


def render_keeper_value_board() -> None:
    """Top keeper bargains league-wide, plus the CSV export and the
    shared-URL submission audit trail — split off Home into its own page
    (Pre-Season > Keepers > Keeper Value Board) so Home can stay focused on
    whatever's actually useful right now (see render_home)."""
    st.markdown('<h2 class="two-tone">Top 50 <span class="g">Keeper Values</span></h2>', unsafe_allow_html=True)
    st.caption("Best keeper bargains across every roster — draft value gained by keeping a "
               "player: his talent minus what his cost round's pick would actually land once keepers "
               "are off the board, so elite players kept early count too. Green = declared keeper · "
               "purple RK = rookie keeper · cyan = free agent. Real NFL rookies are on the ADP tab.")
    fc1, fc2, fc3 = st.columns([1, 1, 1])
    with fc1:
        pos_f = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"], key="lb_pos")
    with fc2:
        team_f = st.selectbox("Team", ["All teams"] + [m["name"] for m in MANAGERS.values()] + ["Free Agent"], key="lb_team")
    with fc3:
        hide_rk = st.toggle("Hide rookie keepers", value=False,
                            help="Filter out players currently in rookie-keeper status.")
    lb = build_value_leaderboard(400, hide_rookie_keepers=hide_rk)
    if not lb.empty:
        if pos_f != "All":
            lb = lb[lb["Pos"] == pos_f]
        if team_f != "All teams":
            lb = lb[lb["Team"] == team_f]
        lb = lb.head(50).reset_index(drop=True)
        lb["#"] = range(1, len(lb) + 1)
    if lb.empty:
        st.info("No players match those filters (or no ADP data yet).")
    else:
        st.markdown(_leaderboard_html(lb), unsafe_allow_html=True)

    # Export — grab every submitted keeper to paste into the year-to-year sheet.
    data = submitted_keepers()
    if any(data.values()):
        export = []
        for oid, m in MANAGERS.items():
            for s in sorted(data.get(oid, []), key=lambda x: (x.get("cost_round") or 99)):
                export.append({
                    "Team": m["name"], "Player": s.get("player_name"), "Pos": s.get("position"),
                    "Type": "Rookie" if s.get("is_rookie_keeper") else "Regular",
                    "Keep Year": s.get("keep_year"), "Round": s.get("cost_round"),
                })
        st.download_button(
            "Download all keepers (CSV)",
            pd.DataFrame(export).to_csv(index=False),
            file_name=f"kreeper_keepers_{SEASON}.csv", mime="text/csv",
        )

    # Recent updates — who changed their keepers and when (shared-URL audit trail).
    st.markdown('<h3 class="two-tone">Recent <span class="g">Updates</span></h3>', unsafe_allow_html=True)
    deadline, locked = keeper_lock()
    if deadline:
        st.caption((f"Submissions closed {deadline:%b %d, %Y · %-I:%M %p}."
                    if locked else
                    f"Submissions close {deadline:%b %d, %Y · %-I:%M %p}."))
    log = storage.load_log(SEASON)
    if not log:
        st.caption("No keeper updates yet.")
    else:
        lines = []
        for e in reversed(log[-12:]):
            n = int(e.get("count", 0) or 0)
            who = e.get("name") or config.manager_name(e.get("owner", ""))
            lines.append(f"- **{who}** → {n} keeper{'' if n == 1 else 's'} · {_fmt_ts(e.get('ts', ''))}")
        st.markdown("\n".join(lines))


def _glance_box(tiles: list) -> None:
    """A gradient-bordered headline strip of liquid-fill stat rings — same
    box as Home's FAAB Pot / Title Favorite, reused for a page's top-line
    stats. `tiles` is [(pct, value_html, ring_label, label, sub, accent), ...]."""
    stats = "".join(
        theme.liquid_stat_html(pct, value, ring_label, label, sub, accent=accent)
        for pct, value, ring_label, label, sub, accent in tiles
    )
    st.markdown(
        f'<div class="glance-panel"><div class="glance-panel-in">'
        f'<div class="liquid-stats">{stats}</div></div></div>',
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=600, show_spinner=False)
def get_standings():
    return season.standings()


@st.cache_data(ttl=600, show_spinner=False)
def get_season_results():
    return season.season_results()


@st.cache_data(ttl=600, show_spinner=False)
def get_power_rankings():
    return season.power_rankings()


@st.cache_data(ttl=600, show_spinner=False)
def get_luck():
    return season.luck()


@st.cache_data(ttl=900, show_spinner="Simulating the rest of the season…")
def get_playoff_odds():
    return season.playoff_odds(playoff_teams=PLAYOFF_TEAMS)


def _no_season_yet(what: str) -> bool:
    """Shared empty state for every results-driven page. True (and renders a
    note) when no regular-season game has been played yet — these pages are
    all honest about having nothing to say rather than showing a table of
    zeroes that looks like real standings."""
    table = get_standings()
    if any(r["weeks_played"] for r in table):
        return False
    st.info(f"🏈 {what} shows up here once Week 1 is in the books.")
    return True


def render_standings() -> None:
    st.markdown(theme.section_head('Standings &amp; <span class="g">Scoreboard</span>',
                                    f'top {PLAYOFF_TEAMS} make the bracket', page=True), unsafe_allow_html=True)
    st.caption("Live from real weekly results. Sorted by record, then points for — "
               "the same tiebreak Sleeper uses.")
    if _no_season_yet("The standings table"):
        return

    table = get_standings()
    played = max(r["weeks_played"] for r in table)
    total = season.regular_season_weeks()
    leader = table[0]
    top_scorer = max(table, key=lambda r: r["points_for"])
    _glance_box([
        (played / max(1, total), f"{played}", "of " + str(total), "Weeks Played",
         f"{total - played} to play", theme.PURPLE),
        (1.0, f'{leader["wins"]}-{leader["losses"]}', "rec", "First Place",
         config.manager_name(leader["owner"]), theme.TEAL),
        (1.0, f'{top_scorer["points_for"]:.0f}', "pf", "Most Points",
         config.manager_name(top_scorer["owner"]), theme.AMBER),
    ])

    body = []
    for r in table:
        rec = f'{r["wins"]}-{r["losses"]}' + (f'-{r["ties"]}' if r["ties"] else "")
        cut = " playoff-cut" if r["rank"] == PLAYOFF_TEAMS else ""
        badge = ('<span class="kept-badge">IN</span>' if r["rank"] <= PLAYOFF_TEAMS else "")
        streak = r["streak"]
        scolor = ("var(--teal)" if streak.startswith("W")
                  else "var(--red)" if streak.startswith("L") else "var(--muted)")
        body.append(
            f'<tr class="{cut.strip()}"><td class="rk">{r["rank"]}</td>'
            f'<td class="pl">{config.manager_name(r["owner"])} {badge}</td>'
            f'<td class="num" style="font-family:var(--font-display);font-weight:600;font-size:15px;">{rec}</td>'
            f'<td class="num">{r["points_for"]:.1f}</td>'
            f'<td class="num">{r["points_against"]:.1f}</td>'
            f'<td class="num" style="color:{scolor};font-weight:700;">{streak}</td></tr>'
        )
    st.markdown(
        '<div class="neonwrap"><table class="lb"><thead><tr>'
        '<th>#</th><th>Team</th><th>Record</th><th>PF</th><th>PA</th><th>Streak</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"Top {PLAYOFF_TEAMS} make the championship bracket — the line sits under "
               f"#{PLAYOFF_TEAMS}. Everyone below plays the consolation bracket.")

    st.markdown(theme.section_head('Weekly Scoreboard', 'pick a week'), unsafe_allow_html=True)
    results = get_season_results()
    if not results:
        return
    weeks = sorted(results, reverse=True)
    pick = st.selectbox("Week", weeks, format_func=lambda w: f"Week {w}",
                        label_visibility="collapsed")
    cards = []
    for g in results[pick]:
        for side, opp in ((g["home"], g["away"]), (g["away"], g["home"])):
            side["_won"] = (not g["tie"]) and g["winner"] == side["owner"]
        rows = "".join(
            f'<div class="mu-row{" win" if s["_won"] else ""}">'
            f'<span class="mu-team">{config.manager_name(s["owner"])}</span>'
            f'<span class="mu-pts">{s["points"]:.1f}</span></div>'
            for s in (g["home"], g["away"])
        )
        note = "TIE" if g["tie"] else f'by {g["margin"]:.1f}'
        cards.append(f'<div class="matchup">{rows}<div class="mu-note">{note}</div></div>')
    st.markdown('<div class="matchups">' + "".join(cards) + '</div>', unsafe_allow_html=True)


def render_power() -> None:
    st.markdown(theme.section_head('Power <span class="g">Rankings</span>',
                                    'record &middot; scoring &middot; form', page=True), unsafe_allow_html=True)
    st.caption("Driven by what's actually happened: 45% win rate, 35% scoring, 20% recent form. "
               "Separate from Title Odds, which is a pre-season keeper-strength model.")
    if _no_season_yet("Power rankings"):
        return

    ranks = get_power_rankings()
    risers = [r for r in ranks if r["rank_delta"] > 0]
    best_riser = max(risers, key=lambda r: r["rank_delta"], default=None)
    hottest = max(ranks, key=lambda r: r["recent_avg"], default=None)
    tiles = [(1.0, f'#{ranks[0]["rank"]}', "power", "Strongest Team",
              config.manager_name(ranks[0]["owner"]), theme.TEAL)]
    if hottest:
        tiles.append((1.0, f'{hottest["recent_avg"]:.0f}', "avg", "Hottest (last 3)",
                      config.manager_name(hottest["owner"]), theme.AMBER))
    if best_riser:
        tiles.append((1.0, f'+{best_riser["rank_delta"]}', "spots", "Most Underrated",
                      f'{config.manager_name(best_riser["owner"])} · standings say '
                      f'#{best_riser["rank"] + best_riser["rank_delta"]}', theme.PURPLE))
    _glance_box(tiles)

    body = []
    for r in ranks:
        d = r["rank_delta"]
        arrow = (f'<span class="pr-up">&#9650; {d}</span>' if d > 0
                 else f'<span class="pr-down">&#9660; {abs(d)}</span>' if d < 0
                 else '<span class="pr-flat">&ndash;</span>')
        body.append(
            f'<tr><td class="rk">{r["rank"]}</td>'
            f'<td class="pl">{config.manager_name(r["owner"])}</td>'
            f'<td class="num" style="font-family:var(--font-display);font-weight:600;color:var(--accent);">{r["score"]}</td>'
            f'<td class="num">{r["win_pct"] * 100:.0f}%</td>'
            f'<td class="num">{r["points_for"]:.1f}</td>'
            f'<td class="num">{r["recent_avg"]:.1f}</td>'
            f'<td class="num">{arrow}</td></tr>'
        )
    st.markdown(
        '<div class="neonwrap"><table class="lb"><thead><tr>'
        '<th>#</th><th>Team</th><th>Power</th><th>Win%</th><th>PF</th>'
        '<th>Last 3</th><th>vs. Standings</th>'
        f'</tr></thead><tbody>{"".join(body)}</tbody></table></div>',
        unsafe_allow_html=True,
    )
    st.caption("“vs. Standings” compares power rank to where the record has them — "
               "green means the record undersells them.")

    st.markdown(theme.section_head('Playoff Odds', '10,000 simulations'), unsafe_allow_html=True)
    st.caption(f"10,000 simulations of every remaining game, drawn from each team's own "
               f"scoring average and volatility. Top {PLAYOFF_TEAMS} make it.")
    odds = get_playoff_odds()
    if odds:
        obody = []
        for r in odds:
            pct = r["odds"]
            color = ("var(--teal)" if pct >= 75 else "var(--amber)" if pct >= 25 else "var(--red)")
            obody.append(
                f'<tr><td class="pl">{config.manager_name(r["owner"])}</td>'
                f'<td class="num" style="font-family:var(--font-display);font-weight:600;font-size:16px;color:{color};">{pct:.0f}%</td>'
                f'<td class="num">{r["current_wins"]}</td>'
                f'<td class="num">{r["proj_wins"]:.1f}</td>'
                f'<td style="min-width:120px;"><div class="burnbar-track">'
                f'<div class="burnbar-fill" style="width:{pct:.0f}%;background:{color};"></div>'
                f'</div></td></tr>'
            )
        st.markdown(
            '<div class="neonwrap"><table class="lb"><thead><tr>'
            '<th>Team</th><th>Playoff Odds</th><th>Wins Now</th><th>Proj. Wins</th><th></th>'
            f'</tr></thead><tbody>{"".join(obody)}</tbody></table></div>',
            unsafe_allow_html=True,
        )

    st.markdown(theme.section_head('Luck', 'expected vs. actual wins'), unsafe_allow_html=True)
    st.caption("Expected wins = what your scores would've earned against the whole league "
               "each week. Positive luck means the schedule has been kind.")
    rows = sorted(get_luck(), key=lambda r: -r["luck"])
    lbody = "".join(
        f'<tr><td class="pl">{config.manager_name(r["owner"])}</td>'
        f'<td class="num">{r["wins"]}</td>'
        f'<td class="num">{r["expected_wins"]:.2f}</td>'
        f'<td class="num" style="font-weight:700;color:'
        f'{"var(--teal)" if r["luck"] > 0 else "var(--red)" if r["luck"] < 0 else "var(--muted)"};">'
        f'{r["luck"]:+.2f}</td></tr>'
        for r in rows
    )
    st.markdown(
        '<div class="neonwrap"><table class="lb"><thead><tr>'
        '<th>Team</th><th>Actual W</th><th>Expected W</th><th>Luck</th>'
        f'</tr></thead><tbody>{lbody}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def _payout_row(label: str, who: str, amount, sub: str, accent: str) -> str:
    money = f"${amount:,.0f}" if isinstance(amount, (int, float)) else amount
    return (f'<div class="payout-row"><div class="po-amt" style="color:{accent};">{money}</div>'
            f'<div class="po-txt"><div class="po-lbl">{label}</div>'
            f'<div class="po-who">{who}</div><div class="po-sub">{sub}</div></div></div>')



_PHASE_ORDER = ["keepers_open", "pre_draft", "pre_season", "in_season", "offseason"]


def _current_phase() -> str:
    """The phase driving Home + the top-bar chip."""
    try:
        return phase.current_phase()
    except Exception:  # noqa: BLE001 — a flaky Sleeper call shouldn't crash Home
        return "keepers_open"


def _phase_label_sub(current: str) -> tuple:
    """(label, sub) for a phase, shown in the top-bar status line."""
    deadline = config.keeper_deadline()
    info = {
        "keepers_open": ("Keepers Open", f"Due {deadline.strftime('%b %-d')}" if deadline else ""),
        "pre_draft": ("Draft Prep", phase.draft_date_label()),
        "pre_season": ("Pre-Season", ""),
        "in_season": ("In-Season", ""),
        "offseason": ("Offseason", ""),
    }
    return info.get(current, ("Draft Prep", ""))


def _status_line_html(current: str) -> str:
    """A thin one-line phase indicator under the wordmark in the top bar,
    persistent on every page (replaces the old corner liquid-ring chip)."""
    label, sub = _phase_label_sub(current)
    sub_html = f' <span class="muted">&middot; {sub}</span>' if sub else ""
    return f'<div class="status-line"><span class="dot"></span>{label.upper()}{sub_html}</div>'


def render_home() -> None:
    """Home leads with whatever's actually useful right now — keeper
    decisions while they're still open, draft prep once they're locked, the
    draft recap once it wraps, and title odds once the season's live. See
    kreeper/phase.py for how the phase is inferred. The top-bar masthead
    (kbar) already carries the branding and phase status, so Home goes
    straight into content."""
    ph = _current_phase()
    if ph == "pre_draft":
        _render_home_pre_draft()
    elif ph == "pre_season":
        _render_home_pre_season()
    elif ph == "in_season":
        _render_home_in_season()
    elif ph == "offseason":
        _render_home_offseason()
    else:
        _render_home_keepers_open()


def _render_home_keepers_open() -> None:
    render_countdown()
    render_home_glance()
    render_keeper_value_board()


def _render_home_pre_draft() -> None:
    render_home_glance()
    render_draft_capital()


def _render_home_pre_season() -> None:
    st.markdown('<h2 class="two-tone">The <span class="g">Draft</span></h2>', unsafe_allow_html=True)
    st.caption("It's in the books — here's how it landed.")
    render_draft_board()
    render_odds()


def _team_of(owner: str) -> str:
    """The manager's team name, falling back to their own name so a row never
    renders blank for someone who never named a team."""
    m = MANAGERS.get(str(owner)) or {}
    return m.get("team") or config.manager_name(owner)


def _two_cell(owner: str, win: bool = False) -> str:
    """Two-line table cell: team name on top, the human under it. Used
    everywhere on Home so a row identifies a team the way people actually
    talk about it, without losing who's behind it."""
    return (f'<td class="two{" w" if win else ""}"><b>{_team_of(owner)}</b>'
            f'<span>{config.manager_name(owner)}</span></td>')


@st.cache_data(ttl=900, show_spinner=False)
def get_recent_moves():
    return season.recent_moves(limit=8)


def _move_player_html(pid: str) -> str:
    p = sleeper.get_players().get(str(pid)) or {}
    nm = p.get("full_name") or p.get("last_name") or str(pid)
    pos = p.get("position") or ""
    return f'{nm}<span class="pos">{pos}</span>' if pos else nm


# ------------------------------------------------------------------ this week
# The Draft Room's weekly screens, rebuilt for Kreeper: a live matchup card,
# lineup advice, every matchup slot by slot. These are the only pages that
# know whose phone they're on — see _me(). Everything league-wide stays
# league-wide.
_START_CHIP = '<span class="chip good">start</span>'
_POSC = {"QB": "#a2447f", "RB": "#1f8a5b", "WR": "#2563b5", "TE": "#b07400", "K": "#6b6580", "DEF": "#4b5a73"}


def _me():
    """The manager this device belongs to, or None.

    Carried in the URL as `me=<owner_id>`. The browser remembers it in
    localStorage and the nav script (render_bottom_bar) puts it back on every
    in-app link, and on a bare URL or bookmark reloads once with it added. A
    cookie would be simpler but Streamlit Cloud's proxy doesn't pass app
    cookies through to st.context — it worked locally and forgot the team on
    every page change in production. No passwords: it only decides whose
    matchup leads, and anyone can switch from the masthead dropdown."""
    q = st.query_params.get("me")
    if q in MANAGERS:
        st.session_state["me"] = q
        return q
    s = st.session_state.get("me")
    return s if s in MANAGERS else None


def _href_with(**kv) -> str:
    """This page's URL with some params replaced — for links that should
    switch something (the team) without leaving the page."""
    from urllib.parse import urlencode
    q = {k: st.query_params.get(k) for k in st.query_params.keys()}
    q.update({k: v for k, v in kv.items() if v is not None})
    return "?" + urlencode(q)


def _initials(owner: str) -> str:
    parts = config.manager_name(owner).split()
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else parts[0][1:2])).upper()


@st.cache_data(ttl=86400, show_spinner=False)
def get_player_meta() -> dict:
    """{pid: (name, pos, nfl_team)} for every skill-position player."""
    out = {}
    for pid, p in sleeper.get_players().items():
        pos = p.get("position")
        if pos in gameday.LINEUP_POS:
            nm = p.get("full_name") or f'{p.get("first_name", "")} {p.get("last_name", "")}'.strip()
            out[str(pid)] = (nm or str(pid), pos, p.get("team") or "")
    return out


@st.cache_data(ttl=86400, show_spinner=False)
def _pos_team_maps():
    meta = get_player_meta()
    return {p: m[1] for p, m in meta.items()}, {p: m[2] for p, m in meta.items()}


def _pname(pid: str) -> str:
    return get_player_meta().get(str(pid), (str(pid), "", ""))[0]


@st.cache_data(ttl=3600, show_spinner=False)
def get_injury_map() -> dict:
    """{pid: (injury_status, practice_participation, body_part)} for every
    flagged lineup-position player, from Sleeper's player blob (refreshed
    daily — Sleeper asks for no more than that)."""
    out = {}
    for pid, p in sleeper.get_players().items():
        if p.get("position") in gameday.LINEUP_POS and (p.get("injury_status") or p.get("practice_participation")):
            out[str(pid)] = (p.get("injury_status"), p.get("practice_participation"), p.get("injury_body_part"))
    return out


def _risk(ctx: dict, pid: str) -> dict:
    """gameday.injury_risk for one player in this week's context, plus the
    evidence behind it for the hover text."""
    pos_of, team_of = _pos_team_maps()
    status, practice, part = get_injury_map().get(str(pid), (None, None, None))
    r = gameday.injury_risk(status, practice, pos_of.get(str(pid), ""),
                            gameday.status(ctx["games"], team_of.get(str(pid), "")))
    r["why"] = " · ".join(x for x in (status, part, f"practice: {practice}" if practice else None) if x)
    return r


def _risk_td(ctx: dict, pid: str) -> str:
    r = _risk(ctx, pid)
    if r["pct"] is None:
        return '<td class="risk"><span class="rkp ok">&mdash;</span></td>'
    lab = f'{r["label"]} ' if r["label"] else ""
    tip = r["why"] or "no injury tag — the usual in-game risk for his position"
    return f'<td class="risk" title="{tip}"><span class="rkp {r["level"]}">{lab}{r["pct"]}%</span></td>'


_RISK_NOTE = ("Risk % = the chance a player misses the game or gets hurt in it: his injury tag "
              "(moved by this week's practice report) plus a typical in-game rate for his "
              "position. Projections are discounted by the chance he misses, so an Out player "
              "projects 0. An estimate, not a medical model; tags refresh daily.")


@st.cache_data(ttl=30, show_spinner=False)
def get_week_ctx(week: int) -> dict:
    """Everything the weekly pages need for one week, cached 30s so a page
    refreshing every 30s for eight phones is still one call per source.

    sides: {owner: {mid, starters, players, actual}}; starters are aligned
    to `slots` the way Sleeper stores them."""
    lid = LEAGUE["sleeper_league_id"]
    games = gameday.load_week(SEASON, week)
    live = gameday.any_live(games)
    rows = sleeper.get_matchups(lid, week, ttl=30 if live else 600) or []
    rosters = sleeper.get_rosters(lid)
    r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in rosters}
    roster_players = {r2o[int(r["roster_id"])]: [str(p) for p in (r.get("players") or [])] for r in rosters}
    slots = [s for s in (sleeper.get_league(lid).get("roster_positions") or [])
             if s not in ("BN", "IR", "TAXI")]
    sides = {}
    for m in rows:
        o = r2o.get(int(m.get("roster_id") or 0))
        if not o or m.get("matchup_id") is None:
            continue
        sides[o] = {"owner": o, "mid": m["matchup_id"],
                    "starters": [str(p) for p in (m.get("starters") or [])],
                    "players": [str(p) for p in (m.get("players") or [])] or roster_players.get(o, []),
                    "actual": {str(k): float(v or 0) for k, v in (m.get("players_points") or {}).items()}}
    # Projections are Sleeper's, discounted by each player's chance of missing
    # the game. Sleeper is slow to zero an Out player, and undiscounted the
    # lineup advice told people to START him (Breece Hall, Out, quad).
    proj = dict(gameday.week_projections(SEASON, week))
    for pid, (status, practice, _part) in get_injury_map().items():
        if pid in proj:
            miss = gameday.injury_risk(status, practice, "")["miss"]
            if miss:
                proj[pid] = round(proj[pid] * (1 - miss), 2)
    return {"week": week, "games": games, "live": live, "slots": slots, "sides": sides,
            "proj": proj}


def _outlook(ctx: dict, side: dict, starters=None) -> dict:
    pos_of, team_of = _pos_team_maps()
    return gameday.side_outlook(starters if starters is not None else side["starters"],
                                side["actual"], ctx["proj"], pos_of, team_of, ctx["games"])


def _pairs(ctx: dict, me=None) -> list:
    """[(side_a, side_b)] for every matchup, `me` first and on the left."""
    by_mid = {}
    for s in ctx["sides"].values():
        by_mid.setdefault(s["mid"], []).append(s)
    out = []
    for mid in sorted(by_mid):
        pair = by_mid[mid]
        if len(pair) != 2:
            continue
        a, b = pair
        if b["owner"] == me:
            a, b = b, a
        out.append((a, b))
    out.sort(key=lambda ab: ab[0]["owner"] != me)
    return out


def _wp(a: dict, b: dict) -> float:
    return gameday.win_prob(a["final"], a["sd"], b["final"], b["sd"])


def _week_started(ctx: dict) -> bool:
    return any(g.get("state") != "pre" for g in ctx["games"].values())


def _slot_chip(pos: str, slot: str = "") -> str:
    c = _POSC.get(pos, "#8a8a95")
    return f'<span class="slot" style="--c:{c}">{slot or pos or "&mdash;"}</span>'


def _two_div(owner: str, win: bool = False) -> str:
    return (f'<div class="two{" w" if win else ""}"><b>{_team_of(owner)}</b>'
            f'<span>{config.manager_name(owner)}</span></div>')


def _hero_html(a: str, b: str, *, pill: str, big_a: float, big_b: float, kicker: str,
               wp: float, sub_a: str, sub_b: str, cells: list) -> str:
    cell = "".join(f'<div class="hc"><i>{k}</i><b class="{c}">{v}</b><span>{s}</span></div>'
                   for k, v, s, c in cells)
    return (
        '<div class="hero"><div class="hrow">'
        f'<div class="who"><span class="av">{_initials(a)}</span><div><b>{_team_of(a)}</b><em>{sub_a}</em></div></div>'
        f'<div class="wk"><span class="wkpill">&#9679; {pill}</span></div>'
        f'<div class="who r"><div><b>{_team_of(b)}</b><em>{sub_b}</em></div><span class="av dim">{_initials(b)}</span></div>'
        '</div>'
        f'<div class="hnum"><span class="big">{big_a:.1f}</span><span class="hk">{kicker}</span>'
        f'<span class="big dim">{big_b:.1f}</span></div>'
        f'<div class="wpbar"><i style="width:{wp * 100:.0f}%"></i></div>'
        f'<div class="hrow lab"><span><b>{wp * 100:.0f}%</b> YOU</span><span class="hk">win probability</span>'
        f'<span>{(1 - wp) * 100:.0f}%</span></div>'
        f'<div class="hcells">{cell}</div></div>')


def _advice(me: str, week: int) -> dict | None:
    """Lineup advice for `me` in `week`, or None if they have no game."""
    ctx = get_week_ctx(week)
    side = ctx["sides"].get(me)
    if not side or not ctx["slots"]:
        return None
    pos_of, team_of = _pos_team_maps()
    locked = {p for p in side["players"]
              if gameday.status(ctx["games"], team_of.get(p, "")) in ("in", "post")}
    adv = gameday.lineup_advice(side["starters"], side["players"], ctx["slots"], ctx["proj"],
                                pos_of, locked=locked)
    adv["byes"] = [p for p in side["players"] if pos_of.get(p) in gameday.LINEUP_POS
                   and team_of.get(p) and team_of[p] not in ctx["games"] and ctx["games"]]
    adv["ctx"], adv["side"], adv["week"] = ctx, side, week
    return adv


def _todo_html(me: str, adv: dict) -> str:
    wk = adv["week"]
    cards = []
    for i, o, gain in adv["swaps"][:3]:
        cards.append(("&uarr;", f"Start {_pname(i)}, bench {_pname(o)}",
                      f"Week {wk} &middot; worth <b>+{gain:.1f}</b> to your total.",
                      f"+{gain:.1f}", "points", ""))
    for h in adv["holes"]:
        cards.append(("+", f"No {h} for Week {wk}",
                      "Nobody on your roster can fill it. Claim one before waivers run Wednesday.",
                      "0.0", "projected", "bad"))
    if adv["byes"]:
        cards.append(("&#9650;", f'Week {wk} takes {len(adv["byes"])} of yours',
                      ", ".join(_pname(p) for p in adv["byes"]) + ".",
                      str(len(adv["byes"])), "on bye", "bad"))
    ctx_ = adv["ctx"]
    hurt = [(p, _risk(ctx_, p)) for p in adv["side"]["starters"] if p and p != "0"]
    hurt = sorted(((p, r) for p, r in hurt if r["level"] in ("high", "out")), key=lambda x: -(x[1]["pct"] or 0))
    if hurt:
        cards.append(("+", f'{len(hurt)} starter{"s" if len(hurt) != 1 else ""} at real risk this week',
                      ", ".join(f'{_pname(p)} ({r["label"] or "—"}, {r["pct"]}%)' for p, r in hurt[:3])
                      + ". Line up a backup before he locks.",
                      f'{hurt[0][1]["pct"]}%', "risk", "bad"))
    if not cards:
        cards.append(("&#10003;", f"Your Week {wk} lineup is the best one you have",
                      "Nothing to change.", "", "", "good"))
    html = "".join(
        f'<div class="todo {c}"><span class="ic">{ic}</span><div><b>{t}</b><span>{s}</span></div>'
        f'<div class="tv"><b>{v}</b><i>{k}</i></div></div>' for ic, t, s, v, k, c in cards)
    # B&B runs priority waivers, not FAAB, so there's no budget to show.
    html += '<div class="todo-foot">Waivers run <b>Wednesday</b>.</div>'
    return html


def _lineup_rows(ctx: dict, side: dict, *, flag=frozenset(), show_actual=True) -> str:
    """Slot / player / bar / points rows for one lineup as set."""
    pos_of, team_of = _pos_team_maps()
    vals = []
    for pid in side["starters"]:
        played = gameday.status(ctx["games"], team_of.get(pid, "")) in ("in", "post")
        vals.append(side["actual"].get(pid, 0.0) if (show_actual and played) else ctx["proj"].get(pid, 0.0))
    mx = max(vals + [1.0])
    rows = []
    for slot, pid, v in zip(ctx["slots"], side["starters"], vals):
        if not pid or pid == "0":
            rows.append(f'<tr class="swap"><td>{_slot_chip("", slot)}</td><td class="two"><b>Empty</b>'
                        '<span>nobody in this slot</span></td><td class="barc"></td><td class="risk"></td>'
                        '<td class="num">0.0</td></tr>')
            continue
        pos, tm = pos_of.get(pid, ""), team_of.get(pid, "")
        rows.append(
            f'<tr class="{"swap" if pid in flag else ""}"><td>{_slot_chip(pos, slot)}</td>'
            f'<td class="two"><b>{_pname(pid)}</b><span>{tm} &middot; {gameday.game_label(ctx["games"], tm)}</span></td>'
            f'<td class="barc"><div class="bar"><i style="width:{100 * v / mx:.0f}%;background:{_POSC.get(pos, "")}"></i></div></td>'
            f'{_risk_td(ctx, pid)}<td class="num">{v:.1f}</td></tr>')
    return '<table class="dt">' + "".join(rows) + "</table>"


def _picker_html(compact: bool = False) -> str:
    me = _me()
    cards = "".join(
        f'<a class="tp{" on" if o == me else ""}" '
        f'href="{_href_with(me=o, p="home" if page == "pick" else None)}" target="_self">'
        f'<b>{m.get("team") or m["name"]}</b><em>{m["name"]}</em></a>'
        for o, m in MANAGERS.items())
    blurb = ("It decides whose matchup and lineup lead Home and the This Week pages. "
             "Asked once, remembered on this device; switch any time from the masthead. "
             "Everything league-wide stays league-wide.")
    return (f'<div class="card picker"><div class="eyebrow">{"Make it yours" if compact else "This device"}</div>'
            f'<h3>Which team is yours?</h3><p>{blurb}</p><div class="tpgrid">{cards}</div></div>')


def render_team_picker() -> None:
    st.markdown(_picker_html(), unsafe_allow_html=True)


def _need_me(what: str):
    """The current owner, or render the picker and return None."""
    me = _me()
    if me is None:
        st.caption(f"{what} is about your team — pick it once and this device remembers.")
        st.markdown(_picker_html(compact=True), unsafe_allow_html=True)
    return me


def _render_home_my_week(me: str, cur: int) -> None:
    """Home's top: your live matchup, what to do, and your lineup."""
    ctx = get_week_ctx(cur)
    pair = next((ab for ab in _pairs(ctx, me) if ab[0]["owner"] == me), None)
    if pair:
        a, b = (_outlook(ctx, s) for s in pair)
        started = _week_started(ctx)
        done = gameday.week_complete(ctx["games"])
        aw = gameday.advice_week(cur, ctx["games"])
        adv = _advice(me, aw)
        rec = next((r for r in get_standings() if r["owner"] == me), None)
        lineup_cell = (("Week %d lineup" % aw,
                        (f'{len(adv["swaps"])} change{"s" if len(adv["swaps"]) != 1 else ""}'
                         + (f' + {len(adv["holes"])} hole' if adv["holes"] else "")),
                        f'worth +{adv["best_total"] - adv["set_total"]:.1f} pts',
                        "amber" if adv["swaps"] or adv["holes"] else "good") if adv else
                       ("Lineup", "&mdash;", "no game that week", ""))
        st.markdown(_hero_html(
            me, pair[1]["owner"],
            pill=f"Week {cur} &middot; {'final' if done else 'live' if started else 'preview'}",
            big_a=a["points"] if started else a["final"], big_b=b["points"] if started else b["final"],
            kicker="final" if done else "live" if started else "projected", wp=_wp(a, b),
            sub_a=f'you &middot; {a["left"]} still to play', sub_b=f'{b["left"]} still to play',
            cells=[("Projected final", f'{a["final"]:.0f}&ndash;{b["final"]:.0f}', "actual + what's left", "good"),
                   ("Still to play", str(a["left"]), f'theirs {b["left"]}', ""),
                   lineup_cell,
                   ("Record", f'{rec["wins"]}&ndash;{rec["losses"]}' if rec else "&mdash;",
                    f'#{rec["rank"]} in the league' if rec else "", "")]),
            unsafe_allow_html=True)
        left = sorted((g for g in ctx["games"].values() if g.get("state") == "pre" and g.get("home")),
                      key=gameday.kickoff_ts)
        if left and not done:
            nxt = left[0]
            st.markdown(f'<div class="lockline">Week {cur} &middot; next kickoff <b>{nxt["opp"]} @ '
                        f'{[t for t, g in ctx["games"].items() if g is nxt][0]}</b> '
                        f'{gameday.kickoff_label(nxt)} &middot; {len(left)} game{"s" if len(left) != 1 else ""} to go</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="lockline"></div>', unsafe_allow_html=True)
        todo = _todo_html(me, adv) if adv else ""
        st.markdown(
            f'<div class="wk-cols"><div><div class="eyebrow">What to do</div>{todo}</div>'
            f'<div><div class="eyebrow">Your lineup &middot; Week {cur}</div>'
            f'{_lineup_rows(ctx, pair[0])}</div></div>', unsafe_allow_html=True)
        st.caption(_RISK_NOTE)


def _render_around_league(cur: int, me=None) -> None:
    ctx = get_week_ctx(cur)
    pairs = _pairs(ctx, me)
    if not pairs:
        return
    done = gameday.week_complete(ctx["games"])
    st.markdown(theme.section_head('Around the <span class="g">League</span>',
                                   f"week {cur} &middot; {'final' if done else f'all {len(pairs)} games'}"),
                unsafe_allow_html=True)
    rows = []
    for sa, sb in pairs:
        a, b = _outlook(ctx, sa), _outlook(ctx, sb)
        to_play = a["left"] + b["left"]
        rows.append(f'<tr>{_two_cell(sa["owner"], a["final"] > b["final"])}'
                    f'{_two_cell(sb["owner"], b["final"] > a["final"])}'
                    f'<td class="num">{a["points"]:.1f} &ndash; {b["points"]:.1f}</td>'
                    f'<td class="num mut">{f"{to_play} to play" if to_play else "final"}</td></tr>')
    st.markdown('<table class="dt">' + "".join(rows) + "</table>", unsafe_allow_html=True)


def _faceoff_html(ctx: dict, sa: dict, sb: dict) -> str:
    pos_of, team_of = _pos_team_maps()

    def cell(side, pid, right=False):
        if not pid or pid == "0":
            return f'<div class="fo{" r" if right else ""}"><div class="fn"><b>Empty</b><em>&mdash;</em></div><div class="fp">0.0</div></div>'
        tm = team_of.get(pid, "")
        s = gameday.status(ctx["games"], tm)
        val = (f'{side["actual"].get(pid, 0.0):.1f}' if s in ("post", "in", "bye")
               else f'<span class="proj">{ctx["proj"].get(pid, 0.0):.1f}</span>')
        cls = {"pre": "live", "in": "inplay"}.get(s, "")
        return (f'<div class="fo {"r" if right else ""} {cls}"><div class="fn"><b>{_pname(pid)}</b>'
                f'<em>{pos_of.get(pid, "")} &middot; <span class="gl">{gameday.game_label(ctx["games"], tm)}</span>'
                f'<span class="gs">{gameday.game_label(ctx["games"], tm, short=True)}</span></em></div>'
                f'<div class="fp">{val}</div></div>')

    rows = []
    for slot, pa, pb in zip(ctx["slots"], sa["starters"], sb["starters"]):
        done = all(gameday.status(ctx["games"], team_of.get(p, "")) in ("post", "bye") for p in (pa, pb))
        d = sa["actual"].get(pa, 0.0) - sb["actual"].get(pb, 0.0) if done else None
        mid = _slot_chip(pos_of.get(pa) or pos_of.get(pb, ""), slot) + (
            f'<i class="{"pos" if d > 0 else "neg" if d < 0 else ""}">{d:+.1f}</i>' if d is not None else "<i>&middot;</i>")
        rows.append(f'<div class="forow">{cell(sa, pa)}<div class="fm">{mid}</div>{cell(sb, pb, True)}</div>')
    return "".join(rows)


def render_live() -> None:
    st.markdown(theme.section_head('<span class="g">Live</span>', "every Kreeper matchup", page=True),
                unsafe_allow_html=True)
    cur = season.current_week()
    if not cur:
        st.info("🏈 Live scores show up here once the season kicks off.")
        return
    me = _me()
    auto = st.toggle("Auto-refresh while a game is on", value=True, key="live_auto")
    every = 30 if (auto and get_week_ctx(cur)["live"]) else None

    @st.fragment(run_every=every)
    def _body():
        ctx = get_week_ctx(cur)
        from zoneinfo import ZoneInfo
        now = dt.datetime.now(ZoneInfo("America/New_York"))
        st.caption(f"Updated {now:%-I:%M:%S %p} ET · "
                   + ("refreshes every 30s while a game is on" if every
                      else "no game on right now — reload to update" if auto else "auto-refresh off"))
        homes = sorted(((t, g) for t, g in ctx["games"].items() if g.get("home")),
                       key=lambda tg: ({"in": 0, "pre": 1, "post": 2}.get(tg[1]["state"], 3),
                                       gameday.kickoff_ts(tg[1])))
        tiles = "".join(
            f'<div class="gm {g["state"]}"><span>{g["opp"]}</span><b>{"" if g["state"] == "pre" else int(g["opp_score"])}</b>'
            f'<span>{t}</span><b>{"" if g["state"] == "pre" else int(g["score"])}</b>'
            f'<em>{gameday.game_label(ctx["games"], t, short=True)}</em></div>' for t, g in homes)
        if tiles:
            st.markdown(f'<div class="eyebrow">The slate &middot; week {cur}</div><div class="strip">{tiles}</div>',
                        unsafe_allow_html=True)
        pairs = _pairs(ctx, me)
        st.markdown(theme.section_head("Every <span class=\"g\">Matchup</span>",
                                       "yours first" if me else ""), unsafe_allow_html=True)
        cards = []
        for i, (sa, sb) in enumerate(pairs):
            a, b = _outlook(ctx, sa), _outlook(ctx, sb)
            wp = _wp(a, b)
            mine = me is not None and sa["owner"] == me
            cards.append(
                f'<div class="lcard{" mine" if mine else ""}"><div class="lhead">'
                f'{_two_div(sa["owner"], a["final"] > b["final"])}'
                f'<div class="ls"><b>{a["points"]:.1f}</b><span>&ndash;</span><b class="dim">{b["points"]:.1f}</b></div>'
                f'{_two_div(sb["owner"], b["final"] > a["final"])}</div>'
                f'<div class="wpbar sm"><i style="width:{wp * 100:.0f}%"></i></div>'
                f'<div class="lfoot"><span><b>{wp * 100:.0f}%</b> &middot; {a["left"]} to play</span>'
                f'<span class="mid">proj {a["final"]:.0f}&ndash;{b["final"]:.0f}</span>'
                f'<span>{b["left"]} to play &middot; <b>{(1 - wp) * 100:.0f}%</b></span></div>'
                + (f'<div class="eyebrow pad">Slot by slot</div>{_faceoff_html(ctx, sa, sb)}' if mine else "")
                + "</div>")
        if me and cards and pairs[0][0]["owner"] == me:
            st.markdown(cards[0] + f'<div class="lgrid">{"".join(cards[1:])}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="lgrid">{"".join(cards)}</div>', unsafe_allow_html=True)
        if not me:
            st.caption("Pick your team (masthead, top right) to see your matchup slot by slot.")

    _body()


def render_matchup() -> None:
    st.markdown(theme.section_head('<span class="g">Matchup</span>', "your next game &middot; start / sit", page=True),
                unsafe_allow_html=True)
    me = _need_me("Matchup")
    cur = season.current_week()
    if me is None:
        return
    if not cur:
        st.info("🏈 Matchups show up here once the season kicks off.")
        return
    aw = gameday.advice_week(cur, get_week_ctx(cur)["games"])
    adv = _advice(me, aw)
    ctx = get_week_ctx(aw)
    pair = next((ab for ab in _pairs(ctx, me) if ab[0]["owner"] == me), None)
    if not adv or not pair:
        st.info(f"No matchup for you in Week {aw}.")
        return
    sa, sb = pair
    a, b = _outlook(ctx, sa), _outlook(ctx, sb)
    best = [p for _, p in adv["best"] if p]
    fixed = _outlook(ctx, sa, starters=best)
    pre = sorted((g for g in ctx["games"].values() if g.get("state") == "pre"), key=gameday.kickoff_ts)
    started = _week_started(ctx)
    st.markdown(_hero_html(
        me, sb["owner"], pill=f"Week {aw} &middot; {'live' if started else 'preview'}",
        big_a=a["final"], big_b=b["final"], kicker="projected final", wp=_wp(a, b),
        sub_a="you &middot; lineup as set", sub_b="their lineup as set",
        cells=[("Lineup", f'{len(adv["swaps"])} change{"s" if len(adv["swaps"]) != 1 else ""}'
                + (f' + {len(adv["holes"])} hole' if adv["holes"] else ""),
                f'worth +{adv["best_total"] - adv["set_total"]:.1f} pts'
                + (f' &middot; no {", ".join(adv["holes"])}' if adv["holes"] else ""),
                "amber" if adv["swaps"] or adv["holes"] else "good"),
               ("On bye", str(len(adv["byes"])), "of your skill players", "bad" if adv["byes"] else ""),
               ("Next lock", gameday.kickoff_label(pre[0]) if pre else "&mdash;",
                "first game still to kick off" if pre else "every game has started", ""),
               ("Win prob if fixed", f"{_wp(fixed, b) * 100:.0f}%",
                f"from {_wp(a, b) * 100:.0f}% as it stands", "good")]),
        unsafe_allow_html=True)
    pos_of, team_of = _pos_team_maps()
    flag_out = {o for _, o, _g in adv["swaps"]}
    flag_in = {i for i, _o, _g in adv["swaps"]}
    bench = sorted((p for p in sa["players"] if p not in sa["starters"] and pos_of.get(p) in gameday.LINEUP_POS),
                   key=lambda p: -ctx["proj"].get(p, 0.0))
    brows = "".join(
        f'<tr class="{"swap" if p in flag_in else ""}"><td class="two"><b>{_pname(p)}<span class="pos">{pos_of.get(p, "")}</span></b>'
        f'<span>{team_of.get(p, "")}</span></td>'
        f'<td class="num mut">{gameday.game_label(ctx["games"], team_of.get(p, ""), short=True)}</td>'
        f'{_risk_td(ctx, p)}<td class="num">{ctx["proj"].get(p, 0.0):.1f}</td>'
        f'<td>{_START_CHIP if p in flag_in else ""}</td></tr>'
        for p in bench)
    st.markdown(
        f'<div class="lockline"></div><div class="wk-cols">'
        f'<div><div class="eyebrow">What to do &middot; Week {aw}</div>{_todo_html(me, adv)}'
        f'<div class="eyebrow pad">Your bench</div><table class="dt">{brows}</table></div>'
        f'<div><div class="eyebrow">Your lineup as set on Sleeper</div>'
        f'{_lineup_rows(ctx, sa, flag=flag_out, show_actual=started)}</div></div>',
        unsafe_allow_html=True)
    with st.expander(f"{_team_of(sb['owner'])}'s lineup as set"):
        st.markdown(_lineup_rows(ctx, sb, show_actual=started), unsafe_allow_html=True)
    st.caption(f'As set: {adv["set_total"]:.1f} projected; best available {adv["best_total"]:.1f}. '
               "Projections from Sleeper; a player on bye projects 0. Players whose game has started "
               "stay where they are. " + _RISK_NOTE + " Win probability treats each lineup's total as a range, wider "
               "for riskier positions — the Draft Room's model.")


# ------------------------------------------------------------- keeper outlook
# The Draft Room's Keepers screen on Kreeper's own engine: if the season ended
# today, what would each player on your roster cost to keep next year, how
# does that price climb, and which five would you keep. One price per player
# can't be checked; the whole ladder with the rule beside it can.
@st.cache_resource(ttl=600, show_spinner=False)
def _history_through_this_season():
    """H plus THIS season's submitted keepers in the ledger. H only loads
    seasons before this one (that's all the current keeper deadline needs),
    and Sleeper has no keeper flags on our offline-entered draft, so without
    this next year's prices would treat every 2026 keeper as merely drafted."""
    import dataclasses
    kept, rook = set(H.kept_set), set(H.rookie_kept_set)
    for picks in storage.load(SEASON).values():
        for x in picks:
            if x.get("player_id"):
                kept.add((str(x["player_id"]), SEASON))
                if x.get("is_rookie_keeper"):
                    rook.add((str(x["player_id"]), SEASON))
    return dataclasses.replace(H, kept_set=kept, rookie_kept_set=rook)


def _keeper_outlook_rows(owner: str) -> list:
    """Every rostered skill player priced for NEXT season under B&B's rules:
    year 1 = the round he came from (ADP may make it cheaper —
    allow_adp_discount), year 2 = up `year2_bump_rounds` (or ADP if cheaper),
    year 3 = ADP; rookie keepers take the last rounds with no clock; a rookie
    moved to a regular slot costs his ORIGINAL rookie draft round
    (rookie_conversion_cost: original_round) and starts the clock; an
    undrafted add keeps at the last round. Pick ownership isn't enforced in
    this league, so a cost never blocks on a traded-away pick."""
    nxt = SEASON + 1
    hist = _history_through_this_season()
    rules = config.rules()
    bump = int(rules.get("year2_bump_rounds", 3))
    owned = (get_owned_for(nxt).get(owner) or {}) if ENFORCE_OWNED else None
    rows = []
    for pid in CANDS.get(owner, []):
        pid = str(pid)
        pm = H.player_meta(pid)
        if pm.position not in gameday.SKILL:
            continue
        rank = adp_rank_for(pm.name, pm.position)
        adp_rd = engine.adp_rank_to_round(rank, NT) if rank else None
        prof = hist.keeper_profile(owner, pid, nxt)
        r = {"_pid": pid, "name": pm.name, "Pos": pm.position, "adp": rank, "adp_rd": adp_rd,
             "nfl": (H.players.get(pid) or {}).get("team") or "", "Rookie": False,
             "cost": None, "ladder": [], "how": "", "blocked": ""}
        if rookie_keeper_eligible(owner, pid, season=nxt, hist=hist):
            r.update(Rookie=True, cost=DRAFT_ROUNDS, last=True,
                     ladder=[(str(nxt), f"R{DRAFT_ROUNDS}"), ("then", "no clock")],
                     how="Rookie keeper &middot; your last rounds, no 3-year clock")
            # if he misses a rookie slot he can still be kept as a regular, at
            # his original rookie draft round
            anchor = rookie_draft_round(pid)
            if anchor and ROOKIE_CONV_MODE == "original_round":
                conv = engine.compute({**prof, "next_keep_year": 1, "consecutive_keeper_years": 0,
                                       "acquired_via": "draft", "original_round": anchor}, adp_rank=rank)
                r["conv_cost"] = conv.recommended_round or anchor
        else:
            from_rookie = (_rookie_ledger_holds(owner, pid, nxt, hist)
                           and not ever_regular_keeper(pid, hist))
            if from_rookie and ROOKIE_CONV_MODE == "original_round" and rookie_draft_round(pid):
                anchor = rookie_draft_round(pid)
                kc = engine.compute({**prof, "next_keep_year": 1, "consecutive_keeper_years": 0,
                                     "acquired_via": "draft", "original_round": anchor}, adp_rank=rank)
                k, base = 1, kc.recommended_round or anchor
                r["how"] = f"Rookie keeper &rarr; regular &middot; his rookie draft round, R{anchor}"
            else:
                kc = engine.compute(prof, adp_rank=rank)
                if not kc.eligible:
                    r["blocked"] = f"kept {rules.get('max_keep_years', 3)} years &middot; ages out"
                    k = base = None
                else:
                    k = kc.keep_year
                    via, orig = prof.get("acquired_via"), prof.get("original_round")
                    if k == 1 and not (via in ("draft", "trade") and orig):
                        base, r["how"], r["last"] = DRAFT_ROUNDS, f"Undrafted in {SEASON} &middot; keeps at your last round", True
                    else:
                        base = kc.recommended_round
                        if k == 1 and via == "trade":
                            r["how"] = (f'From {config.manager_name(prof.get("prev_owner") or "").split()[0]} '
                                        f"&middot; inherits his R{orig}")
                        elif k == 1:
                            r["how"] = f"Drafted R{orig} in {SEASON}"
                        elif k == 2:
                            r["how"] = f"Kept in {SEASON} &middot; year 2 moves up {bump} rounds, or ADP if cheaper"
                        else:
                            r["how"] = "Year 3 &middot; costs his ADP round"
            if k is not None:
                cost = engine.adjust_to_owned(base, owned, DRAFT_ROUNDS) if (base and owned is not None) else base
                if base and cost is None:
                    r["blocked"] = f"needs a {nxt} pick in R{base} or earlier &middot; you don't own one"
                elif base is None:
                    r["blocked"] = "no ADP yet to price year 3"
                else:
                    r["cost"] = cost
                    # allow_adp_discount: say so when ADP made him cheaper than
                    # the round he came from, or "Drafted R7" next to an R12
                    # cost reads like a bug
                    orig = prof.get("original_round")
                    if k == 1 and orig and cost > orig and not r.get("last"):
                        r["how"] += f" &middot; ADP makes it R{cost}"
                    if k == 1:
                        r["ladder"] = [(str(nxt), f"R{cost}"), (str(nxt + 1), f"R{max(1, base - bump)}"),
                                       (str(nxt + 2), "ADP")]
                    elif k == 2:
                        r["ladder"] = [(str(nxt), f"R{cost}"), (str(nxt + 1), "ADP"), ("", "done")]
                    else:
                        r["ladder"] = [(str(nxt), f"R{cost} &middot; ADP"), ("", "done")]
        r["Value"] = keeper_value(rank, r["cost"]) if r["cost"] else None
        rows.append(r)

    # Pick the five: rookie slots first from rookie-eligible players; a rookie
    # who misses a rookie slot competes for a regular slot at his conversion
    # price (his original rookie round here), not cut behind a worse veteran.
    from collections import Counter
    caps, pc = position_keeper_caps(), Counter()

    def fits(x):
        lim = caps.get(x["Pos"])
        return lim is None or pc[x["Pos"]] < lim

    cands = [x for x in rows if x["Value"] is not None]
    rook_pick, reg_pick = [], []
    for x in sorted((c for c in cands if c["Rookie"]), key=lambda c: -c["Value"]):
        if len(rook_pick) < MAX_ROOKIE and fits(x):
            rook_pick.append(x)
            pc[x["Pos"]] += 1
    for x in rows:
        if x["Rookie"] and x not in rook_pick and x.get("conv_cost"):
            c = x["conv_cost"]
            x.update(Rookie=False, converted=True, last=False, cost=c, Value=keeper_value(x["adp"], c),
                     ladder=[(str(nxt), f"R{c}"), (str(nxt + 1), f"R{max(1, c - bump)}"), (str(nxt + 2), "ADP")],
                     how=f"Rookie keeper &rarr; regular &middot; his rookie draft round, R{c}")
    cands = [x for x in rows if x["Value"] is not None]
    for x in sorted((c for c in cands if c not in rook_pick and not c["Rookie"]), key=lambda c: -c["Value"]):
        if len(reg_pick) < MAX_REG and fits(x):
            reg_pick.append(x)
            pc[x["Pos"]] += 1
    # Last-round keepers (rookie slots, undrafted adds) step down from the
    # last round: R16, R15, ...
    rnd = DRAFT_ROUNDS
    for x in rook_pick + reg_pick:
        if x.get("last"):
            x["cost"] = rnd
            x["Value"] = keeper_value(x["adp"], rnd) if x["adp"] else x["Value"]
            x["ladder"] = ([(str(nxt), f"R{rnd}"), ("then", "no clock")] if x["Rookie"] else
                           [(str(nxt), f"R{rnd}"), (str(nxt + 1), f"R{max(1, rnd - bump)}"), (str(nxt + 2), "ADP")])
            rnd -= 1
    keep_ids = [x["_pid"] for x in rook_pick + reg_pick]
    for x in rows:
        x["verdict"] = "keep" if x["_pid"] in keep_ids else "blocked" if x["blocked"] else "cut"
        x["slot"] = "rookie" if x in rook_pick else "regular"
    cuts = sorted((x for x in rows if x["verdict"] == "cut" and x["Value"] is not None),
                  key=lambda x: -x["Value"])
    if cuts:
        cuts[0]["verdict"] = "next"
    order = {"keep": 0, "next": 1, "cut": 2, "blocked": 3}
    rows.sort(key=lambda x: (order[x["verdict"]], keep_ids.index(x["_pid"]) if x["_pid"] in keep_ids else 0,
                             -(x["Value"] if x["Value"] is not None else -99)))
    return rows


def _headshot(pid: str) -> str:
    return (f'<img class="kh-img" src="https://sleepercdn.com/content/nfl/players/thumb/{pid}.jpg" '
            f'onerror="this.style.visibility=\'hidden\'" alt="">')


def _keeper_tray_html(rows: list) -> str:
    keeps = [r for r in rows if r["verdict"] == "keep"]
    reg = [r for r in keeps if r["slot"] == "regular"]
    rook = [r for r in keeps if r["slot"] == "rookie"]
    slots = [(f"Keeper {i + 1}", reg[i] if i < len(reg) else None) for i in range(MAX_REG)] + \
            [(f"Rookie {i + 1}", rook[i] if i < len(rook) else None) for i in range(MAX_ROOKIE)]
    cells = []
    for lab, r in slots:
        if r is None:
            cells.append(f'<div class="kt empty"><i>{lab}</i><b>open</b><span>nobody worth it</span></div>')
            continue
        v = r["Value"]
        cells.append(f'<div class="kt"><i>{lab}</i>{_headshot(r["_pid"])}<b>{r["name"]}</b>'
                     f'<span>R{r["cost"]} &middot; <em class="{"good" if (v or 0) > 0 else "bad" if (v or 0) < 0 else ""}">'
                     f'{v:+d}</em></span></div>')
    return f'<div class="ktray">{"".join(cells)}</div>'


_VERDICT = {"keep": ("keep", "good"), "next": ("first out", "amber"), "cut": ("cut", ""),
            "blocked": ("blocked", "bad")}


def _keeper_card_html(r: dict) -> str:
    lab, tone = _VERDICT[r["verdict"]]
    steps = "".join(
        f'<span class="ks{" now" if i == 0 else ""}"><i>{yr}</i><b>{price}</b></span>'
        + ('<span class="ka">&rarr;</span>' if i < len(r["ladder"]) - 1 else "")
        for i, (yr, price) in enumerate(r["ladder"]))
    if r["blocked"]:
        steps = f'<span class="kb">{r["blocked"]}</span>'
    v = r["Value"]
    val = (f'<div class="kv {"good" if v > 0 else "bad" if v < 0 else ""}"><b>{v:+d}</b><i>value</i></div>'
           if v is not None else
           f'<div class="kv"><b>&mdash;</b><i>{"blocked" if r["blocked"] else "no ADP"}</i></div>')
    adp = f'ADP R{r["adp_rd"]} (#{int(r["adp"])})' if r["adp"] else "no ADP"
    return (f'<div class="kcard2 {r["verdict"]}">{_headshot(r["_pid"])}<div class="kc-main">'
            f'<div class="kc-top"><b>{r["name"]}</b><span class="pos">{r["Pos"]} &middot; {r["nfl"] or "FA"}</span>'
            f'<span class="chip {tone}">{lab}</span></div>'
            f'<div class="kladder">{steps}</div>'
            f'<div class="kc-how">{r["how"] or "&nbsp;"} &middot; {adp}</div></div>{val}</div>')


def render_keeper_outlook() -> None:
    nxt = SEASON + 1
    st.markdown(theme.section_head(f'{nxt} <span class="g">Keepers</span>', "if the season ended today",
                                   page=True), unsafe_allow_html=True)
    me = _need_me("Keepers")
    if me is None:
        return
    rows = _keeper_outlook_rows(me)
    if not rows:
        st.info("No skill players on your roster to price.")
        return
    keeps = [r for r in rows if r["verdict"] == "keep"]
    blocked = [r for r in rows if r["verdict"] == "blocked"]
    best = max(keeps, key=lambda r: r["Value"] or -99) if keeps else None
    bump = int(config.rules().get("year2_bump_rounds", 3))
    cells = [("Keeper slots", str(MAX_REG + MAX_ROOKIE), f"{MAX_REG} regular + {MAX_ROOKIE} rookie", ""),
             ("Best value", best["name"].split()[-1] if best else "&mdash;",
              f'{best["Value"]:+d} value' if best else "", "good"),
             ("Blocked", str(len(blocked)), blocked[0]["name"] if blocked else "nobody aged out",
              "bad" if blocked else ""),
             ("Escalation", f"&minus;{bump} rds", f'year 2 &middot; year {config.rules().get("max_keep_years", 3)} is ADP', "")]
    st.markdown('<div class="hero kh"><div class="hcells">' + "".join(
        f'<div class="hc"><i>{k}</i><b class="{c}">{v}</b><span>{s}</span></div>' for k, v, s, c in cells)
        + "</div></div>", unsafe_allow_html=True)
    st.markdown(f'<div class="eyebrow pad">The five it would keep</div>{_keeper_tray_html(rows)}',
                unsafe_allow_html=True)

    notes = []
    for b in blocked[:1]:
        notes.append(("&#8856;", f'{b["name"]} can\'t be kept in {nxt}',
                      f'{b["blocked"].replace("&middot;", "—")}. From here he\'s a rental, so his trade value only falls.',
                      "bad"))
    cheap = [r for r in keeps if (r["Value"] or 0) >= 25]
    if cheap:
        notes.append(("&#9678;", ", ".join(r["name"] for r in cheap[:3]),
                      "Cost a late pick and are worth an early one — build trades around them, don't sell them.",
                      "good"))
    nxt_out = next((r for r in rows if r["verdict"] == "next"), None)
    if nxt_out:
        notes.append(("!", f'{nxt_out["name"]} is the first one out',
                      f'{nxt_out["Value"]:+d} value. If a keeper above gets hurt or traded, he\'s the replacement.',
                      ""))
    notes.append(("$", f"A waiver add keeps at R{DRAFT_ROUNDS}",
                  "So a mid-season breakout is the cheapest keeper there is. Every claim competes with the list below.",
                  "good"))
    st.markdown('<div class="eyebrow pad">What this changes now</div>' + "".join(
        f'<div class="todo {c}"><span class="ic">{ic}</span><div><b>{t}</b><span>{s}</span></div></div>'
        for ic, t, s, c in notes), unsafe_allow_html=True)

    st.markdown(theme.section_head("Your roster, <span class=\"g\">priced year by year</span>"),
                unsafe_allow_html=True)
    st.markdown('<div class="kgrid">' + "".join(_keeper_card_html(r) for r in rows) + "</div>",
                unsafe_allow_html=True)
    st.caption(f"**Value** is what keeping him is worth: his talent (a draft-value curve, the #1 player ≈ 100) "
               f"minus what that round's pick would actually land in our draft once ~40 keepers are off the board. "
               f"That's why an elite player kept in the 1st still scores well — a 1st-round pick only lands about "
               f"the 35th-best player — and why a stud at a last-round price scores best of all. ADP is this year's "
               f"consensus. Costs follow the house rules: the round he came from, up {bump} rounds in year 2, ADP in "
               f"year 3 (ADP can always make a keeper cheaper here); rookie keepers take your last rounds with no clock, "
               f"and one moved to a regular slot costs his original rookie draft round. "
               f"Set My Keepers does the exact allocation before the draft.")


def _render_home_payouts() -> None:
    """The league's payouts as liquid bowls, from config.yaml `payouts:`.
    Hidden until the amounts are filled in — better no section than a wrong
    one. Shape:
        payouts:
          buy_in: 100
          places:
            - {label: "Champion", amount: 600, note: "..."}
    """
    cfg = config.load().get("payouts") or {}
    places = [p for p in (cfg.get("places") or []) if p.get("amount")]
    if not places:
        return
    total = sum(float(p["amount"]) for p in places)
    buy_in = cfg.get("buy_in")
    cap = (f'${float(buy_in):,.0f} buy-in &middot; ${total:,.0f} paid out' if buy_in
           else f'${total:,.0f} paid out')
    st.markdown(theme.section_head('The <span class="g">Money</span>', cap), unsafe_allow_html=True)
    top = max(float(p["amount"]) for p in places)
    colors = [theme.PURPLE, theme.GOLD_D, theme.TEAL, theme.CYAN, theme.RED]
    bowls = []
    for i, p in enumerate(places):
        amt = float(p["amount"])
        ring = theme.liquid_ring_html(amt / top, f"${amt:,.0f}", "", size=132, accent=colors[i % len(colors)])
        bowls.append(f'<div class="bowl">{ring}<div class="bl">{p.get("label", "")}</div>'
                     f'<div class="bn">{p.get("note", "")}</div></div>')
    st.markdown('<div class="money-bowls">' + "".join(bowls) + "</div>", unsafe_allow_html=True)


def _render_home_in_season() -> None:
    """Live season, as a Command Center: your matchup, what to do and your
    lineup first (for whichever team this device picked — see _me), then the
    league-wide Home: every matchup, the money, power rankings, recent moves.
    With no team picked, the picker sits where your matchup would be.
    """
    table = get_standings()
    cur = season.current_week()
    if not cur:
        # The season hasn't kicked off — nothing live to lead with.
        render_home_glance()
        render_odds()
        return

    # ---- your week (the Command Center) ----
    me = _me()
    if me:
        _render_home_my_week(me, cur)
    else:
        st.markdown(_picker_html(compact=True), unsafe_allow_html=True)

    # ---- every matchup this week ----
    _render_around_league(cur, me)

    # ---- the money ----
    _render_home_payouts()

    # ---- power rankings ----
    power = get_power_rankings()
    if power:
        st.markdown(theme.section_head(
            'Power <span class="g">Rankings</span>',
            "45% win rate &middot; 35% scoring &middot; 20% recent form"),
            unsafe_allow_html=True)
        by_owner = {r["owner"]: r for r in table}
        top = max(r["score"] for r in power) or 1
        prow = []
        for r in power:
            d = r["rank_delta"]
            chip = (f'<span class="chip good">&#9650; {d}</span>' if d > 0
                    else f'<span class="chip bad">&#9660; {abs(d)}</span>' if d < 0
                    else '<span class="chip">holding</span>')
            s = by_owner.get(r["owner"], {})
            prow.append(
                f'<tr><td class="rk">{r["rank"]}</td>{_two_cell(r["owner"])}'
                f'<td class="num">{s.get("wins", 0)}&ndash;{s.get("losses", 0)}</td>'
                f'<td class="num pf">{s.get("points_for", 0):.1f}</td>'
                f'<td class="pw"><div class="pbar">'
                f'<i style="width:{100 * r["score"] / top:.0f}%"></i></div></td>'
                f'<td>{chip}</td></tr>')
        st.markdown(
            '<div class="neonwrap"><table class="lb"><thead><tr><th></th><th>Team</th>'
            '<th style="text-align:right;">W&ndash;L</th>'
            '<th class="pf" style="text-align:right;">PF</th><th>Power</th><th></th></tr></thead>'
            f'<tbody>{"".join(prow)}</tbody></table></div>', unsafe_allow_html=True)
        st.markdown(
            f'<p class="sec-note">The bracket is decided on <b>record</b>, not this — the top '
            f'{PLAYOFF_TEAMS} by record make it. Power ranks the ten by how they\'ve actually '
            f'played; the arrow is movement against where the standings have them.</p>',
            unsafe_allow_html=True)

    # ---- recent moves ----
    moves = get_recent_moves()
    if moves:
        st.markdown(theme.section_head('Recent <span class="g">Moves</span>',
                                       "claims, adds and trades"), unsafe_allow_html=True)
        mrow = "".join(
            f'<tr><td class="two"><b>{m["kind"]}</b><span>week {m["week"]}</span></td>'
            f'<td class="two"><b>{_move_player_html(m["player_id"])}</b>'
            f'<span>{config.manager_name(m["owner"])}</span></td>'
            '</tr>' for m in moves)
        st.markdown(
            '<div class="neonwrap"><table class="lb"><thead><tr><th>Move</th><th>Player</th>'
            f'</tr></thead><tbody>{mrow}</tbody></table></div>', unsafe_allow_html=True)


def _render_home_offseason() -> None:
    st.caption("Season's over — here's the recap.")
    render_home_glance()
    render_record_book()
    render_superlatives()


def render_rookies() -> None:
    st.markdown(f'<h2 class="two-tone">{SEASON} Top <span class="g">Rookies</span></h2>', unsafe_allow_html=True)
    st.caption("This year's NFL rookie class ranked by our consensus ADP — your rookie-keeper targets.")
    df = build_rookies_table(40)
    if df.empty:
        st.info("No rookies found in the current ADP data yet — run `python scripts/refresh_adp.py`.")
        return
    rows = []
    for _, r in df.iterrows():
        cadp = "" if r["Consensus ADP"] is None else f'{r["Consensus ADP"]:.1f}'
        rows.append(
            f'<tr><td class="rk">{r["#"]}</td>'
            f'<td class="pl">{theme.img_tag(r["_pid"])}{r["Player"]}</td>'
            f'<td class="pos"><span class="posdot p-{r["Pos"]}"></span>{r["Pos"]}</td>'
            f'<td>{r["NFL"]}</td>'
            f'<td class="num">{r["ADP"]}</td>'
            f'<td class="num">{cadp}</td></tr>'
        )
    head = ('<tr><th>#</th><th>Player</th><th>Pos</th><th>NFL</th>'
            '<th>ADP&nbsp;Rank</th><th>Consensus&nbsp;ADP</th></tr>')
    st.markdown('<div class="neonwrap" style="max-height:660px;overflow:auto;">'
                '<table class="lb lb-rook"><thead>' + head + '</thead><tbody>'
                + "".join(rows) + '</tbody></table></div>', unsafe_allow_html=True)


@st.cache_data(ttl=1800, show_spinner=False)
def get_recent_trades(limit: int = 8) -> list:
    from kreeper import trades as trades_mod
    return trades_mod.recent_trades(lambda pid: H.player_meta(pid).name, limit=limit)


def render_recent_trades() -> None:
    st.markdown('<h2 class="two-tone">Recent <span class="g">Trades</span></h2>', unsafe_allow_html=True)
    st.caption("Every deal carries its keeper round obligations forward to the new team.")
    deals = get_recent_trades()
    if not deals:
        st.info("No completed trades on record yet.")
        return
    cards = []
    for t in deals:
        header = ' <span class="vs">traded with</span> '.join(f'<b>{nm}</b>' for nm, _ in t["teams"])
        cols = "".join(
            f'<div><b>{nm} receives</b>'
            + "".join(f'<span class="chip asset">{a}</span>' for a in assets)
            + '</div>'
            for nm, assets in t["teams"]
        )
        cards.append(
            f'<div class="trade"><div class="trade-teams">{header}</div>'
            f'<div class="trade-assets">{cols}</div>'
            f'<div class="trade-date">{t["date"]}</div></div>'
        )
    st.markdown('<div class="trades-wrap">' + "".join(cards) + '</div>', unsafe_allow_html=True)


def render_trade_targets() -> None:
    st.markdown('<h2 class="two-tone">Keeper Trade <span class="g">Market</span></h2>', unsafe_allow_html=True)
    st.caption("Pick the round you'd keep someone at — these are the players across "
               "the league whose keeper cost is that round. The keeper round carries "
               "over on a trade, so you could deal for one and keep them there. Best "
               "value (cheapest relative to ADP) up top.")
    df = build_trade_targets()
    if df.empty:
        st.info("No keeper data yet — run `python scripts/refresh_adp.py` to populate ADP.")
        return

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        rnd = st.selectbox("Keeper cost round", list(range(1, DRAFT_ROUNDS + 1)),
                           index=1, help="The round a keeper would cost you.")
    with c2:
        pos_f = st.selectbox("Position", ["All", "QB", "RB", "WR", "TE"], key="tm_pos")
    with c3:
        me = st.selectbox("Hide my own players (optional)",
                          ["— show everyone —"] + list(NAME_TO_ID.keys()), index=0)

    view = df[df["Cost Rd"] == rnd].copy()
    if pos_f != "All":
        view = view[view["Pos"] == pos_f]
    if me in NAME_TO_ID:
        view = view[view["Owner"] != me]

    view = view.sort_values(["Value", "ADP"], ascending=[False, True])
    if view.empty:
        st.info(f"No keeper-eligible players cost Round {rnd} right now.")
        return

    rows = []
    for i, (_, r) in enumerate(view.iterrows(), 1):
        val = int(r["Value"])
        color = "#1c9b63" if val > 0 else ("#c0392b" if val < 0 else "#8a7fb3")
        rk = ' <span class="rk-badge">RK</span>' if r.get("Rookie") else ""
        rows.append(
            f'<tr><td class="rk">{i}</td>'
            f'<td class="pl">{theme.img_tag(r["_pid"])}{r["Player"]}{rk}</td>'
            f'<td class="pos"><span class="posdot p-{r["Pos"]}"></span>{r["Pos"]}</td>'
            f'<td>{r["Owner"]}</td>'
            f'<td class="num">{r["Keep Yr"]}</td>'
            f'<td class="num">{r["ADP"]}</td>'
            f'<td class="num" style="color:{color};font-weight:600;">{val:+d}</td></tr>'
        )
    head = ('<tr><th>#</th><th>Player</th><th>Pos</th><th>Owner</th>'
            '<th>Keep&nbsp;Yr</th><th>ADP</th><th class="r">Value</th></tr>')
    st.markdown(f'<p style="margin:.2rem 0 .6rem;">Keepable at <b>Round {rnd}</b>:</p>',
                unsafe_allow_html=True)
    st.markdown('<div class="neonwrap"><table class="lb lb-trade"><thead>' + head
                + '</thead><tbody>' + "".join(rows) + '</tbody></table></div>',
                unsafe_allow_html=True)
    st.caption(f"Value = the player's talent minus what a Round {rnd} pick would actually "
               "land once keepers are off the board. **RK** = currently a rookie keeper — on a "
               "trade they convert to a regular keeper at the round they were originally "
               "drafted as a rookie (rookie status doesn't transfer and the 3-year clock "
               "starts), which is the cost shown here.")


def build_record_book():
    from kreeper import sleeper
    chain = sleeper.league_chain(LEAGUE["sleeper_league_id"])
    seasons = []  # newest first: {season, standings:[...], champ, runner}
    agg = {o: {"w": 0, "l": 0, "pf": 0.0, "titles": 0, "runner": 0, "seasons": 0, "best": ""}
           for o in MANAGERS}
    for c in chain:
        if c["season"] == SEASON:
            continue
        rosters = sleeper.get_rosters(c["league_id"])
        r2o = {int(r["roster_id"]): str(r.get("owner_id")) for r in rosters}
        champ = runner = None
        try:
            for m in sleeper.get_winners_bracket(c["league_id"]):
                if m.get("p") == 1:
                    champ, runner = r2o.get(m.get("w")), r2o.get(m.get("l"))
        except Exception:  # noqa: BLE001
            pass
        standings = []
        for r in rosters:
            o = str(r.get("owner_id"))
            s = r.get("settings", {}) or {}
            w, l = s.get("wins", 0) or 0, s.get("losses", 0) or 0
            pf = s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100
            standings.append({"owner": o, "name": config.manager_name(o), "w": w, "l": l, "pf": round(pf, 1)})
            if o in agg:
                agg[o]["w"] += w; agg[o]["l"] += l; agg[o]["pf"] += pf; agg[o]["seasons"] += 1
                if o == champ:
                    agg[o]["titles"] += 1
                if o == runner:
                    agg[o]["runner"] += 1
        standings.sort(key=lambda x: (-x["w"], -x["pf"]))
        seasons.append({"season": c["season"], "standings": standings,
                        "champ": config.manager_name(champ) if champ else None,
                        "runner": config.manager_name(runner) if runner else None})
    return seasons, agg


def render_record_book() -> None:
    st.markdown('<h2 class="two-tone">League <span class="g">Record Book</span></h2>', unsafe_allow_html=True)
    seasons, agg = build_record_book()
    if not seasons:
        st.info("No completed seasons on record yet.")
        return

    st.markdown("##### Champions")
    champ_rows = "".join(
        f'<tr><td class="rk">{s["season"]}</td>'
        f'<td class="pl">{s["champ"] or "—"}</td>'
        f'<td>runner-up: {s["runner"] or "—"}</td></tr>'
        for s in seasons)
    st.markdown('<div class="neonwrap"><table class="lb"><thead>'
                '<tr><th>Season</th><th>Champion</th><th></th></tr></thead><tbody>'
                + champ_rows + '</tbody></table></div>', unsafe_allow_html=True)

    st.markdown("##### All-Time Standings")
    rows = []
    order = sorted(agg.items(),
                   key=lambda kv: (kv[1]["titles"], kv[1]["w"] / max(1, kv[1]["w"] + kv[1]["l"])),
                   reverse=True)
    for i, (o, a) in enumerate(order, 1):
        if a["seasons"] == 0:
            continue
        wp = a["w"] / max(1, a["w"] + a["l"])
        rings = (f'<span style="color:var(--gold-d);font-weight:700;">&times;{a["titles"]}</span>' if a["titles"] else "")
        rows.append(
            f'<tr><td class="rk">{i}</td>'
            f'<td class="pl">{config.manager_name(o)} {rings}</td>'
            f'<td class="num">{a["w"]}-{a["l"]}</td>'
            f'<td class="num">{wp:.3f}</td>'
            f'<td class="num">{int(a["pf"])}</td>'
            f'<td class="num">{a["titles"]}</td>'
            f'<td class="num">{a["runner"]}</td></tr>'
        )
    head = ('<tr><th>#</th><th>Manager</th><th>All-Time</th><th>Win%</th>'
            '<th>Points</th><th>Titles</th><th>Finals</th></tr>')
    st.markdown('<div class="neonwrap"><table class="lb lb-record"><thead>' + head
                + '</thead><tbody>' + "".join(rows) + '</tbody></table></div>',
                unsafe_allow_html=True)

    st.markdown("##### Season by Season")
    for s in seasons:
        title = f"{s['season']} — {s['champ'] or '—'}"
        with st.expander(title):
            body = "".join(
                f'<tr><td class="rk">{i}</td><td class="pl">{r["name"]}</td>'
                f'<td class="num">{r["w"]}-{r["l"]}</td><td class="num">{r["pf"]}</td></tr>'
                for i, r in enumerate(s["standings"], 1))
            st.markdown('<table class="lb"><thead><tr><th>#</th><th>Team</th>'
                        '<th>Record</th><th>Points</th></tr></thead><tbody>'
                        + body + '</tbody></table>', unsafe_allow_html=True)


def _draft_value(pos: int) -> int:
    """Trade-value points for an asset at overall draft position `pos` (a standard
    decaying draft-value curve; pick #1 ≈ 100)."""
    return max(1, round(100 * (0.965 ** (max(1, pos) - 1))))


def asset_value(rank: int, rookie: bool, rookie_factor: float | None = None) -> int:
    """Trade value of an available draft asset. Veterans = talent by their ADP.
    Rookies are worth MORE than their rookie-year ADP because a hit becomes a
    near-free last-round keeper for their whole career — so we scale a rookie's
    talent by the league's rookie premium (1/rookie_factor; at 0.4 that's ~2.5x).
    This is why a stud rookie tops the board and the 1.01 is so valuable."""
    base = _draft_value(rank)
    if not rookie:
        return base
    rf = _mock_rookie_factor() if rookie_factor is None else rookie_factor
    return max(1, round(base / max(0.15, rf)))


def _pick_value(rnd: int) -> int:
    """Points for a draft pick in a given round (valued at a mid-round slot)."""
    return _draft_value((rnd - 1) * NT + NT // 2)


def pick_market_values():
    """Realistic value of each draft pick = the trade-asset value of the player
    projected AVAILABLE at that slot once keepers are off the board — including the
    rookie-keeper premium, so the 1.01 lands the top rookie (a career last-round
    keeper) and is the most valuable pick, not an abstract '#1 overall'. A pick
    occupied by a keeper in the projection is valued by the nearest open pick.
    Returns (by_pick: {pick_no: pts}, by_round: {round: avg pts})."""
    rf = _mock_rookie_factor()
    mock = build_mock_draft()
    by_pick = {}
    for _, r in mock.iterrows():
        rank = r.get("ADP")
        if not bool(r.get("Keeper")) and rank is not None and not pd.isna(rank):
            by_pick[int(r["Pick"])] = asset_value(int(rank), bool(r.get("Rookie")), rf)
    valued = sorted(by_pick)
    for _, r in mock.iterrows():
        pn = int(r["Pick"])
        if pn not in by_pick and valued:
            by_pick[pn] = by_pick[min(valued, key=lambda p: abs(p - pn))]
    by_round: dict = {}
    for _, r in mock.iterrows():
        by_round.setdefault(int(r["Round"]), []).append(by_pick.get(int(r["Pick"]), 1))
    by_round = {rd: max(1, round(sum(v) / len(v))) for rd, v in by_round.items()}
    return by_pick, by_round


def render_trade_analyzer() -> None:
    st.markdown('<h2 class="two-tone">Trade <span class="g">Analyzer</span></h2>', unsafe_allow_html=True)
    st.caption("Build a deal and grade it. Each player is valued by their talent "
               "(ADP draft position) plus any keeper bargain on top; picks by a "
               "draft-value curve. Higher total wins.")

    tt = build_trade_targets()
    if tt.empty:
        st.info("No keeper data yet — run `python scripts/refresh_adp.py` to populate ADP.")
        return
    kv = {str(r["_pid"]): int(r["Value"]) for _, r in tt.iterrows() if r["Value"] is not None}  # keeper value (talent pts)
    adp = {str(r["_pid"]): int(r["ADP"]) for _, r in tt.iterrows()}      # ADP rank

    names = list(NAME_TO_ID.keys())
    c1, c2 = st.columns(2)
    with c1:
        a = st.selectbox("Team A", names, index=0, key="ta_a")
    with c2:
        b = st.selectbox("Team B", [n for n in names if n != a], index=0, key="ta_b")
    oa, ob = NAME_TO_ID[a], NAME_TO_ID[b]

    def roster_opts(oid):
        out = {}
        for pid in CANDS.get(oid, []):
            pm = H.player_meta(pid)
            if pm.position in ("QB", "RB", "WR", "TE"):
                out[f"{pm.name} ({pm.position})"] = str(pid)
        return out

    # Once this year's draft has run its picks are gone, so the tradeable
    # picks are the next three drafts — listing the spent year showed rounds a
    # team no longer has (and hid the ones it does).
    first_year = SEASON + 1 if current_draft_done() else SEASON
    pick_seasons = [first_year, first_year + 1, first_year + 2]
    cur_slots = current_pick_slots()
    by_pick, by_round = pick_market_values()

    def owned_picks(oid):
        """[(label, points)] for every pick `oid` owns. Picks are valued by the
        player projected AVAILABLE at that slot once keepers are off the board (so
        the 1.01 is worth the best un-kept player, and a 1.03 differs from a 1.01).
        This year uses the real snake/trade-aware slot ('2026 R1 (1.03)'); future
        years use that round's average value, discounted ~20% per year out."""
        items = []
        for yr in pick_seasons:
            discount = 0.8 ** (yr - first_year)
            if yr == SEASON:
                for rnd in sorted(cur_slots.get(oid, {})):
                    for pick_no in cur_slots[oid][rnd]:
                        pir = pick_no - (rnd - 1) * NT
                        pts = by_pick.get(pick_no, by_round.get(rnd, 1))
                        items.append((f"{yr} R{rnd} ({rnd}.{pir:02d})", pts * discount))
            else:
                owned = get_owned_for(yr).get(oid) or {}
                for rnd in range(1, DRAFT_ROUNDS + 1):
                    cnt = owned.get(rnd, 0)
                    for i in range(cnt):
                        label = f"{yr} R{rnd}" + (f" (#{i+1})" if cnt > 1 else "")
                        items.append((label, by_round.get(rnd, _pick_value(rnd)) * discount))
        return items

    ra, rb = roster_opts(oa), roster_opts(ob)
    a_picks, b_picks = owned_picks(oa), owned_picks(ob)
    a_pts_map, b_pts_map = dict(a_picks), dict(b_picks)
    with c1:
        a_pl = st.multiselect(f"{a} sends — players", list(ra.keys()), key="ta_apl")
        a_pk = st.multiselect(f"{a} sends — picks", [lbl for lbl, _ in a_picks], key="ta_apk")
    with c2:
        b_pl = st.multiselect(f"{b} sends — players", list(rb.keys()), key="ta_bpl")
        b_pk = st.multiselect(f"{b} sends — picks", [lbl for lbl, _ in b_picks], key="ta_bpk")

    def player_value(pid):
        """Talent (by ADP draft position) + a bonus for any keeper bargain."""
        pid = str(pid)
        ar = adp.get(pid) or adp_rank_for(H.player_meta(pid).name, H.player_meta(pid).position)
        talent = _draft_value(int(ar)) if ar else 4
        bonus = max(0, kv.get(pid, 0))   # keeper value — same talent-point units, on top of talent
        return talent + bonus

    def side_value(players, ropts, picks, pts_map):
        pv = sum(player_value(ropts[p]) for p in players)
        pc = sum(pts_map.get(p, 0) for p in picks)
        return pv, pc

    # What each team RECEIVES (the other side's outgoing assets).
    a_pv, a_pc = side_value(b_pl, rb, b_pk, b_pts_map)   # A receives B's stuff
    b_pv, b_pc = side_value(a_pl, ra, a_pk, a_pts_map)   # B receives A's stuff

    if not (a_pl or a_pk or b_pl or b_pk):
        st.info("Pick players and/or picks for each side to grade the deal.")
        return

    a_score, b_score = a_pv + a_pc, b_pv + b_pc
    col1, col2 = st.columns(2)
    for col, who, pv, pc, score in ((col1, a, a_pv, a_pc, a_score), (col2, b, b_pv, b_pc, b_score)):
        col.markdown(f"#### {who} receives")
        col.metric("Players", f"{round(pv)} pts", help="Talent (ADP position) + keeper bargain")
        col.metric("Picks", f"{round(pc)} pts")
        col.caption(f"Total value: **{round(score)}**")

    diff = a_score - b_score
    if abs(diff) <= max(10, 0.08 * max(a_score, b_score, 1)):
        st.success("Even deal — both sides come out roughly equal.")
    else:
        winner = a if diff > 0 else b
        st.success(f"Edge to **{winner}** by ~{abs(round(diff))} pts.")
    st.caption("Heuristic only — player value = a draft-value curve at their ADP "
               "plus a bonus for any keeper discount. Picks are valued by the player "
               "projected available at that slot once keepers are off the board, "
               "including the rookie-keeper premium — so the 1.01 lands the top rookie "
               "(a near-free last-round keeper for years) and is the most valuable pick, "
               "and a 1.03 differs from a 1.01. Future-year picks use that round's "
               "average value, discounted ~20% per year out. Doesn't model roster need.")


def render_keeper_landscape() -> None:
    st.markdown('<h2 class="two-tone">Keeper <span class="g">Landscape</span></h2>', unsafe_allow_html=True)
    done = current_draft_done()
    if done:
        # The draft has run: show who was actually kept, by the team that kept
        # him — not a projection, and not whoever rosters him now.
        st.caption("Positional scarcity: of the top players at each position, who was "
                   "kept at the draft (and by whom) vs. who went into the pool.")
        pid_owner = {str(x["player_id"]): config.manager_name(o)
                     for o, picks in draft_keepers().items() for x in picks if x.get("player_id")}
        kept = set(pid_owner)
    else:
        st.caption("Positional scarcity: of the top players at each position, who's "
                   "likely kept (and by whom) vs. left in the draft pool. Thin pools "
                   "= positions to target early; deep pools = wait.")
        kept = _projected_kept_ids()
        pid_owner = {}
    for o, pids in ({} if done else CANDS).items():
        for pid in pids:
            pid_owner[str(pid)] = config.manager_name(o)
    name_idx = get_name_index()
    by_pos = {p: [] for p in ("RB", "WR", "QB", "TE")}
    seen = set()
    for _, ar in ADP_DF.iterrows():
        pos, rank = ar.get("position"), ar.get("consensus_rank")
        if pos not in by_pos or pd.isna(rank):
            continue
        pid = name_idx.get(normalize_name(ar["name"]), "")
        if not pid or str(pid) in seen:
            continue
        seen.add(str(pid))
        owner = pid_owner.get(str(pid)) if str(pid) in kept else None
        by_pos[pos].append((int(rank), ar["name"], str(pid), owner))

    tabs = st.tabs(["RB", "WR", "QB", "TE"])
    for tab, pos in zip(tabs, ["RB", "WR", "QB", "TE"]):
        with tab:
            players = sorted(by_pos[pos], key=lambda x: x[0])[:18]
            kept_n = sum(1 for *_, o in players if o)
            avail_n = len(players) - kept_n
            tone = "thin" if avail_n <= len(players) * 0.35 else ("moderate" if avail_n <= len(players) * 0.6 else "deep")
            st.caption(f"Top {len(players)} {pos}s — **{kept_n} {'kept' if done else 'likely kept'}**, "
                       f"**{avail_n} available**. Draft pool: {tone}.")
            rows = []
            for rank, nm, pid, owner in players:
                if owner:
                    status = f'<span style="color:#b3235a;">kept · {owner}</span>'
                else:
                    status = '<span class="kept-badge">AVAILABLE</span>'
                rows.append(
                    f'<tr><td class="rk">{rank}</td>'
                    f'<td class="pl">{theme.img_tag(pid)}{nm}</td>'
                    f'<td>{status}</td></tr>'
                )
            head = '<tr><th>ADP</th><th>Player</th><th>Status</th></tr>'
            st.markdown('<div class="neonwrap"><table class="lb"><thead>' + head
                        + '</thead><tbody>' + "".join(rows) + '</tbody></table></div>',
                        unsafe_allow_html=True)


def render_adp_trends() -> None:
    st.markdown('<h2 class="two-tone">ADP <span class="g">Risers &amp; Fallers</span></h2>', unsafe_allow_html=True)
    win = st.selectbox("Window", [7, 14, 30], format_func=lambda d: f"Last {d} days", key="adp_win")
    # getattr guard: a stale cached consensus module (Streamlit Cloud hot rerun)
    # may not yet have adp_movement; treat as "no history yet" rather than crash.
    _mv_fn = getattr(adp_consensus, "adp_movement", None)
    mv = _mv_fn(SEASON, window_days=win) if _mv_fn else {"moves": []}
    if not mv.get("moves"):
        st.info("Collecting ADP history — risers & fallers show up once there are "
                "two daily snapshots. A snapshot is saved with each daily ADP refresh, "
                "so check back tomorrow.")
        return
    st.caption(f"Consensus-ADP movement **{mv['prior']} → {mv['latest']}**, limited to the "
               f"top {DRAFT_SCOPE_RANK} by current consensus ADP (the realistic draft pool). "
               "▲ = climbing draft boards (being drafted earlier).")
    # Only players currently inside the draft pool — deep-waiver churn isn't useful.
    moves = [m for m in mv["moves"] if abs(m["delta"]) >= 1 and m["now"] <= DRAFT_SCOPE_RANK]
    if not moves:
        st.info(f"No top-{DRAFT_SCOPE_RANK} players moved over this window yet.")
        return
    # Split by direction so a faller never lands in the risers column (and vice versa).
    risers = sorted([m for m in moves if m["delta"] > 0], key=lambda x: -x["delta"])[:15]
    fallers = sorted([m for m in moves if m["delta"] < 0], key=lambda x: x["delta"])[:15]

    def _tbl(data):
        body = []
        for m in data:
            d = m["delta"]
            color = "#1c9b63" if d > 0 else "#b3235a"
            arrow = "▲" if d > 0 else "▼"
            body.append(
                f'<tr><td class="pl">{m["name"]} <span style="font-size:10px;color:#8a7fb3;">{m["pos"]}</span></td>'
                f'<td class="num">{m["was"]}→{m["now"]}</td>'
                f'<td class="num" style="color:{color};font-weight:700;">{arrow}{abs(d)}</td></tr>')
        return ('<table class="lb"><thead><tr><th>Player</th><th>ADP</th><th>Move</th>'
                '</tr></thead><tbody>' + "".join(body) + "</tbody></table>")

    c1, c2 = st.columns(2)
    c1.markdown("##### Risers")
    c1.markdown(_tbl(risers), unsafe_allow_html=True)
    c2.markdown("##### Fallers")
    c2.markdown(_tbl(fallers), unsafe_allow_html=True)


def render_draft_capital() -> None:
    st.markdown('<h2 class="two-tone">Draft <span class="g">Capital</span> &amp; Keeper Cost</h2>',
                unsafe_allow_html=True)
    _, locked = keeper_lock()
    st.caption("What each team brings to the draft after keepers: picks they'll "
               "actually make, future-pick stash, and a win-now vs. rebuild lean. "
               + ("Tap a team to see their locked keepers." if locked else
                  "Tap a team to see their full keeper contracts."))
    rows = []
    for o in MANAGERS:
        kr = team_keeper_rows(o)
        nk = len(kr)
        p26 = sum(get_owned_for(SEASON).get(o, {}).values())
        p27 = sum(get_owned_for(SEASON + 1).get(o, {}).values())
        p28 = sum(get_owned_for(SEASON + 2).get(o, {}).values())
        draftable = max(0, p26 - nk)
        kval = sum(int(r.get("Value", 0)) for r in kr)
        net_future = (p27 - DRAFT_ROUNDS) + (p28 - DRAFT_ROUNDS)
        if net_future >= 2:
            lean, lean_cls = "Rebuild", "rebuild"
        elif net_future <= -2 or draftable <= 8:
            lean, lean_cls = "Win-Now", "win-now"
        else:
            lean, lean_cls = "Balanced", "balanced"
        rows.append((o, config.manager_name(o), nk, kval, p26, draftable, p27, p28, lean, lean_cls))
    rows.sort(key=lambda x: -x[3])  # by keeper value
    max_abs = max((abs(r[3]) for r in rows), default=1) or 1

    cards = []
    for i, (o, nm, nk, kval, p26, dr, p27, p28, lean, lean_cls) in enumerate(rows, 1):
        pct = max(4, round(100 * abs(kval) / max_abs))
        val_cls = "val-pos" if kval >= 0 else "val-neg"
        df = build_candidate_rows(o)
        if locked:
            kept_ids = {s.get("player_id") for s in manager_submitted(o)}
            df = df[df["player_id"].isin(kept_ids)]
        body = (_contract_cards_grid_html(df) if not df.empty
                else '<p class="empty-note">Nothing submitted.</p>')
        cards.append(
            f'<details class="dc-row">'
            f'<summary>'
            f'<span class="dc-rank">{i}</span>'
            f'<span class="dc-main"><b>{nm}</b>'
            f'<span class="dc-meta">'
            f'<span class="chip {lean_cls}">{lean}</span>'
            f'<span class="chip">{nk} keepers</span>'
            f'<span class="chip">{dr}/{p26} picks {SEASON}</span>'
            f'<span class="chip">{p27} &middot; {p28} future</span>'
            f'</span></span>'
            f'<span class="dc-stat"><b class="{val_cls}">{kval:+d}</b><small>Keeper Val</small>'
            f'<span class="dc-bar"><span class="{val_cls}" style="width:{pct}%"></span></span></span>'
            f'</summary>'
            f'<div class="dc-body">{body}</div>'
            f'</details>'
        )
    st.markdown('<div class="dc-list">' + "".join(cards) + '</div>', unsafe_allow_html=True)
    st.caption(f"Picks {SEASON} = total owned / actually draftable after keepers. {SEASON+1} · "
               f"{SEASON+2} future = total picks owned those years ({DRAFT_ROUNDS} = untouched). "
               "Lean: hoarding future picks → rebuild; sold future/early picks or thin on this "
               "year's picks → win-now.")


_DEFAULT_LOTTERY_WEIGHTS = [640, 320, 160, 80, 40, 20, 8, 4, 2, 1]


def _lottery_weights() -> list:
    """Read straight from config.load() (always present) rather than a newer
    config.* function — so a stale cached config module on Streamlit Cloud
    (which doesn't reload on a hot rerun) can't AttributeError here."""
    try:
        w = config.load().get("lottery", {}).get("weights")
        return [int(x) for x in w] if w else list(_DEFAULT_LOTTERY_WEIGHTS)
    except (ValueError, TypeError):
        return list(_DEFAULT_LOTTERY_WEIGHTS)


def _lottery_rules_caption() -> str:
    w = _lottery_weights()
    return (f"**{SEASON}'s results set the {SEASON+1} draft lottery.** \"Chase for the Pick\" "
            f"winner (the consolation bracket's champion) gets the most balls ({w[0]}); the "
            f"league champion gets the fewest ({w[-1]}); the remaining 8 teams are seeded by "
            f"regular-season record, worst to best, at {', '.join(str(x) for x in w[1:-1])} "
            "balls. The draw sets a **selection order** — 1st choice picks any draft slot they "
            "want, 2nd choice picks from what's left, and so on — not a slot directly.")


def _lottery_bar_panels(items: list, eyebrow: str, weight_label: str = "Weight",
                         weight_fmt=lambda w: f"{w:g}") -> None:
    """Shared bar-chart rendering for all three lottery states (pre-season,
    live, and final) — `items` is [(name, weight, sub_html), ...], any
    ordering; sorted here by weight descending so every state looks and
    behaves the same regardless of where its numbers come from."""
    items = sorted(items, key=lambda x: -x[1])
    max_weight = max(w for _, w, _ in items) or 1
    rows = "".join(
        f'<div class="lot-row"><div class="lot-label"><b>{name}</b><small>{sub}</small></div>'
        f'<div class="lot-track"><div class="lot-fill" style="width:{max(round(100 * w / max_weight), 3)}%">'
        f'{weight_fmt(w)}</div></div><div class="lot-pos">#{i + 1}</div></div>'
        for i, (name, w, sub) in enumerate(items)
    )
    st.markdown(
        f'<div class="lot-wrap"><div class="lot-head"><h4>{weight_label}</h4>'
        f'<span class="lot-eyebrow">{eyebrow}</span></div>{rows}</div>',
        unsafe_allow_html=True,
    )


def render_lottery() -> None:
    from kreeper import lottery
    st.markdown(f'<h2 class="two-tone">Draft-Order <span class="g">Lottery</span></h2>', unsafe_allow_html=True)
    st.caption("Weighted odds set next season's draft position directly.")
    st.caption(_lottery_rules_caption())

    complete = lottery.season_is_complete()
    if not complete:
        _render_lottery_live_projection()
    else:
        _render_lottery_conduct()


def _render_lottery_live_projection() -> None:
    from kreeper import lottery
    proj = lottery.live_projection()
    if not any(r["wins"] + r["losses"] for r in proj["rows"]):
        _render_lottery_preseason_projection()
        return
    st.caption("**Live approximation** — shifts every week until the season ends: seeds "
               "the top/next groups by CURRENT record, then models each bracket's winner by "
               "this season's win% and points scored. The real weights lock in once both "
               "brackets finish.")
    items = [(
        config.manager_name(r["owner"]), r["expected_weight"],
        f'{r["wins"]}-{r["losses"]} · {r["pf"]} PF · {r["p_chase_winner"]*100:.0f}% chase-bound'
    ) for r in proj["rows"]]
    _lottery_bar_panels(items, eyebrow="Live projection · current record",
                         weight_label="Projected Ball Weights", weight_fmt=lambda w: f"{w:g}")
    st.caption("Proj. Balls = a blended expected weight (P(champ)×lowest + P(chase)×highest + "
               "P(neither)×the standings-tier weight at your current rank). For sorting/vibes "
               "only — the real draw only uses the final, locked weights below once the season ends.")


def _render_lottery_preseason_projection() -> None:
    """No games played yet, so there's no record to project from — fall back
    to the same pre-season power score the Title Odds page uses (3 seasons
    of history blended with keeper strength/value)."""
    st.caption("Pre-season approximation — no games played yet.")
    odds = build_championship_odds()  # best (title favorite) to worst
    if not odds:
        st.info("Nothing to project lottery odds from yet — check back once games have been played.")
        return
    weights = _lottery_weights()
    n = len(odds)
    items = []
    for rank, r in enumerate(odds):  # rank 0 = best power score
        if rank == 0:
            w, basis = weights[-1], "Title favorite"
        elif rank == n - 1:
            w, basis = weights[0], "Weakest power score"
        else:
            w, basis = weights[min(rank, len(weights) - 2)], "Power rank"
        items.append((r["Team"], w, basis))
    _lottery_bar_panels(items, eyebrow="Pre-season projection · power score",
                         weight_label="Projected Ball Weights", weight_fmt=lambda w: f"{w:g}")
    st.caption("Power rank = this year's Title Odds model (3-yr history + keeper strength/value). "
               "Purely for early-offseason vibes — the real weights lock in once the season ends.")


def _render_lottery_conduct() -> None:
    from kreeper import lottery
    tiers = lottery.final_tiers()
    if not tiers:
        st.error("Season shows complete but tiers couldn't be computed — check the winners/"
                 "losers bracket on Sleeper.")
        return

    total = sum(t["weight"] for t in tiers.values())
    items = [(config.manager_name(o), info["weight"], info["tier"]) for o, info in tiers.items()]
    _lottery_bar_panels(items, eyebrow="Weighted by final standing",
                         weight_label="Final Ball Weights", weight_fmt=lambda w: f"{w:g}")
    st.caption(f"{total} balls total.")

    weights = {o: info["weight"] for o, info in tiers.items()}
    probs = lottery.position_probabilities(weights)
    order_by_weight = sorted(tiers, key=lambda o: -tiers[o]["weight"])
    n = len(order_by_weight)

    st.markdown("##### Odds at 1st choice")
    st.caption("Quick-scan favorite — the full position-by-position breakdown is below.")
    bar_rows = "".join(
        f'<div class="lot-row"><div class="lot-label"><b>{config.manager_name(o)}</b>'
        f'<small>{tiers[o]["tier"]} · {tiers[o]["weight"]} balls</small></div>'
        f'<div class="lot-track"><div class="lot-fill" style="width:{max(probs[o][0]*100, 1.5):.1f}%">'
        f'{probs[o][0]*100:.1f}%</div></div>'
        f'<div class="lot-pos">#{i+1}</div></div>'
        for i, o in enumerate(order_by_weight)
    )
    st.markdown(f'<div class="lot-wrap">{bar_rows}</div>', unsafe_allow_html=True)

    st.markdown("##### Full odds — every selection position")
    st.caption("Each team's exact chance at each selection position (1st choice through last).")
    head = '<tr><th>Team</th>' + "".join(f'<th>{i+1}{"st" if i==0 else "nd" if i==1 else "rd" if i==2 else "th"}</th>' for i in range(n)) + '</tr>'
    body = "".join(
        f'<tr><td class="pl">{config.manager_name(o)}</td>'
        + "".join(f'<td class="num">{probs[o][i]*100:.1f}%</td>' for i in range(n))
        + '</tr>'
        for o in order_by_weight
    )
    st.markdown('<div class="neonwrap" style="overflow-x:auto;"><table class="lb" style="font-size:12px;">'
                '<thead>' + head + '</thead><tbody>' + body + '</tbody></table></div>',
                unsafe_allow_html=True)

    st.markdown("##### Conduct the lottery")
    record = lottery.load_record(SEASON)
    draw = record.get("draw_order")

    if not draw:
        st.caption("Nobody's run the draw yet. This is a single random weighted pick without "
                   "replacement, live — refresh-proof once it's run (saved immediately).")
        if st.button("Run the lottery", type="primary"):
            drawn = lottery.draw_order(weights)
            record = {"season": SEASON, "weights": weights, "tiers": tiers,
                      "draw_order": drawn, "slot_picks": {}}
            lottery.save_record(record, SEASON)
            st.rerun()
        return

    st.success("The lottery has been run — this order is locked in.")
    st.markdown("###### Selection order (1st choice → last)")
    rev = "".join(
        f'<div class="draw-row"><span class="pickno">{i+1}</span>'
        f'<div><div class="who">{config.manager_name(o)}</div>'
        f'<div class="sub">{tiers.get(o, {}).get("tier", "")} · {weights.get(o, "?")} balls</div></div></div>'
        for i, o in enumerate(draw)
    )
    st.markdown(f'<div class="draw-list">{rev}</div>', unsafe_allow_html=True)

    st.markdown("###### Pick your slot")
    st.caption("In the order above, each team picks their actual draft slot from what's left. "
               "Once all 10 are in, carry this order into next season's `config.yaml` "
               "`draft_order` when the new season starts.")
    picks: dict = dict(record.get("slot_picks", {}))
    taken_slots = set(picks.values())
    for i, o in enumerate(draw):
        name = config.manager_name(o)
        if o in picks:
            st.markdown(f"**#{i+1}. {name}** → Draft Slot **{picks[o]}** ✓")
            continue
        if i > 0 and draw[i-1] not in picks:
            st.markdown(f"#{i+1}. {name} — waiting on the picks ahead.")
            break
        avail = [s for s in range(1, len(draw) + 1) if s not in taken_slots]
        c1, c2 = st.columns([3, 1])
        choice = c1.selectbox(f"#{i+1}. {name} picks their slot", avail, key=f"lottery_slot_{o}")
        if c2.button("Confirm", key=f"lottery_confirm_{o}"):
            picks[o] = choice
            record["slot_picks"] = picks
            lottery.save_record(record, SEASON)
            st.rerun()
        break

    if len(picks) == len(draw):
        st.balloons()
        st.markdown("###### Final draft order")
        final_rows = "".join(
            f'<tr><td class="rk">{slot}</td><td class="pl">{config.manager_name(o)}</td></tr>'
            for o, slot in sorted(picks.items(), key=lambda kv: kv[1])
        )
        st.markdown('<div class="neonwrap"><table class="lb"><thead>'
                    '<tr><th>Slot</th><th>Team</th></tr></thead><tbody>'
                    + final_rows + '</tbody></table></div>', unsafe_allow_html=True)

    if st.button("Reset the lottery (redo)", help="Clears the draw and any slot picks made so far."):
        lottery.save_record({}, SEASON)
        st.rerun()


def render_roster_needs() -> None:
    st.markdown('<h2 class="two-tone">Roster <span class="g">Needs</span></h2>', unsafe_allow_html=True)
    st.caption("After likely keepers, the starting spots each team still has to draft. "
               "green = set · amber = one short · red = multiple holes.")
    from collections import Counter
    slots = starter_slots()
    need = Counter(s for s in slots if s in ("QB", "RB", "WR", "TE"))
    n_start = len([s for s in slots])
    cols_pos = ["QB", "RB", "WR", "TE"]

    def cell(have, req):
        gap = req - have
        bg = "#1c9b63" if gap <= 0 else ("#d98a00" if gap == 1 else "#b3235a")
        return (f'<td class="num"><span style="background:{bg};color:#fff;padding:2px 9px;'
                f'border-radius:6px;">{have}/{req}</span></td>')

    body = []
    for o in MANAGERS:
        kr = team_keeper_rows(o)
        pc = Counter(r["Pos"] for r in kr)
        filled, flex_left = 0, sum(1 for s in slots if s == "FLEX")
        for p in ("QB", "RB", "WR", "TE"):
            use = min(pc.get(p, 0), need.get(p, 0))
            filled += use
            overflow = pc.get(p, 0) - use
            if p in ("RB", "WR", "TE"):
                take = min(overflow, flex_left)
                filled += take
                flex_left -= take
        cells = "".join(cell(pc.get(p, 0), need.get(p, 0)) for p in cols_pos)
        body.append(f'<tr><td class="pl">{config.manager_name(o)}</td>{cells}'
                    f'<td class="num">{filled}/{n_start}</td></tr>')
    head = ('<tr><th>Team</th>' + "".join(f"<th>{p}</th>" for p in cols_pos)
            + '<th>Starters&nbsp;Set</th></tr>')
    st.markdown('<div class="neonwrap"><table class="lb"><thead>' + head
                + '</thead><tbody>' + "".join(body) + '</tbody></table></div>',
                unsafe_allow_html=True)
    st.caption(f"Each cell = keepers / starters needed at that position ({dict(need)}). "
               "Starters Set counts FLEX filled by extra RB/WR/TE.")


@st.cache_data(ttl=86400 * 7, show_spinner=False)
def _season_stats(yr: int) -> dict:
    """player_id -> season stat line (pos_rank_ppr...). Disk-cached + resilient so a
    flaky/slow fetch never blocks the page (this machine's urllib3 can hang)."""
    import json as _json
    import requests
    p = config.DATA_DIR / f"cache_stats_{yr}.json"
    if p.exists():
        try:
            return _json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            pass
    try:
        r = requests.get(f"https://api.sleeper.app/v1/stats/nfl/regular/{yr}",
                         headers={"User-Agent": "babies-and-boomer/1.0"}, timeout=15)
        r.raise_for_status()
        data = r.json() or {}
    except Exception:  # noqa: BLE001
        return {}
    try:
        p.write_text(_json.dumps(data))
    except Exception:  # noqa: BLE001
        pass
    return data


@st.cache_data(ttl=3600, show_spinner="Grading old keeper calls…")
def build_keeper_hitrate():
    thresh = {"QB": 12, "RB": 24, "WR": 30, "TE": 12}
    stats = {}
    per_owner, decisions = {}, []
    for yr in range(SEASON - 3, SEASON):
        ss = stats.get(yr) or _season_stats(yr)
        stats[yr] = ss
        for oid, picks in storage.load(yr).items():
            for s in picks:
                pid = s.get("player_id")
                if not pid:
                    continue
                pos = H.player_meta(pid).position
                if pos not in thresh:
                    continue
                pr = (ss.get(str(pid)) or {}).get("pos_rank_ppr")
                if pr is None:
                    continue
                hit = pr <= thresh[pos]
                d = per_owner.setdefault(oid, {"hit": 0, "tot": 0})
                d["hit"] += 1 if hit else 0
                d["tot"] += 1
                decisions.append({"owner": oid, "season": yr,
                                  "name": s.get("player_name") or H.player_meta(pid).name,
                                  "pos": pos, "fin": int(pr), "hit": hit})
    return per_owner, decisions


def render_keeper_hitrate() -> None:
    st.markdown('<h2 class="two-tone">Keeper <span class="g">Hit-Rate</span></h2>', unsafe_allow_html=True)
    st.caption("Did past keepers pay off? A keep \"hits\" if the player finished a "
               "startable positional rank that season (QB/TE top-12, RB top-24, WR top-30).")
    per_owner, decisions = build_keeper_hitrate()
    if not decisions:
        st.info("No prior keeper seasons on record yet (or season stats unavailable).")
        return
    rows = []
    for oid, d in sorted(per_owner.items(), key=lambda kv: -(kv[1]["hit"] / max(1, kv[1]["tot"]))):
        rate = d["hit"] / max(1, d["tot"])
        rows.append(f'<tr><td class="pl">{config.manager_name(oid)}</td>'
                    f'<td class="num">{d["hit"]}/{d["tot"]}</td>'
                    f'<td class="num" style="font-weight:700;color:{"#1c9b63" if rate>=.5 else "#b3235a"};">'
                    f'{rate*100:.0f}%</td></tr>')
    st.markdown('##### Manager hit-rate (last 3 seasons)')
    st.markdown('<table class="lb"><thead><tr><th>Manager</th><th>Hits</th><th>Rate</th>'
                '</tr></thead><tbody>' + "".join(rows) + '</tbody></table>', unsafe_allow_html=True)
    best = sorted(decisions, key=lambda x: x["fin"])[:6]
    worst = sorted([d for d in decisions if not d["hit"]], key=lambda x: -x["fin"])[:6]
    c1, c2 = st.columns(2)
    c1.markdown("##### Best keeper calls")
    c1.markdown("\n".join(
        f'- **{d["name"]}** ({d["pos"]}{d["fin"]}, {d["season"]}) · {config.manager_name(d["owner"]).split()[0]}'
        for d in best))
    c2.markdown("##### Coldest keeps")
    c2.markdown("\n".join(
        f'- **{d["name"]}** ({d["pos"]}{d["fin"]}, {d["season"]}) · {config.manager_name(d["owner"]).split()[0]}'
        for d in worst))


def render_superlatives() -> None:
    st.markdown('<h2 class="two-tone">Superlatives</h2>', unsafe_allow_html=True)
    cards = []

    def card(title, who, sub):
        cards.append(f'<div class="kcard"><h4>{title}</h4>'
                     f'<div class="who">{who}</div><div class="sub">{sub}</div></div>')

    lb = build_value_leaderboard(400)
    if not lb.empty:
        top = lb.sort_values("Value", ascending=False).iloc[0]
        card("Biggest Keeper Steal", top["Player"],
             f'{top["Team"]} · keep R{top["Cost Rd"]} vs ADP {top["ADP"]} (+{int(top["Value"])})')

    odds = build_championship_odds()
    if odds:
        card("Title Favorite", odds[0]["Team"], f'{odds[0]["Odds"]} · {odds[0]["Win %"]}%')

    cap = []
    for o in MANAGERS:
        nk = len(team_keeper_rows(o))
        p26 = sum(get_owned_for(SEASON).get(o, {}).values())
        cap.append((config.manager_name(o), max(0, p26 - nk), p26))
    allin = min(cap, key=lambda x: x[1])
    deep = max(cap, key=lambda x: x[2])
    card("Most All-In", allin[0], f'only {allin[1]} picks left to draft')
    card("Deepest War Chest", deep[0], f'{deep[2]} draft picks in {SEASON}')

    seasons, agg = build_record_book()
    champ = max(agg.items(), key=lambda kv: (kv[1]["titles"], kv[1]["w"]))
    if champ[1]["titles"]:
        card("Most Titles", config.manager_name(champ[0]), f'{champ[1]["titles"]} championship(s)')
    runner = max(agg.items(), key=lambda kv: (kv[1]["runner"], -kv[1]["titles"]))
    if runner[1]["runner"] and not runner[1]["titles"]:
        card("Always a Bridesmaid", config.manager_name(runner[0]),
             f'{runner[1]["runner"]} finals, 0 titles')
    best_rec = max(agg.items(), key=lambda kv: kv[1]["w"] / max(1, kv[1]["w"] + kv[1]["l"]))
    card("Best All-Time Record", config.manager_name(best_rec[0]),
         f'{best_rec[1]["w"]}-{best_rec[1]["l"]}')
    st.markdown('<div class="kcards">' + "".join(cards) + "</div>", unsafe_allow_html=True)


def _mock_rookie_factor() -> float:
    """Read the rookie premium straight from config.load() (always present) rather
    than a newer config.* function — so a stale cached config module on Streamlit
    Cloud (which doesn't reload on a hot rerun) can't AttributeError here."""
    try:
        return float(config.load().get("mock_draft_rookie_factor", 0.4))
    except (ValueError, TypeError):
        return 0.4


def build_mock_draft(rookie_factor: float | None = None) -> pd.DataFrame:
    """A full projected draft board: each team's likely KEEPERS occupy their pick
    slots, and every other pick is filled by the best available player (ADP with
    our league's rookie premium). Accounts for traded picks via the real board."""
    if rookie_factor is None:
        rookie_factor = _mock_rookie_factor()
    board = get_board()
    cells, rounds = board["cells"], board["rounds"]
    owner_to_roster = board["owner_to_roster"]

    # 1) Place each team's projected keepers onto a pick they OWN (their keeper
    #    cost round, or the nearest owned pick), marking those pick numbers.
    keeper_at = {}     # pick_no -> {player, pos, adp, owner}
    kept_ids, used = set(), set()
    for o in MANAGERS:
        rid = owner_to_roster.get(str(o))
        owned = {}     # round -> [pick_no]
        for (r, _slot), c in cells.items():
            if c["owner_roster"] == rid:
                owned.setdefault(r, []).append(c["pick_no"])
        for k in sorted(team_keeper_rows(o), key=lambda x: (x.get("Cost Rd") or 99)):
            kept_ids.add(str(k["_pid"]))
            rd = int(k.get("Cost Rd") or rounds)
            cand = [rd] + [rd - i for i in range(1, rd)] + [rd + i for i in range(1, rounds)]
            spot = next((pn for cr in cand for pn in owned.get(cr, []) if pn not in used), None)
            if spot is not None:
                used.add(spot)
                keeper_at[spot] = {"player": k["Player"], "pos": k["Pos"], "pid": str(k["_pid"]),
                                   "adp": k.get("ADP"), "owner": config.manager_name(o)}

    # 2) Available pool: ADP-ranked, keepers removed, league rookie premium applied.
    name_idx, pool, seen = get_name_index(), [], set()
    for _, ar in ADP_DF.iterrows():
        pos, rank = ar.get("position"), ar.get("consensus_rank")
        if pos not in ("QB", "RB", "WR", "TE") or pd.isna(rank):
            continue
        pid = name_idx.get(normalize_name(ar["name"]), "")
        if not pid or str(pid) in kept_ids or str(pid) in seen:
            continue
        seen.add(str(pid))
        rookie = _years_exp(pid) == 0
        pool.append((float(rank) * (rookie_factor if rookie else 1.0), str(pid),
                     ar["name"], pos, int(rank), rookie))
    pool.sort(key=lambda x: x[0])

    # 3) Walk the board in pick order; keeper cells = keepers, else next available.
    rows, pi = [], 0
    for (r, slot), c in sorted(cells.items(), key=lambda kv: kv[1]["pick_no"]):
        pn = c["pick_no"]
        base = {"Pick": pn, "Round": r, "Slot": slot, "Team": c["owner_name"]}
        if pn in keeper_at:
            k = keeper_at[pn]
            rows.append({**base, "_pid": k["pid"], "Player": k["player"], "Pos": k["pos"],
                         "ADP": k["adp"], "Rookie": False, "Keeper": True})
        elif pi < len(pool):
            _adj, pid, nm, pos, adp, rk = pool[pi]
            pi += 1
            rows.append({**base, "_pid": pid, "Player": nm, "Pos": pos,
                         "ADP": adp, "Rookie": rk, "Keeper": False})
    return pd.DataFrame(rows)


def render_mock_draft() -> None:
    st.markdown('<h2 class="two-tone">Projected <span class="g">Draft</span></h2>', unsafe_allow_html=True)
    st.caption("A full projected board: each team's likely keepers (locked in, declared + "
               "best by value) sit in their pick slots, and every other pick is the "
               "best available by consensus ADP with our league's rookie premium.")
    rf = _mock_rookie_factor()
    c1, c2 = st.columns([2, 1])
    with c1:
        rf = st.slider("Rookie premium (lower = rookies go higher)", 0.15, 1.0,
                       value=float(rf), step=0.05,
                       help="A rookie's draft rank = ADP rank × this. 1.0 = no premium.")
    df = build_mock_draft(rf)
    if df.empty:
        st.info("No ADP data yet — run `python scripts/refresh_adp.py`.")
        return
    only_rd = c2.selectbox("Show round", ["Full board (all rounds)", "First 3 rounds"]
                           + [f"Round {r}" for r in range(1, DRAFT_ROUNDS + 1)])
    if only_rd.startswith("Full board"):
        view = df
    elif only_rd == "First 3 rounds":
        view = df[df["Round"] <= 3]
    else:
        view = df[df["Round"] == int(only_rd.split()[1])]
    rows = []
    multi_round = view["Round"].nunique() > 1
    cur_round = None
    for _, r in view.iterrows():
        if multi_round and int(r["Round"]) != cur_round:
            cur_round = int(r["Round"])
            rows.append(f'<tr class="rd-sep"><td colspan="5">Round {cur_round}</td></tr>')
        keep = bool(r.get("Keeper"))
        tag = (' <span class="kept-badge">KEEP</span>' if keep
               else (' <span class="rk-badge">RK</span>' if r["Rookie"] else ""))
        adp = "" if (keep or not r["ADP"]) else r["ADP"]
        tr = ' style="background:rgba(255,206,31,.18);"' if keep else ""
        rows.append(
            f'<tr{tr}><td class="rk">{int(r["Round"])}.{int(r["Slot"]):02d}</td>'
            f'<td class="pl">{theme.img_tag(r["_pid"])}{r["Player"]}{tag}</td>'
            f'<td class="pos"><span class="posdot p-{r["Pos"]}"></span>{r["Pos"]}</td>'
            f'<td>{r["Team"]}</td>'
            f'<td class="num">{adp}</td></tr>'
        )
    head = '<tr><th>Pick</th><th>Player</th><th>Pos</th><th>On the clock</th><th>ADP</th></tr>'
    st.markdown('<div class="neonwrap"><table class="lb lb-mock"><thead>' + head
                + '</thead><tbody>' + "".join(rows) + '</tbody></table></div>',
                unsafe_allow_html=True)
    st.caption("**KEEP** = a kept player (occupies that pick) · everyone else = projected "
               "pick by ADP. **RK** = rookie. Tune the rookie premium above to match "
               "how your league really values rookies.")


def render_my_keepers() -> None:
    st.markdown('<h3>Set Your <span class="g">Keepers</span></h3>', unsafe_allow_html=True)
    deadline, locked = keeper_lock()
    if locked:
        st.warning(f"Keeper submissions closed on **{deadline:%b %d, %Y · %-I:%M %p}**. "
                   "The board is final — selections are read-only.")
    elif deadline:
        st.caption(f"Submissions close **{deadline:%b %d, %Y · %-I:%M %p}**.")

    # Start on the team this device picked (masthead dropdown), if any.
    _names = list(NAME_TO_ID.keys())
    _mine = _me()
    _idx = _names.index(MANAGERS[_mine]["name"]) if _mine and MANAGERS[_mine]["name"] in _names else None
    name = st.selectbox("Who are you?", _names, index=_idx,
                        placeholder="Pick your name…")
    if not name:
        st.info("Select your name to load your roster.")
        return

    owner_id = NAME_TO_ID[name]

    if locked:
        saved = manager_submitted(owner_id)
        if not saved:
            st.info(f"{name} didn't submit any keepers before the deadline.")
            return
        st.markdown("##### Your locked keepers")
        kept_ids = {s.get("player_id") for s in saved}
        df = build_candidate_rows(owner_id)
        df = df[df["player_id"].isin(kept_ids)]
        render_contract_cards(name, df, show_title=False)
        return

    df = build_candidate_rows(owner_id)
    if df.empty:
        st.warning("No skill-position players found on your roster.")
        return
    render_contract_cards(name, df)

    saved = {s["player_id"]: s for s in manager_submitted(owner_id)}
    df["Keep"] = df["player_id"].map(lambda p: p in saved)
    df["Rookie Keeper"] = df["player_id"].map(
        lambda p: bool(saved.get(p, {}).get("is_rookie_keeper", False)))

    st.caption("Tick **Keep** for players you want to keep. Tick **Rookie Keeper** "
               "for career-long rookie keepers (kept at your last rounds, exempt from the 3-year clock).")
    edited = st.data_editor(
        df,
        key=f"editor_{owner_id}",
        hide_index=True,
        use_container_width=True,
        column_order=["Keep", "Rookie Keeper", "Photo", "Player", "Pos", "NFL",
                      "Keep Year", "Reg. Cost", "ADP Rank", "Orig. Rd", "Acq."],
        column_config={
            "player_id": None,
            "Eligible": None,
            "Photo": st.column_config.ImageColumn("", width="small"),
            "Keep": st.column_config.CheckboxColumn("Keep", width="small"),
            "Rookie Keeper": st.column_config.CheckboxColumn("Rookie Keeper", width="small"),
            "ADP Rank": st.column_config.NumberColumn("ADP Rank", help="Consensus overall ADP rank"),
            "Orig. Rd": st.column_config.NumberColumn("Orig. Rd", help="Round originally drafted"),
        },
        disabled=["Photo", "Player", "Pos", "NFL", "Keep Year", "Reg. Cost", "ADP Rank", "Orig. Rd", "Acq."],
    )

    # Ticking Rookie Keeper auto-keeps the player — no need to tick both.
    picked = edited[edited["Keep"] | edited["Rookie Keeper"]]

    st.markdown("##### Your keeper slip")
    st.caption("Tip: ticking **Rookie Keeper** keeps the player automatically — "
               "you don't need to also tick Keep.")

    items = []
    ineligible = []
    year2_choices = {}
    for _, r in picked.iterrows():
        pid = r["player_id"]
        is_rookie = bool(r["Rookie Keeper"])
        # A rookie keeper must have been drafted by THIS team in the player's
        # rookie season; a trade-acquired player can't be a rookie keeper.
        if is_rookie and not rookie_keeper_eligible(owner_id, pid):
            ineligible.append(
                f"**{r['Player']}** can't be a *rookie keeper* — you must have drafted "
                "them in their rookie season and held them since (this player was "
                "acquired by trade or not drafted by you as a rookie). Untick Rookie "
                "Keeper; keep them as a regular keeper if eligible."
            )
            continue
        prof = H.keeper_profile(owner_id, pid, SEASON)
        rank = adp_rank_for(r["Player"], r["Pos"])
        # Was a rookie keeper, now kept as a regular keeper. Under original_round
        # mode that costs their rookie draft round; the 3-year clock resets.
        from_rookie = ((not is_rookie) and _rookie_ledger_holds(owner_id, pid)
                       and not ever_regular_keeper(pid))
        if not is_rookie and not from_rookie:
            base = engine.compute(prof, adp_rank=rank, is_rookie_keeper=False)
            if not base.eligible:
                ineligible.append(f"**{r['Player']}** — {base.reason}")
                continue
            # Any keep year may now offer a choice (e.g. rule cost vs. cheaper ADP).
            opt_rounds = [o.round for o in base.options]
            if len([x for x in opt_rounds if x is not None]) > 1:
                labels = [o.label for o in base.options]
                ridx = opt_rounds.index(base.recommended_round) if base.recommended_round in opt_rounds else 0
                choice = st.radio(f"{r['Player']} — keeper cost (Year {base.keep_year})",
                                  labels, horizontal=True, index=ridx,
                                  key=f"cost_{owner_id}_{pid}")
                year2_choices[pid] = choice.split(" (")[0]
        items.append({
            "player_id": pid, "name": r["Player"], "position": r["Pos"],
            "is_rookie": is_rookie, "from_rookie": from_rookie, "profile": prof, "adp_rank": rank,
            "rookie_draft_round": rookie_draft_round(pid) if from_rookie else None,
            "year2_choice": year2_choices.get(pid),
        })

    costs = engine.allocate_keeper_costs(items, draft_rounds=DRAFT_ROUNDS,
                                         owned=owned_for(owner_id),
                                         rookie_owned=get_owned().get(owner_id))
    reg_items = [i for i in items if not i["is_rookie"]]
    rook_items = [i for i in items if i["is_rookie"]]

    summary = []
    for it in items:
        c = costs[it["player_id"]]
        summary.append({
            "Player": it["name"], "Pos": it["position"],
            "Type": "Rookie" if it["is_rookie"] else "Regular",
            "Keep Year": c.keep_year,
            "Cost": f"Round {c.recommended_round}" if c.recommended_round else c.recommended_label,
        })

    # Ownership eligibility: a keeper must cost a pick at its round or earlier (a
    # higher pick). allocate_keeper_costs flags anyone you can't actually keep.
    for it in items:
        c = costs[it["player_id"]]
        if not c.eligible or c.recommended_round is None:
            reason = c.reason or "no pick available to keep this player."
            ineligible.append(f"**{it['name']}** — {reason}")

    for msg in ineligible:
        st.error("Can't keep: " + msg)
    problems = []
    if len(reg_items) > MAX_REG:
        problems.append(f"Too many **regular** keepers: {len(reg_items)} (max {MAX_REG}).")
    if len(rook_items) > MAX_ROOKIE:
        problems.append(f"Too many **rookie** keepers: {len(rook_items)} (max {MAX_ROOKIE}).")

    if summary:
        st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
    st.caption(f"Regular: {len(reg_items)}/{MAX_REG} · Rookie: {len(rook_items)}/{MAX_ROOKIE}")
    for p in problems:
        st.warning(p)

    disabled = bool(problems or ineligible)
    if st.button("Save my keepers", type="primary", disabled=disabled):
        # Re-check server-side: the set must still be valid and the deadline open
        # (it could have passed, or another tab changed things, since page load).
        _, locked_now = keeper_lock()
        if locked_now:
            st.error("Submissions just closed — your changes weren't saved.")
        elif problems or ineligible:
            st.error("Fix the issues above before saving.")
        else:
            payload = []
            for it in items:
                c = costs[it["player_id"]]
                payload.append({
                    "player_id": it["player_id"], "player_name": it["name"], "position": it["position"],
                    "is_rookie_keeper": it["is_rookie"], "keep_year": c.keep_year,
                    "cost_choice": it.get("year2_choice"), "cost_round": c.recommended_round,
                })
            try:
                storage.save_manager_selections(owner_id, payload, SEASON)
                storage.append_log(owner_id, name, len(payload),
                                   dt.datetime.now().isoformat(timespec="seconds"), SEASON)
                st.success(f"Saved {len(payload)} keepers for {name}.")
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't save — try again in a moment. ({type(e).__name__})")


_POS_COLOR = {"QB": "var(--gold-d)", "RB": "var(--purple-l)", "WR": "var(--cyan)", "TE": "var(--red)"}
# Same four hues as _POS_COLOR, as raw rgb() triples for building translucent
# cell-shading rgba() below (CSS can't tint a var() color with an alpha).
_POS_RGB = {"QB": "201,151,0", "RB": "122,91,216", "WR": "35,144,192", "TE": "214,51,108"}


def _clean_pos(pos) -> str:
    """A stray NaN (a consensus-ADP row with no position for some
    source combination) stored straight into a logged pick renders as the
    literal string "nan" otherwise — pandas/JSON round-trip a float NaN
    right through an f-string. Anything that isn't a real position string
    becomes "", not text."""
    return pos if isinstance(pos, str) and pos.upper() in _POS_COLOR else ""


def _pos_span(pos: str) -> str:
    """A player's position, colored to match the posdot convention used
    everywhere else (ADP tables, contract cards) — lets a positional run
    jump out while scanning the draft grid instead of every filled cell
    reading as the same flat color."""
    pos = _clean_pos(pos)
    if not pos:
        return ""
    return f'<span style="font-weight:700;color:{_POS_COLOR[pos]};">{pos}</span>'


def _pos_cell_style(pos: str) -> str:
    """Shade a filled draft-grid cell by the position drafted — the same
    hues as _pos_span, now as the cell's own background/ring instead of
    just the position label, so a positional run is visible at a glance
    across the whole grid, not just on close reading."""
    rgb = _POS_RGB.get(_clean_pos(pos))
    if not rgb:
        return ""
    return f'background:rgba({rgb},.16);box-shadow:inset 0 0 0 1px rgba({rgb},.45);color:var(--ink);'


def _dbplayer_html(pid: str, name: str, pos: str, extra: str = "") -> str:
    """Small headshot + stacked name/position, the same treatment headshots
    already get everywhere else on the site (leaderboards, ADP, contract
    cards) — just sized down for the draft grid's tight cells. No pid (a
    D/ST or kicker pick, which the ADP/name index doesn't resolve) just
    skips the photo rather than showing a broken image. `extra` (a rookie-
    keeper badge, a cross-team owner tag) rides along in the text stack."""
    img = theme.img_tag(pid, cls="hs-sm") if pid else ""
    return (f'<div class="dbplayer">{img}<div class="dbplayer-txt">'
            f'<b>{name}</b><span class="pos">{_pos_span(pos)}{extra}</span></div></div>')


def _board_cell_html(c: dict, keepers: list) -> str:
    pick = f'<span class="dbpick">#{c["pick_no"]}</span>'
    if keepers:
        conflict = False
        parts = []
        for k in keepers:
            rk = ' <span class="rk-badge">RK</span>' if k.get("is_rookie_keeper") else ""
            # Keeper on an acquired pick (not their own column) -> tag the owner.
            tag = "" if k.get("_home") else f' <span style="font-size:9px;">({k.get("_owner_short","")})</span>'
            parts.append(_dbplayer_html(k.get("player_id", ""), k["player_name"],
                                        k.get("position", ""), rk + tag))
            conflict = conflict or k.get("_conflict")
        names = "".join(parts)
        if conflict:
            return (f'<td class="dbcell db-conflict">{pick}{names}'
                    f'<span style="font-size:9px;">no pick this round</span></td>')
        style = _pos_cell_style(keepers[0].get("position", ""))
        return f'<td class="dbcell" style="{style}">{pick}{names}</td>'
    if c["traded"]:
        return (f'<td class="dbcell db-traded">{pick}<br><b>{c["owner_short"]}</b><br>'
                f'<span style="font-size:9px;">◄ {c["base_short"]}</span></td>')
    return f'<td class="dbcell db-base">{pick}<br>{c["owner_short"]}</td>'


@st.cache_data(ttl=1800, show_spinner="Setting the line…")
def build_championship_odds():
    """A for-fun Vegas-style title line. Rosters reset at the draft, so the only
    thing that carries over is each team's KEEPERS — the model blends three
    seasons of results with keeper strength (talent retained) and keeper value
    (draft capital saved), then converts to win probabilities and American odds
    with a bookmaker's vig."""
    from kreeper import sleeper

    chain = sleeper.league_chain(LEAGUE["sleeper_league_id"])
    completed = [c["season"] for c in chain if c["season"] != SEASON]
    recency = dict(zip(sorted(completed, reverse=True), [0.5, 0.3, 0.2, 0.1, 0.05]))

    hist = {o: 0.0 for o in MANAGERS}       # recency-weighted win %
    record = {o: [0, 0] for o in MANAGERS}  # aggregate W, L over completed seasons
    for c in chain:
        if c["season"] not in recency:
            continue
        wt = recency[c["season"]]
        for r in sleeper.get_rosters(c["league_id"]):
            o = str(r.get("owner_id"))
            if o not in hist:
                continue
            stt = r.get("settings", {}) or {}
            w, l = stt.get("wins", 0) or 0, stt.get("losses", 0) or 0
            hist[o] += wt * (w / max(1, w + l))
            record[o][0] += w
            record[o][1] += l

    # Keeper-based strength: only the players a team can carry over matter. Take
    # each team's most valuable eligible keepers (their likely keep set) and
    # measure the talent retained (ADP) and the draft capital saved (value).
    lb = build_value_leaderboard(400)
    keep_n = MAX_REG + MAX_ROOKIE
    pos_cap = position_keeper_caps()
    talent, kcap, best = {}, {}, {}
    for o in MANAGERS:
        team = lb[lb["Team"] == config.manager_name(o)]
        sel = _select_keepers(team, keep_n, pos_cap)  # realistic keep set (no 2 QB/TE)
        talent[o] = float(sum(max(0, 260 - int(r["ADP"])) for r in sel))
        kcap[o] = float(sum(r["Value"] for r in sel))
        best[o] = [r["Player"] for r in sel[:3]]

    def _z(d):
        v = list(d.values())
        m = sum(v) / len(v)
        sd = (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 or 1.0
        return {k: (x - m) / sd for k, x in d.items()}

    hz, tz, vz = _z(hist), _z(talent), _z(kcap)
    power = {o: 0.35 * hz[o] + 0.40 * tz[o] + 0.25 * vz[o] for o in MANAGERS}

    T = 1.05  # temperature: lower = bigger favorites, higher = more parity
    exps = {o: math.exp(power[o] / T) for o in power}
    tot = sum(exps.values())
    fair = {o: exps[o] / tot for o in power}
    keeprank = {o: i + 1 for i, o in enumerate(sorted(talent, key=talent.get, reverse=True))}

    def american(p):
        p = min(0.95, max(0.01, p * 1.16))  # ~16% overround (the house edge)
        return f"-{round(p / (1 - p) * 100)}" if p >= 0.5 else f"+{round((1 - p) / p * 100)}"

    rows = []
    for o in sorted(fair, key=fair.get, reverse=True):
        rows.append({
            "Team": config.manager_name(o),
            "Odds": american(fair[o]),
            "Win %": round(fair[o] * 100, 1),
            "Record": f"{record[o][0]}-{record[o][1]}",
            "KeeperRk": keeprank[o],
            "KeepVal": round(kcap[o]),
            "Best": best[o],
        })
    return rows


def render_odds() -> None:
    st.markdown(f'<h2 class="two-tone">{SEASON} <span class="g">Title Odds</span></h2>', unsafe_allow_html=True)
    st.caption("For fun — rosters reset at the draft, so this prices each team on "
               "what carries over: three seasons of results plus keeper strength "
               "and value. A Vegas-style line, juice included. Not a real sportsbook.")
    rows = build_championship_odds()
    body = []
    n = len(rows)
    for i, r in enumerate(rows):
        tag = ('<span class="kept-badge">FAVORITE</span>' if i == 0 else
               ('<span class="rk-badge">LONGSHOT</span>' if i >= n - 2 else ""))
        keepers = ", ".join(r["Best"][:3]) or "—"
        body.append(
            f'<tr><td class="rk">{i+1}</td>'
            f'<td class="pl">{r["Team"]} {tag}</td>'
            f'<td class="num" style="font-family:var(--font-display);font-weight:600;font-size:17px;color:var(--purple);">{r["Odds"]}</td>'
            f'<td class="num">{r["Win %"]}%</td>'
            f'<td class="num">{r["Record"]}</td>'
            f'<td class="num">{r["KeeperRk"]}/{n}</td>'
            f'<td class="num">{r["KeepVal"]:+d}</td>'
            f'<td style="font-size:12px;opacity:.85;">{keepers}</td></tr>'
        )
    head = ('<tr><th>#</th><th>Team</th><th>Odds</th><th>Win&nbsp;%</th>'
            '<th>3-Yr&nbsp;W-L</th><th>Keeper&nbsp;Rk</th><th>Keeper&nbsp;Value</th>'
            '<th>Top Keepers</th></tr>')
    st.markdown('<div class="neonwrap"><table class="lb lb-odds"><thead>' + head
                + '</thead><tbody>' + "".join(body) + '</tbody></table></div>',
                unsafe_allow_html=True)
    st.caption("Odds = how the model prices each team to win it all (American "
               "format: −150 = favorite, +600 = longshot). Keeper Rk = strength of "
               "your kept players by ADP (1 = best core) · Keeper Value = draft "
               "rounds gained by your best keepers.")


def _keeper_cell_map(board: dict) -> dict:
    """Overlay submitted keepers onto a pick the team OWNS that round —
    preferring their own column, then an acquired pick's slot. So two
    keepers at the same round (when the team owns two of that pick) split
    across both cells instead of stacking. Each cell is used at most once.
    Shared by the static Draft Board and the live draft board — both need
    to know which cells are already spoken for by a keeper."""
    from collections import defaultdict
    cells = board["cells"]
    data = draft_keepers()
    owner_to_slot = board["owner_to_slot"]
    owner_to_roster = board["owner_to_roster"]
    owned_slots = defaultdict(list)  # (round, roster_id) -> [slots that roster owns]
    for (r, slot), c in cells.items():
        owned_slots[(r, c["owner_roster"])].append(slot)

    keeper_cell: dict = {}
    used_cells: set = set()
    for owner_id, picks in data.items():
        roster = owner_to_roster.get(str(owner_id))
        own_slot = owner_to_slot.get(str(owner_id))
        if roster is None:
            continue
        short = config.manager_name(owner_id).split()[0]
        for s in sorted(picks, key=lambda x: (x.get("cost_round") or 99)):
            rd = s.get("cost_round")
            if not rd:
                continue
            rd = int(rd)
            cands = sorted(owned_slots.get((rd, roster), []),
                           key=lambda sl: (sl != own_slot, sl))
            placed = next((sl for sl in cands if (rd, sl) not in used_cells), None)
            conflict = placed is None
            if placed is None:
                placed = own_slot  # team owns no pick this round — flag it
            used_cells.add((rd, placed))
            entry = dict(s)
            entry["_owner_short"] = short
            entry["_home"] = placed == own_slot
            entry["_conflict"] = conflict
            keeper_cell.setdefault((rd, placed), []).append(entry)
    return keeper_cell


def render_draft_board() -> None:
    st.markdown(f'<h3>{SEASON} <span class="g">Draft Board</span></h3>', unsafe_allow_html=True)
    try:
        board = get_board()
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load the draft board from Sleeper: {e}")
        return

    if not board["order_set"]:
        st.caption("Draft order isn't set in Sleeper yet — slots show in default roster "
                   "order and will update automatically once the commissioner sets it. "
                   "Traded picks are already reflected.")

    teams, rounds, cells = board["teams"], board["rounds"], board["cells"]
    keeper_cell = _keeper_cell_map(board)
    html = ['<div class="neonwrap"><table class="dboard">']
    html.append('<tr><th style="width:32px;">Rd</th>')
    for slot in range(1, teams + 1):
        html.append(f'<th>{slot}. {board["slot_team"][slot].split()[0]}</th>')
    html.append("</tr>")
    for r in range(1, rounds + 1):
        html.append("<tr>")
        html.append(f'<td class="dbcell db-rd">{r}</td>')
        for slot in range(1, teams + 1):
            html.append(_board_cell_html(cells[(r, slot)], keeper_cell.get((r, slot))))
        html.append("</tr>")
    html.append("</table></div>")
    st.markdown("".join(html), unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:14px;color:var(--muted);">'
        'A shaded cell is a locked-in keeper, colored by position — '
        f'{_pos_span("QB")} &middot; {_pos_span("RB")} &middot; {_pos_span("WR")} &middot; {_pos_span("TE")} '
        '(a name in parentheses = kept on a pick acquired via trade) &middot; '
        '<span style="display:inline-block;width:9px;height:9px;background:rgba(255,206,31,.6);'
        'margin-right:5px;"></span>traded pick (new owner, &#9666; original owner) &middot; plain cell = pick owner. '
        "Keepers appear here for everyone as soon as they're saved.</p>",
        unsafe_allow_html=True,
    )


def _live_cell_html(c: dict, keepers: list, live: dict, is_onclock: bool) -> str:
    if keepers:
        return _board_cell_html(c, keepers)
    pick = f'<span class="dbpick">#{c["pick_no"]}</span>'
    # Traded picks get the same small "◄ original owner" tag as the static
    # Draft Board, so it's obvious a slot changed hands even once it's filled.
    trade_tag = (f'<span class="dbtrade">&#9666; {c["base_short"]}</span>'
                 if c.get("traded") else "")
    if live:
        pos = live.get("position") or ""
        nfl = f' · {live["nfl"]}' if live.get("nfl") else ""
        style = _pos_cell_style(pos)
        player = _dbplayer_html(live.get("player_id", ""), live["player_name"], pos, nfl)
        return f'<td class="dbcell" style="{style}">{pick}{player}{trade_tag}</td>'
    cls = "dbcell db-open db-onclock" if is_onclock else "dbcell db-open"
    return (f'<td class="{cls}">{pick}<br><span style="font-size:9px;">{c["owner_short"]}</span>'
            f'<br>{trade_tag}</td>')


def _live_draft_body() -> None:
    """The auto-refreshing half of the live draft board — grid, on-the-clock
    banner, and the pick-entry form. Wrapped in st.fragment(run_every=...)
    by render_live_draft() so every open tab picks up new picks on its own,
    no manual refresh needed."""
    try:
        board = get_board()
    except Exception as e:  # noqa: BLE001
        st.error(f"Couldn't load the draft board from Sleeper: {e}")
        return

    teams, rounds, cells = board["teams"], board["rounds"], board["cells"]
    keeper_cell = _keeper_cell_map(board)
    record = live_draft.load_record(SEASON)
    picks: dict = record.get("picks", {})

    ordered = sorted(cells.items(), key=lambda kv: kv[1]["pick_no"])
    open_slots = [(r, slot, c) for (r, slot), c in ordered
                  if (r, slot) not in keeper_cell and str(c["pick_no"]) not in picks]
    onclock = open_slots[0] if open_slots else None
    on_deck = open_slots[1:4]  # next few picks, for the "on deck" preview

    total_picks = teams * rounds
    made = len(keeper_cell) + len(picks)

    # A chime for everyone watching (not just whoever logged the pick) —
    # each browser tab tracks the last pick count it saw in its own
    # session_state, so a jump on this auto-refresh (someone else's pick
    # landed) or right after this tab's own "Log pick" both fire it once.
    # Browsers block audio before any user gesture on the page, so the
    # very first chime of a session may be silent until someone taps
    # something — routine after that.
    #
    # The chime iframe is rendered on EVERY rerun (height 0), not just when a
    # pick lands: inserting a brand-new component element mid-page makes the
    # browser re-layout and jump the viewer to the top of the page every
    # time someone picked. A slot that's always there just swaps content.
    last_seen = st.session_state.get("ld_seen_picks")
    play = st.session_state.get("ld_sound", True) and last_seen is not None and made > last_seen
    components.html(
        "<script>(function(){"
        f"if(!{'true' if play else 'false'}) return;"
        "try{"
        "const ctx = new (window.AudioContext || window.webkitAudioContext)();"
            "function tone(freq, start, dur){"
            "  const o = ctx.createOscillator(), g = ctx.createGain();"
            "  o.type = 'sine'; o.frequency.value = freq;"
            "  g.gain.setValueAtTime(0.0001, ctx.currentTime + start);"
            "  g.gain.exponentialRampToValueAtTime(0.3, ctx.currentTime + start + 0.02);"
            "  g.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + start + dur);"
            "  o.connect(g); g.connect(ctx.destination);"
            "  o.start(ctx.currentTime + start); o.stop(ctx.currentTime + start + dur + 0.05);"
            "}"
        "tone(660, 0, 0.12); tone(880, 0.11, 0.2);"
        "}catch(e){}"
        "})();</script>",
        height=0,
    )
    st.session_state["ld_seen_picks"] = made

    if onclock:
        r, slot, c = onclock
        # The CELL's current owner, not the slot's base/column owner — a pick
        # traded away from the slot's original team must show the new owner.
        team = c["owner_name"]
        trade_note = (f' <span style="font-size:12px;color:var(--gold-d);font-weight:400;">'
                      f'(traded from {c["base_short"]})</span>' if c.get("traded") else "")
        deck_html = ""
        if on_deck:
            names = " &rarr; ".join(f'<b>{dr[2]["owner_name"]}</b>' for dr in on_deck)
            deck_html = f'<div class="meta">On deck: {names}</div>'
        st.markdown(
            f'<div class="ld-clock"><div><div class="who">On the clock: {team}{trade_note}</div>'
            f'<div class="meta">Round {r}, Pick {c["pick_no"]} (slot {slot})</div>'
            f'{deck_html}</div>'
            f'<div class="badge">{made}/{total_picks} picks in</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown("##### Log the pick")
        kept_names = {normalize_name(s.get("player_name", ""))
                      for ps in submitted_keepers().values() for s in ps}
        live_names = {normalize_name(p.get("player_name", "")) for p in picks.values()}
        taken = kept_names | live_names

        pool = ADP_DF[~ADP_DF["name_key"].isin(taken)] if not ADP_DF.empty else ADP_DF
        pool = pool.sort_values("name")

        if pool.empty:
            st.info("No undrafted players left.")
        else:
            # A single searchable dropdown — Streamlit's own selectbox already
            # filters its options as you type, so there's no need for a
            # separate search box feeding a second "matches" box.
            options = {f'{row["name"]} — {row["position"]}': row for _, row in pool.iterrows()}
            choice = st.selectbox("Search player", list(options.keys()), key="ld_choice", index=None,
                                  placeholder="Start typing a name…")
            if choice and st.button("Log pick", type="primary", key="ld_log"):
                row = options[choice]
                name_idx = get_name_index()
                pid = name_idx.get(normalize_name(row["name"]), "")
                nfl = (H.players.get(pid, {}) or {}).get("team") if pid else ""
                picks[str(c["pick_no"])] = {
                    "player_id": pid, "player_name": row["name"],
                    "position": row["position"] if pd.notna(row["position"]) else "",
                    "nfl": nfl or "",
                }
                record["picks"] = picks
                record["season"] = SEASON
                try:
                    live_draft.save_record(record, SEASON)
                    st.session_state.pop("ld_choice", None)
                    st.rerun(scope="fragment")
                except Exception as e:  # noqa: BLE001
                    st.error("Couldn't save this pick — GitHub is throttling writes right now. "
                             "Jot it down and log it again in a few minutes; the board itself "
                             f"stays live. ({type(e).__name__})")
    else:
        st.success(f"All {total_picks} picks are in — the draft is complete.")

    html = ['<div class="neonwrap"><table class="dboard">']
    html.append('<tr><th style="width:32px;">Rd</th>')
    for slot in range(1, teams + 1):
        html.append(f'<th>{slot}. {board["slot_team"][slot].split()[0]}</th>')
    html.append("</tr>")
    for r in range(1, rounds + 1):
        html.append("<tr>")
        html.append(f'<td class="dbcell db-rd">{r}</td>')
        for slot in range(1, teams + 1):
            c = cells[(r, slot)]
            live = picks.get(str(c["pick_no"]))
            is_onclock = onclock is not None and onclock[0] == r and onclock[1] == slot
            html.append(_live_cell_html(c, keeper_cell.get((r, slot)), live, is_onclock))
        html.append("</tr>")
    html.append("</table></div>")
    st.markdown("".join(html), unsafe_allow_html=True)

    export_rows = []
    for (r, slot), c in sorted(cells.items(), key=lambda kv: kv[1]["pick_no"]):
        ks = keeper_cell.get((r, slot))
        live_pick = picks.get(str(c["pick_no"]))
        base = {
            "Pick": c["pick_no"], "Round": r, "Slot": slot,
            "Team": c["owner_name"],
            "Traded From": c["base_short"] if c.get("traded") else "",
        }
        if ks:
            for k in ks:
                export_rows.append({**base,
                    "Type": "Rookie Keeper" if k.get("is_rookie_keeper") else "Keeper",
                    "Player": k["player_name"], "Pos": k.get("position", ""), "NFL": ""})
        elif live_pick:
            export_rows.append({**base, "Type": "Live Pick",
                "Player": live_pick["player_name"],
                "Pos": _clean_pos(live_pick.get("position", "")),
                "NFL": live_pick.get("nfl", "")})
        else:
            export_rows.append({**base, "Type": "", "Player": "", "Pos": "", "NFL": ""})
    st.download_button(
        "Download draft results (CSV)",
        pd.DataFrame(export_rows).to_csv(index=False),
        file_name=f"babies_and_boomer_draft_{SEASON}.csv", mime="text/csv",
        key="ld_export",
    )

    if picks:
        st.markdown("##### Recent picks")
        recent = sorted(picks.items(), key=lambda kv: -int(kv[0]))[:8]
        for pn, p in recent:
            col1, col2 = st.columns([5, 1])
            col1.markdown(
                f'<div class="ld-recent-row"><span class="pk">#{pn}</span>'
                f'<span class="nm">{p["player_name"]}</span>'
                f'<span style="color:var(--muted);font-size:11px;">{p.get("position","")}</span></div>',
                unsafe_allow_html=True,
            )
            if col2.button("Undo", key=f"ld_undo_{pn}"):
                picks.pop(pn, None)
                record["picks"] = picks
                try:
                    live_draft.save_record(record, SEASON)
                    st.rerun(scope="fragment")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Couldn't undo right now — GitHub is throttling writes. ({type(e).__name__})")

    with st.expander("Reset the live draft"):
        st.caption("Clears every logged pick. Keepers aren't affected — they're computed "
                   "live from Set My Keepers, not stored here.")
        if st.button("Reset all picks", key="ld_reset"):
            try:
                live_draft.save_record({}, SEASON)
                st.rerun(scope="fragment")
            except Exception as e:  # noqa: BLE001
                st.error(f"Couldn't reset right now — GitHub is throttling writes. ({type(e).__name__})")


def render_live_draft() -> None:
    st.markdown('<h2 class="two-tone">Live <span class="g">Draft Board</span></h2>', unsafe_allow_html=True)
    st.caption("Track the actual (offline) draft pick by pick. Keepers are pre-filled from "
               "Set My Keepers; everyone with this page open sees new picks on their own — "
               "no refresh needed.")
    c1, c2 = st.columns(2)
    auto = c1.toggle("Auto-refresh (every 5s)", value=True, key="ld_auto")
    c2.toggle("Sound on new pick", value=True, key="ld_sound")
    st.fragment(run_every=(5 if auto else None))(_live_draft_body)()


def render_adp() -> None:
    st.markdown(f'<h2 class="two-tone">{SEASON} Consensus <span class="g">ADP</span></h2>', unsafe_allow_html=True)
    st.caption("One consensus number per player, averaged across all sources: "
               + ", ".join(ADP_META.get("sources", [])) + ". The **Move** column shows each "
               "player's consensus-rank change over the selected window (up = drafted earlier).")
    if ADP_DF.empty:
        st.info("No ADP data yet. Run `python scripts/refresh_adp.py`.")
        return
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        q = st.text_input("Search player", "")
    with c2:
        pos = st.multiselect("Position", ["QB", "RB", "WR", "TE"], default=[])
    with c3:
        win = st.selectbox("Move window", [7, 14, 30], index=2,
                           format_func=lambda d: f"Last {d} days", key="cadp_win")

    _mv_fn = getattr(adp_consensus, "adp_movement", None)
    mv = _mv_fn(SEASON, window_days=win) if _mv_fn else {"moves": []}
    move_map = {normalize_name(m["name"]): m["delta"] for m in mv.get("moves", [])}
    name_idx = get_name_index()

    def _fmt_move(d):
        if d is None or (isinstance(d, float) and pd.isna(d)):
            return '<span style="color:var(--muted);">—</span>'
        d = int(d)
        if d > 0:
            return f'<span style="color:#1c9b63;font-weight:700;">▲ {d}</span>'
        if d < 0:
            return f'<span style="color:var(--red);font-weight:700;">▼ {abs(d)}</span>'
        return '<span style="color:var(--muted);">—</span>'

    view = ADP_DF.copy()
    if q:
        view = view[view["name"].str.contains(q, case=False, na=False)]
    if pos:
        view = view[view["position"].isin(pos)]
    view = view.sort_values("consensus_rank")
    if view.empty:
        st.info("No players match those filters.")
        return
    rows = []
    for _, r in view.iterrows():
        pid = name_idx.get(normalize_name(r["name"]), "")
        cadp = "" if pd.isna(r["consensus_adp"]) else f'{r["consensus_adp"]:.1f}'
        rows.append(
            f'<tr><td class="rk">{int(r["consensus_rank"])}</td>'
            f'<td class="pl">{theme.img_tag(pid) if pid else ""}{r["name"]}</td>'
            f'<td class="pos"><span class="posdot p-{r["position"]}"></span>{r["position"]}</td>'
            f'<td class="num">{cadp}</td>'
            f'<td class="num">{_fmt_move(move_map.get(r["name_key"]))}</td></tr>'
        )
    head = ('<tr><th>#</th><th>Player</th><th>Pos</th>'
            '<th>Consensus&nbsp;ADP</th><th>Move&nbsp;({}d)</th></tr>').format(win)
    st.markdown('<div class="neonwrap" style="max-height:660px;overflow:auto;">'
                '<table class="lb lb-rook"><thead>' + head + '</thead><tbody>'
                + "".join(rows) + '</tbody></table></div>', unsafe_allow_html=True)
    if not mv.get("moves"):
        st.caption("ADP movement appears once two daily snapshots exist — check back after "
                   "the next daily refresh.")


# ----------------------------------------------------------------- navigation
# Three-level routing via `?p=<home|preseason|inseason>&g=<group>&t=<leaf>` —
# mirrors kreeper-league's nav so both apps behave the same way. `page` is
# the top-level section; Pre-Season/In-Season each fan out through a
# group -> leaf popover (render_bottom_bar) instead of on-page tab rows.
_TOP_SECTIONS = {"home", "preseason", "inseason"}
page = st.query_params.get("p", "home")
if page not in _TOP_SECTIONS:
    page = "home"

# Sub-tab trees for the two sections that have them.
PRESEASON_GROUPS = [("keepers", "Keepers"), ("draft", "Draft"), ("players", "Players")]
PRESEASON_LEAVES = {
    "keepers": [("setkeepers", "Set My Keepers"), ("value", "Keeper Value Board"),
                ("landscape", "Keeper Landscape")],
    "draft": [("live", "Live Draft Board"), ("board", "Draft Board"), ("projected", "Projected Draft")],
    "players": [("adp", "ADP & Rookies")],
}
INSEASON_GROUPS = [("week", "This Week"), ("trades", "Trades"), ("league", "League"), ("history", "History")]
INSEASON_LEAVES = {
    "week": [("live", "Live"), ("matchup", "Matchup"), ("keepers", f"{SEASON + 1} Keepers")],
    "trades": [("recent", "Trades"), ("analyzer", "Trade Analyzer")],
    "league": [("standings", "Standings"), ("lottery", "Draft-Order Lottery")],
    "history": [("record", "Record Book")],
}
# Pages that were folded into another one. Old links (shared in the group
# chat, bookmarked) land on the page that now holds that content.
LEAF_ALIASES = {
    "preseason": {("keepers", "needs"): ("keepers", "landscape"),
                  ("draft", "capital"): ("draft", "board"),
                  ("players", "trends"): ("players", "adp")},
    "inseason": {("trades", "market"): ("trades", "recent"),
                 ("league", "odds"): ("league", "standings"),
                 ("league", "superlatives"): ("history", "record"),
                 ("history", "hitrate"): ("history", "record")},
}


def _resolve_leaf(section: str, leaves_by_group: dict, default_g: str):
    """(group, leaf) for the current URL, following LEAF_ALIASES and writing
    the canonical pair back so the nav highlights the right item."""
    g = st.query_params.get("g", default_g)
    t = st.query_params.get("t", "")
    if (g, t) in LEAF_ALIASES.get(section, {}):
        g, t = LEAF_ALIASES[section][(g, t)]
        st.query_params["g"], st.query_params["t"] = g, t
    if g not in leaves_by_group:
        g = default_g
    if t not in dict(leaves_by_group[g]):
        t = leaves_by_group[g][0][0]
    return g, t


def _stack(*renders) -> None:
    """One page made of several former pages, in order."""
    for i, fn in enumerate(renders):
        if i:
            st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
        fn()


def _group_popover_html(pop_id: str, section_label: str, groups: list,
                         leaves_by_group: dict, page_key: str) -> str:
    """One flat sheet for a bottom-bar section — every leaf listed directly
    under a plain (non-tappable) group label, one tap from the bar to any
    page. Shared by Pre-Season and In-Season."""
    cur_g = st.query_params.get("g", "")
    cur_t = st.query_params.get("t", "")

    def leaf_links(leaves, gk):
        return "".join(
            f'<a class="bb-pop-item{" leaf-active" if page == page_key and cur_g == gk and cur_t == k else ""}" '
            f'href="?p={page_key}&g={gk}&t={k}" target="_self">'
            f'<span class="lbl">{label}</span></a>'
            for k, label in leaves
        )

    sections = "".join(
        f'<div class="bb-sec-label">{glabel}</div>' + leaf_links(leaves_by_group[gk], gk)
        for gk, glabel in groups
    )
    return (
        f'<div class="bb-pop" id="bb-pop-{pop_id}">'
        f'<div class="bb-pop-head"><span class="bb-pop-title">{section_label}</span></div>'
        f'<div class="bb-pop-list">{sections}</div>'
        f'</div>'
    )


def _me_popover_html() -> str:
    """The masthead team dropdown: every team, each a link to THIS page with
    that team as `me`."""
    me = _me()
    items = "".join(
        f'<a class="bb-pop-item{" leaf-active" if o == me else ""}" href="{_href_with(me=o)}" target="_self">'
        f'<span class="lbl">{m.get("team") or m["name"]}</span><span class="sub">{m["name"]}</span></a>'
        for o, m in MANAGERS.items())
    return ('<div class="bb-pop bb-pop-me" id="bb-pop-me"><div class="bb-pop-head">'
            '<span class="bb-pop-title">Whose phone is this?</span></div>' + items + "</div>")


# Installed once per page load, in the PAGE's own JS realm (window.parent.eval),
# not the components iframe's: Streamlit rebuilds both the iframe and the
# masthead on reruns, so per-element listeners bound from the iframe go stale
# or die with it. One delegated capture-phase handler covers every case:
#   - [data-toggle] opens/closes a sheet (bottom bar sections, the team chip)
#   - the scrim closes them
#   - any in-app link ("?p=...") gets the remembered team appended, so the
#     choice survives every page change.
_NAV_HANDLER_JS = r"""
(function(){
  if (document.__kreeperNav) return;
  document.__kreeperNav = true;
  var KEY = 'kreeper_me';
  function closeAll(){
    document.querySelectorAll('.bb-pop').forEach(function(p){ p.classList.remove('on'); });
    var sc = document.getElementById('bb-scrim'); if (sc) sc.classList.remove('on');
  }
  document.addEventListener('click', function(e){
    var tg = e.target.closest('[data-toggle]');
    if (tg) {
      e.preventDefault(); e.stopPropagation();
      var pop = document.getElementById(tg.getAttribute('data-toggle'));
      var was = pop && pop.classList.contains('on');
      closeAll();
      if (pop && !was) { pop.classList.add('on'); var sc = document.getElementById('bb-scrim'); if (sc) sc.classList.add('on'); }
      return;
    }
    if (e.target.id === 'bb-scrim') { closeAll(); return; }
    var a = e.target.closest('a[href]');
    if (!a) return;
    var h = a.getAttribute('href') || '';
    if (h.charAt(0) !== '?') return;
    var u = new URLSearchParams(h.slice(1));
    if (u.get('me')) { try { localStorage.setItem(KEY, u.get('me')); } catch(_) {} return; }
    var m = null; try { m = localStorage.getItem(KEY); } catch(_) {}
    if (m) { u.set('me', m); a.setAttribute('href', '?' + u.toString()); }
  }, true);
})();
"""


def render_bottom_bar() -> None:
    """Fixed floating pill bar — the site's only nav. Home is a plain link;
    Pre-Season / In-Season pop a sheet above the bar so you can jump
    straight to a leaf sub-page instead of landing at the section root.
    Also carries the masthead's team dropdown and remembers the team."""
    ps_pop = _group_popover_html("preseason", "Pre-Season", PRESEASON_GROUPS, PRESEASON_LEAVES, "preseason")
    is_pop = _group_popover_html("inseason", "In-Season", INSEASON_GROUPS, INSEASON_LEAVES, "inseason")

    active = lambda k: " active" if page == k else ""
    bar_html = (
        '<div class="bb-scrim" id="bb-scrim"></div>'
        + ps_pop + is_pop + _me_popover_html() +
        '<div class="bottom-bar-wrap"><div class="bottom-bar">'
        f'<a class="navlink{active("home")}" href="?p=home" target="_self">Home</a>'
        f'<div class="navlink{active("preseason")}" data-toggle="bb-pop-preseason">Pre-Season</div>'
        f'<div class="navlink{active("inseason")}" data-toggle="bb-pop-inseason">In-Season</div>'
        '</div></div>'
    )
    # st.markdown silently strips <script> tags, so this can't live there.
    # components.html runs real JS in a same-origin iframe, which reaches the
    # app's document as window.parent.document: the bar is injected THERE
    # (its CSS lives in the app document, and position:fixed then anchors to
    # the real viewport). Community Cloud's own badge lives one level further
    # out, in Cloud's wrapper page, so hiding it needs window.top.
    #
    # Team memory: a URL `me` is saved to localStorage; a bare URL with a
    # saved team reloads once with it (that's a fresh visit, so the server
    # can't know the team any other way — see _me for why not a cookie). The
    # reload runs through P.eval: this iframe is sandboxed without
    # allow-top-navigation, so it may not navigate its parent itself.
    valid = json.dumps(list(MANAGERS))
    components.html(
        "<script>(function(){"
        "const P = window.parent, doc = P.document, topDoc = window.top.document;"
        f"const VALID = {valid};"
        "try {"
        "  const q = new URLSearchParams(P.location.search);"
        "  const me = q.get('me');"
        "  if (me && VALID.includes(me)) { P.localStorage.setItem('kreeper_me', me); }"
        "  else { const saved = P.localStorage.getItem('kreeper_me');"
        "    if (saved && VALID.includes(saved)) { q.set('me', saved);"
        "      P.eval('location.replace(' + JSON.stringify(P.location.pathname + '?' + q.toString()) + ')');"
        "      return; } }"
        "} catch (e) {}"
        "if (!topDoc.getElementById('kreeper-hide-cloud-chrome')) {"
        "  const s = topDoc.createElement('style');"
        "  s.id = 'kreeper-hide-cloud-chrome';"
        "  s.textContent = '[class*=\"viewerBadge\"], [class*=\"profileContainer\"], "
        "[class*=\"profilePreview\"], [data-testid=\"manage-app-button\"], "
        "a[href=\"https://streamlit.io/cloud\"], a[href*=\"share.streamlit.io\"]"
        "{ display:none !important; }';"
        "  topDoc.head.appendChild(s);"
        "}"
        "const old = doc.getElementById('kreeper-bottom-bar-root');"
        "if (old) old.remove();"
        "const root = doc.createElement('div');"
        "root.id = 'kreeper-bottom-bar-root';"
        f"root.innerHTML = {json.dumps(bar_html)};"
        "doc.body.appendChild(root);"
        f"P.eval({json.dumps(_NAV_HANDLER_JS)});"
        "})();</script>",
        height=0,
    )


def _masthead_right(current: str) -> str:
    """Right-hand side of the masthead. In-season: the season line ("2026 ·
    Week 4 of 13") and the whose-phone chip, which opens the team dropdown.
    In every other phase, the phase status line."""
    if current == "in_season":
        wk = season.current_week()
        total = season.regular_season_weeks()
        line = f'Week {wk} of {total}' if wk else "Kickoff"
        me = _me()
        chip = (f'<span class="mechip" role="button" data-toggle="bb-pop-me"><span class="av sm">{_initials(me)}</span>'
                f'{_team_of(me)} <i>&#9662;</i></span>' if me else
                '<span class="mechip" role="button" data-toggle="bb-pop-me">Pick your team <i>&#9662;</i></span>')
        return f'<div class="mh-right"><div class="mh-meta">{SEASON} &middot; {line}</div>{chip}</div>'
    return _status_line_html(current)


# Masthead on every page: a full-bleed solid purple band with the gold stripe
# under it, the script wordmark on the left (clickable through to Home) and
# the season line + team chip on the right. Section links live in the fixed
# bottom bar.
st.markdown(
    f'<div class="masthead">'
    f'<a class="mh-home" href="?p=home" target="_self">'
    f'{theme.logo_html(30, None, "Babies &amp; Boomer")}</a>'
    f'{_masthead_right(_current_phase())}'
    f'</div>',
    unsafe_allow_html=True,
)

if page == "home":
    render_home()
elif page == "pick":
    render_team_picker()
elif page == "preseason":
    g, t = _resolve_leaf("preseason", PRESEASON_LEAVES, "keepers")
    {("keepers", "setkeepers"): render_my_keepers,
     ("keepers", "value"): render_keeper_value_board,
     ("keepers", "landscape"): lambda: _stack(render_keeper_landscape, render_roster_needs),
     ("draft", "live"): render_live_draft,
     ("draft", "board"): lambda: _stack(render_draft_board, render_draft_capital),
     ("draft", "projected"): render_mock_draft,
     ("players", "adp"): lambda: _stack(render_rookies, render_adp, render_adp_trends),
     }[(g, t)]()
elif page == "inseason":
    g, t = _resolve_leaf("inseason", INSEASON_LEAVES, "week")
    {("week", "live"): render_live,
     ("week", "matchup"): render_matchup,
     ("week", "keepers"): render_keeper_outlook,
     ("trades", "recent"): lambda: _stack(render_recent_trades, render_trade_targets),
     ("trades", "analyzer"): render_trade_analyzer,
     ("league", "standings"): lambda: _stack(render_standings, render_power, render_odds),
     ("league", "lottery"): render_lottery,
     ("history", "record"): lambda: _stack(render_record_book, render_superlatives, render_keeper_hitrate),
     }[(g, t)]()

render_bottom_bar()
