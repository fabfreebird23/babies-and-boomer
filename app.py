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

from kreeper import config, draftboard, engine, history, live_draft, phase, storage, theme
from kreeper.adp import consensus as adp_consensus
from kreeper.names import normalize_name

st.set_page_config(page_title="Babies and Boomer — Keeper Hub", layout="wide")
theme.inject(st)

LEAGUE = config.league()
SEASON = config.current_season()
MANAGERS = config.managers()  # owner_id -> {handle, name, team}
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
<link href="https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@500;700&display=swap" rel="stylesheet">
<style>
 *{margin:0;box-sizing:border-box;}
 html,body{background:transparent;overflow:hidden;font-family:'Oswald',sans-serif;}
 .cd{display:flex;flex-direction:column;align-items:center;gap:6px;
   background:#fff;border:2px solid #ff4f9d;border-radius:16px;padding:14px 18px;
   box-shadow:0 6px 22px rgba(123,92,255,.18);}
 .ttl{font-family:'Anton',sans-serif;text-transform:uppercase;letter-spacing:3px;
   font-size:15px;color:#7b5cff;}
 .units{display:flex;gap:16px;}
 .u{display:flex;flex-direction:column;align-items:center;min-width:60px;}
 .u .n{font-family:'Anton',sans-serif;font-size:42px;line-height:1;color:#ff4f9d;
   text-shadow:0 0 12px rgba(255,79,157,.45);}
 .u .l{font-size:10px;letter-spacing:2px;text-transform:uppercase;color:#8b86a0;margin-top:5px;}
 .sub{font-size:12px;letter-spacing:1px;color:#6a6580;}
 .locked{font-family:'Anton',sans-serif;font-size:30px;color:#7b5cff;letter-spacing:2px;}
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
        from_rookie = (bool(storage.prior_rookie_seasons(owner_id, pid, SEASON))
                       and not ever_regular_keeper(pid))
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
    surplus = None
    if cost_round is not None and adp_round is not None:
        surplus = adp_round - cost_round
        cls = "surplus-pos" if surplus > 0 else ("surplus-neg" if surplus < 0 else "")
        sign = f"+{surplus}" if surplus > 0 else str(surplus)
        badges.append(f'<span class="badge {cls}">{sign} RD SURPLUS</span>')

    if not eligible:
        note = ("Not eligible to keep — clock's up or no pick left to use." if keep_year == "DONE"
                else "No pick available at or before this round.")
    elif surplus is not None and surplus > 5:
        note = "Big discount to market — a strong keep."
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


def ever_regular_keeper(pid: str) -> bool:
    """True if the player has EVER been kept as a regular (non-rookie) keeper.
    Moving a rookie keeper into a normal keeper slot is permanent — once they've
    been a regular keeper they can never go back to a rookie-keeper spot."""
    pid = str(pid)
    return any(p == pid and (p, s) not in H.rookie_kept_set for (p, s) in H.kept_set)


def rookie_keeper_eligible(owner_id: str, pid: str) -> bool:
    """A player may be kept as a ROOKIE keeper only if THIS team drafted them in
    the player's rookie season and has held them continuously since. A trade (or
    picking them up as a veteran) breaks rookie-keeper eligibility, and so does
    ever having been moved into a regular keeper slot (the conversion is permanent).
    """
    pid = str(pid)
    # Converted to a regular keeper at some point -> can't return to a rookie slot.
    if ever_regular_keeper(pid):
        return False
    # An established rookie keeper for THIS owner stays eligible (seeded ledger
    # may predate our Sleeper draft window).
    if storage.prior_rookie_seasons(owner_id, pid, SEASON):
        return True
    ye = _years_exp(pid)
    if ye is None:
        return False
    rookie_season = SEASON - int(ye)
    ps = H.player_seasons.get(pid, {})
    rec = ps.get(rookie_season)
    # Must be their rookie-season DRAFT pick (not a keeper slot) by THIS owner.
    if not rec or str(rec.get("owner")) != str(owner_id) or rec.get("is_keeper"):
        return False
    # Held continuously since — any season under a different owner = traded.
    for s in range(rookie_season, SEASON):
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


def build_value_leaderboard(top_n: int = 50, hide_rookie_keepers: bool = False) -> pd.DataFrame:
    """Best keeper bargains across every roster.

    Value = keeper-cost round minus ADP round, i.e. how many rounds of draft
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
                    "Value": cost_round - adp_round,
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
                "Value": fa_cost - adp_round,
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
                "Value": int(cost_round) - adp_round,
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
               "player (cost round vs. consensus ADP round). Green = declared keeper · "
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


def _render_home_in_season() -> None:
    render_home_glance()
    render_odds()


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
    st.caption(f"Value = Round {rnd} − the player's ADP round (draft capital you'd "
               "gain by keeping them there). **RK** = currently a rookie keeper — on a "
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
    kv = {str(r["_pid"]): int(r["Value"]) for _, r in tt.iterrows()}     # keeper bargain (rounds)
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

    pick_seasons = [SEASON, SEASON + 1, SEASON + 2]
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
            discount = 0.8 ** (yr - SEASON)
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
        bonus = max(0, kv.get(pid, 0)) * 6   # cheap-keeper edge, on top of talent
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
    st.caption("Positional scarcity: of the top players at each position, who's "
               "likely kept (and by whom) vs. left in the draft pool. Thin pools "
               "= positions to target early; deep pools = wait.")
    kept = _projected_kept_ids()
    pid_owner = {}
    for o, pids in CANDS.items():
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
            st.caption(f"Top {len(players)} {pos}s — **{kept_n} likely kept**, "
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

    name = st.selectbox("Who are you?", list(NAME_TO_ID.keys()), index=None,
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
        from_rookie = ((not is_rookie) and bool(storage.prior_rookie_seasons(owner_id, pid, SEASON))
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


def _pos_span(pos: str) -> str:
    """A player's position, colored to match the posdot convention used
    everywhere else (ADP tables, contract cards) — lets a positional run
    jump out while scanning the draft grid instead of every filled cell
    reading as the same flat color."""
    return f'<span style="font-weight:700;color:{_POS_COLOR.get(pos, "var(--muted)")};">{pos}</span>'


def _board_cell_html(c: dict, keepers: list) -> str:
    pick = f'<span class="dbpick">#{c["pick_no"]}</span>'
    if keepers:
        conflict = False
        parts = []
        for k in keepers:
            rk = ' <span class="rk-badge">RK</span>' if k.get("is_rookie_keeper") else ""
            # Keeper on an acquired pick (not their own column) -> tag the owner.
            tag = "" if k.get("_home") else f' <span style="font-size:9px;">({k.get("_owner_short","")})</span>'
            parts.append(f'<b>{k["player_name"]}</b> '
                         f'<span style="font-size:9px;">{_pos_span(k.get("position",""))}{rk}</span>{tag}')
            conflict = conflict or k.get("_conflict")
        names = "<br>".join(parts)
        if conflict:
            return (f'<td class="dbcell db-conflict">{pick}<br>{names}'
                    f'<br><span style="font-size:9px;">no pick this round</span></td>')
        return f'<td class="dbcell db-keep">{pick}<br>{names}</td>'
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
            f'<td class="num" style="font-family:\'Anton\';font-size:17px;color:var(--purple);">{r["Odds"]}</td>'
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
    data = submitted_keepers()
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
        '<span style="display:inline-block;width:9px;height:9px;background:rgba(28,155,99,.4);'
        'margin-right:5px;"></span>keeper locked in (a name in parentheses = kept on a pick acquired via trade) &middot; '
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
    trade_tag = (f'<br><span class="dbtrade">&#9666; {c["base_short"]}</span>'
                 if c.get("traded") else "")
    if live:
        sub = _pos_span(live.get("position") or "")
        if live.get("nfl"):
            sub += f' · {live["nfl"]}'
        return (f'<td class="dbcell db-live">{pick}<br><b>{live["player_name"]}</b>'
                f'<br><span style="font-size:9px;">{sub}</span>{trade_tag}</td>')
    cls = "dbcell db-open db-onclock" if is_onclock else "dbcell db-open"
    return (f'<td class="{cls}">{pick}<br><span style="font-size:9px;">{c["owner_short"]}</span>'
            f'{trade_tag}</td>')


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
                    "position": row["position"], "nfl": nfl or "",
                }
                record["picks"] = picks
                record["season"] = SEASON
                try:
                    live_draft.save_record(record, SEASON)
                    st.session_state.pop("ld_choice", None)
                    st.rerun(scope="fragment")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Couldn't save — try again in a moment. ({type(e).__name__})")
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
                live_draft.save_record(record, SEASON)
                st.rerun(scope="fragment")

    with st.expander("Reset the live draft"):
        st.caption("Clears every logged pick. Keepers aren't affected — they're computed "
                   "live from Set My Keepers, not stored here.")
        if st.button("Reset all picks", key="ld_reset"):
            live_draft.save_record({}, SEASON)
            st.rerun(scope="fragment")


def render_live_draft() -> None:
    st.markdown('<h2 class="two-tone">Live <span class="g">Draft Board</span></h2>', unsafe_allow_html=True)
    st.caption("Track the actual (offline) draft pick by pick. Keepers are pre-filled from "
               "Set My Keepers; everyone with this page open sees new picks on their own — "
               "no refresh needed.")
    auto = st.toggle("Auto-refresh (every 5s)", value=True, key="ld_auto")
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
                ("landscape", "Keeper Landscape"), ("needs", "Roster Needs")],
    "draft": [("live", "Live Draft Board"), ("board", "Draft Board"),
              ("projected", "Projected Draft"), ("capital", "Draft Capital & Keeper Cost")],
    "players": [("adp", "ADP"), ("trends", "ADP Trends")],
}
INSEASON_GROUPS = [("trades", "Trades"), ("league", "League"), ("history", "History")]
INSEASON_LEAVES = {
    "trades": [("recent", "Recent Trades"), ("market", "Trade Market"), ("analyzer", "Trade Analyzer")],
    "league": [("odds", "Title Odds"), ("superlatives", "Superlatives"), ("lottery", "Draft-Order Lottery")],
    "history": [("record", "Record Book"), ("hitrate", "Keeper Hit-Rate")],
}


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


def render_bottom_bar() -> None:
    """Fixed floating pill bar — the site's only nav. Home is a plain link;
    Pre-Season / In-Season pop a sheet above the bar so you can jump
    straight to a leaf sub-page instead of landing at the section root."""
    ps_pop = _group_popover_html("preseason", "Pre-Season", PRESEASON_GROUPS, PRESEASON_LEAVES, "preseason")
    is_pop = _group_popover_html("inseason", "In-Season", INSEASON_GROUPS, INSEASON_LEAVES, "inseason")

    active = lambda k: " active" if page == k else ""
    bar_html = (
        '<div class="bb-scrim" id="bb-scrim"></div>'
        + ps_pop + is_pop +
        '<div class="bottom-bar-wrap"><div class="bottom-bar">'
        f'<a class="navlink{active("home")}" href="?p=home" target="_self">Home</a>'
        f'<div class="navlink{active("preseason")}" data-toggle="bb-pop-preseason">Pre-Season</div>'
        f'<div class="navlink{active("inseason")}" data-toggle="bb-pop-inseason">In-Season</div>'
        '</div></div>'
    )
    # st.markdown silently strips <script> tags, so the popover's click
    # handlers can't live there (see render_countdown for the same issue).
    # components.html runs real JS in a same-origin iframe, which lets us
    # reach through to window.parent.document and inject the bar directly
    # into the real page — that's also the only way position:fixed ends up
    # anchored to the actual viewport instead of a tiny iframe box.
    #
    # Streamlit Community Cloud's own chrome (the crown badge for signed-out
    # visitors, the "Manage app"/profile-avatar badge for the owner) renders
    # in Cloud's outer wrapper page, a level further out than the app iframe
    # — hiding it needs window.top specifically (the one target that always
    # reaches the true outermost page) rather than window.parent.
    components.html(
        "<script>(function(){"
        "const doc = window.parent.document;"
        "const topDoc = window.top.document;"
        "if (!topDoc.getElementById('bb-hide-cloud-chrome')) {"
        "  const s = topDoc.createElement('style');"
        "  s.id = 'bb-hide-cloud-chrome';"
        "  s.textContent = '[class*=\"viewerBadge\"], [class*=\"profileContainer\"], "
        "[class*=\"profilePreview\"], [data-testid=\"manage-app-button\"], "
        "a[href=\"https://streamlit.io/cloud\"], a[href*=\"share.streamlit.io\"]"
        "{ display:none !important; }';"
        "  topDoc.head.appendChild(s);"
        "}"
        "const old = doc.getElementById('bb-bottom-bar-root');"
        "if (old) old.remove();"
        "const root = doc.createElement('div');"
        "root.id = 'bb-bottom-bar-root';"
        f"root.innerHTML = {json.dumps(bar_html)};"
        "doc.body.appendChild(root);"
        "const scrim = doc.getElementById('bb-scrim');"
        "function closeAll(){ doc.querySelectorAll('.bb-pop').forEach(p=>p.classList.remove('on')); scrim.classList.remove('on'); }"
        "doc.querySelectorAll('[data-toggle]').forEach(function(btn){"
        "  btn.addEventListener('click', function(e){"
        "    e.stopPropagation();"
        "    const pop = doc.getElementById(btn.dataset.toggle);"
        "    const wasOn = pop.classList.contains('on');"
        "    closeAll();"
        "    if (!wasOn){ pop.classList.add('on'); scrim.classList.add('on'); }"
        "  });"
        "});"
        "scrim.addEventListener('click', closeAll);"
        "})();</script>",
        height=0,
    )


# Top bar on every page: centered "Babies & Boomer" script-logo masthead
# band, clickable through to Home, with the persistent phase status line
# underneath, above the gold rule. Section links live in the fixed bottom
# bar instead.
st.markdown(
    f'<div class="kbar">'
    f'<a class="khome" href="?p=home" target="_self">'
    f'{theme.logo_html(30, "The Keeper Sportsource", "Babies &amp; Boomer")}</a>'
    f'{_status_line_html(_current_phase())}'
    f'</div>',
    unsafe_allow_html=True,
)

if page == "home":
    render_home()
elif page == "preseason":
    g = st.query_params.get("g", "keepers")
    if g not in PRESEASON_LEAVES:
        g = "keepers"

    leaves = PRESEASON_LEAVES[g]
    t = st.query_params.get("t", leaves[0][0])
    if t not in dict(leaves):
        t = leaves[0][0]

    if g == "keepers":
        {"setkeepers": render_my_keepers, "value": render_keeper_value_board,
         "landscape": render_keeper_landscape, "needs": render_roster_needs}[t]()
    elif g == "draft":
        {"live": render_live_draft, "board": render_draft_board, "projected": render_mock_draft,
         "capital": render_draft_capital}[t]()
    else:
        if t == "adp":
            render_rookies()
            st.divider()
            render_adp()
        else:
            render_adp_trends()
elif page == "inseason":
    g = st.query_params.get("g", "trades")
    if g not in INSEASON_LEAVES:
        g = "trades"

    leaves = INSEASON_LEAVES[g]
    t = st.query_params.get("t", leaves[0][0])
    if t not in dict(leaves):
        t = leaves[0][0]

    if g == "trades":
        {"recent": render_recent_trades, "market": render_trade_targets,
         "analyzer": render_trade_analyzer}[t]()
    elif g == "league":
        {"odds": render_odds, "superlatives": render_superlatives,
         "lottery": render_lottery}[t]()
    else:
        {"record": render_record_book, "hitrate": render_keeper_hitrate}[t]()

render_bottom_bar()
