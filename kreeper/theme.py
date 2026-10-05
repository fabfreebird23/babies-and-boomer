"""Old-school Eastbay '90s theme: purple/gold/black duotone magazine look —
brush-script wordmark, yellow cut-out frames, white/black label tags, gritty
halftone field. Shared CSS for the custom HTML surfaces (leaderboard, team
cards, draft board) plus purple-duotone, gold-framed Sleeper headshots.
"""
from __future__ import annotations

import math

_ASSETS = None  # (sneaker assets no longer used; section icon is an inline SVG)

SLEEPER_IMG = "https://sleepercdn.com/content/nfl/players/thumb/{pid}.jpg"
SLEEPER_DEFAULT = "https://sleepercdn.com/images/v2/icons/player_default.webp"
ESPN_IMG = "https://a.espncdn.com/i/headshots/nfl/players/full/{eid}.png"

# sleeper_pid -> espn player/headshot id, populated by app at startup
# (set_espn_ids). Lets newly-added rookies — who have no Sleeper photo — fall
# back to ESPN's headshot before the generic silhouette.
_ESPN_BY_PID: dict = {}


def set_espn_ids(mapping: dict) -> None:
    _ESPN_BY_PID.clear()
    _ESPN_BY_PID.update({str(k): str(v) for k, v in mapping.items() if v})


# Eastbay palette
PURPLE = "#4b2d9f"
PURPLE_L = "#7a5bd8"
GOLD = "#ffce1f"
GOLD_D = "#e0a400"
INK = "#0d0a14"
CYAN = "#3fd0e8"
RED = "#ff4f4f"
TEAL = "#1f8a5b"   # good
AMBER = "#b07400"  # warning

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Oswald:wght@500;600;700&family=Pacifico&display=swap');

:root{
  --bg:#f4f0e6; --panel:#ffffff; --panel2:#f3eef9;
  --purple:#4b2d9f; --purple-d:#2a1a5e; --purple-l:#7a5bd8;
  --gold:#ffce1f; --gold-d:#c99700; --cyan:#2390c0; --red:#d6336c;
  --ink:#241a40; --muted:#6f6593; --line:#e3dcf2;
  /* type: Oswald display, Inter for text and every number (tabular figures);
     Pacifico is the wordmark only */
  --font-display:'Oswald', system-ui, sans-serif; --font-body:'Inter', system-ui, sans-serif;
  --mono:'Inter', system-ui, sans-serif; --display-ls:.4px; --display-wt:600;
  /* flattened kit: purple surfaces, gold highlights, no gradients or glow */
  --royal:var(--purple); --trim:var(--gold); --accent:var(--purple);
  --teal:#1f8a5b; --amber:#b07400; --g1:var(--gold-d);
  --grad:linear-gradient(var(--purple), var(--purple));
  --hl:linear-gradient(var(--gold-d), var(--gold-d));
}

/* light cream/lavender magazine field */
.stApp{ background:var(--bg); }
html, body, [class*="css"]{ font-family:var(--font-body); color:var(--ink);
  font-variant-numeric:tabular-nums; }

[data-testid="stHeader"]{ background:transparent; }
/* no sidebar anywhere in this app — hide Streamlit's collapsed-sidebar
   toggle so there's no dangling entry point to an empty panel. */
[data-testid="stSidebarCollapsedControl"]{ display:none !important; }

/* headings — heavy condensed caps. h2 = magazine "panel" bar. */
h1,h2,h3{ font-family:var(--font-display) !important; font-weight:600 !important; letter-spacing:2px; text-transform:uppercase; }
h1, h1 *{ color:var(--purple) !important; }
h2{ background:var(--purple); border-bottom:3px solid var(--gold);
  padding:9px 14px; display:flex; align-items:center; box-shadow:5px 5px 0 rgba(123,91,216,.18); }
h2, h2 *{ color:#fff !important; }
h3, h3 *{ color:var(--purple-d) !important; }

/* brush-script wordmark — purple fill, gold outline, drop shadow */
.neon-logo{ font-family:'Pacifico', cursive; color:var(--purple-l); line-height:1;
  -webkit-text-stroke:3px var(--gold);
  text-shadow:4px 4px 0 var(--purple-d);
  transform:rotate(-3deg); display:inline-block; white-space:nowrap; }
.neon-tag{ font-family:var(--font-body); letter-spacing:6px; font-weight:700; font-size:11px;
  color:var(--purple); text-transform:uppercase; margin-top:8px; }

.stButton>button{ font-family:var(--font-display); font-weight:600; letter-spacing:2px; text-transform:uppercase;
  background:var(--gold); color:var(--purple-d); border:none; border-radius:0; }
.stButton>button:hover{ background:var(--purple); color:#fff; box-shadow:0 0 0 2px var(--gold); }

/* ---- shared custom tables ---- */
/* No boxed card around tables — the gold header row + striped rows carry
   the structure, so the table sits directly on the page like everything else. */
.neonwrap{ overflow:auto; max-height:72vh; }
/* Plain rows on a bottom border, no card/box around the table — the gold
   underline on th and the row dividers are the only structure, so it reads
   as a list that sits on the page rather than a boxed data-grid. */
table.lb{ width:100%; border-collapse:collapse; font-family:var(--font-body); font-size:14px; }
table.lb th{ color:var(--muted); text-transform:uppercase; letter-spacing:1px;
  font-family:var(--font-display); font-weight:600; font-size:11px; text-align:left; padding:8px 10px;
  border-bottom:2px solid var(--gold); position:sticky; top:0; z-index:5; background:var(--bg); }
table.lb th.r{ text-align:right; }
table.lb td{ padding:7px 10px; border-bottom:1px solid var(--line); color:var(--ink); }
table.lb tr:hover td{ background:rgba(75,45,159,.04); }
table.lb tr.kept td{ background:linear-gradient(90deg, rgba(255,206,31,.30), rgba(255,206,31,.06)); }
table.lb tr.kept td:first-child{ box-shadow:inset 4px 0 0 var(--gold-d); }
.lb .rk{ font-family:var(--font-display); font-weight:600; color:var(--gold-d); width:34px; text-align:center; }
.lb .pl{ font-weight:600; color:var(--ink); }
.lb .pos{ color:var(--muted); font-size:11px; font-weight:600; white-space:nowrap; }
.lb .val{ font-family:var(--font-display); font-weight:600; color:#1c9b63; text-align:right; letter-spacing:1px; }
.lb .num{ text-align:right; color:var(--ink); }
.lb .kept-badge{ color:var(--purple-d); background:var(--gold); font-weight:700; font-size:10px;
  font-family:var(--font-display); font-weight:600; padding:1px 6px; text-transform:uppercase; letter-spacing:1px; }
.lb .rk-badge{ color:var(--purple-d); background:var(--gold); font-weight:700; font-size:10px;
  font-family:var(--font-display); font-weight:600; padding:1px 6px; text-transform:uppercase; letter-spacing:1px; margin-left:4px; }
.lb .fa-tag{ color:var(--cyan); font-weight:600; font-size:12px; font-style:italic; }
table.lb tr.fa td{ background:rgba(35,144,192,.08); }
table.lb tr.rd-sep td{ background:var(--purple-d); color:var(--gold); font-family:var(--font-display); font-weight:600;
  letter-spacing:2px; text-transform:uppercase; font-size:12px; padding:5px 12px;
  position:sticky; top:38px; z-index:4; }

/* purple-duotone, gold-framed headshots (full colour on hover) */
.hs{ width:32px; height:32px; border-radius:4px; object-fit:cover; vertical-align:middle;
  background:#ece5fb; border:2px solid var(--gold-d); margin-right:9px;
  filter:grayscale(1) contrast(1.05) sepia(.55) hue-rotate(205deg) saturate(1.9) brightness(1.02);
  transition:filter .15s; }
.hs:hover{ filter:none; }
/* Round, full-color (no duotone) at this size — the stylized filter reads
   fine at 32px+ elsewhere on the site but turns to mush at grid size. A
   two-layer ring (solid white, then a dark hairline outside it) keeps the
   photo visually separated from the cell's tint no matter how pale that
   tint is — a single white ring nearly disappears against a light tint. */
.hs-sm{ width:32px; height:32px; border-radius:50%; object-fit:cover; flex:none;
  background:#ece5fb; border:2px solid #fff;
  box-shadow:0 0 0 1px rgba(42,26,94,.4); }
.dbplayer{ display:flex; align-items:center; gap:7px; margin-top:3px; width:100%; }
.dbplayer-txt{ min-width:0; line-height:1.2; flex:1 1 auto; }
.dbplayer-txt b{ display:-webkit-box; -webkit-box-orient:vertical; -webkit-line-clamp:2;
  overflow:hidden; font-size:11.5px; font-weight:700; white-space:normal; }
.dbplayer-txt .pos{ font-size:9px; white-space:nowrap; }
.posdot{ display:inline-block; width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;}
.p-QB{background:var(--gold-d);} .p-RB{background:var(--purple-l);} .p-WR{background:var(--cyan);} .p-TE{background:var(--red);}

/* stat cards (Superlatives, lottery draw order) — thin border + left accent
   rail, no drop shadow or gold top-bar, echoing the Draft Capital rows and
   contract cards rather than a heavier boxed style of its own. */
.kcards{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
.kcard{ border:1px solid var(--line); border-radius:10px; background:#fff;
  padding:12px 14px; position:relative; overflow:hidden; box-shadow:0 2px 6px rgba(75,45,159,.05); }
.kcard::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--gold-d); }
.kcard h4{ font-family:var(--font-display); font-weight:600; font-size:10.5px; letter-spacing:.6px;
  text-transform:uppercase; color:var(--muted); margin:0 0 4px; }
.kcard .who{ font-family:var(--font-display); font-weight:600; font-size:16px; color:var(--purple-d); }
.kcard .sub{ font-size:11.5px; color:var(--muted); margin-top:3px; }

/* lottery draw-order reveal — a single-line row list, same idea as the
   Draft Capital rows, instead of a grid of boxed cards. */
.draw-list{ display:flex; flex-direction:column; gap:6px; }
.draw-row{ display:flex; align-items:center; gap:12px; border:1px solid var(--line);
  border-radius:10px; background:#fff; padding:10px 14px; box-shadow:0 2px 6px rgba(75,45,159,.05); }
.draw-row .pickno{ font-family:var(--font-display); font-weight:600; font-size:18px; color:var(--gold-d);
  width:28px; text-align:center; flex:none; }
.draw-row .who{ font-family:var(--font-display); font-weight:600; font-size:15px; color:var(--purple-d); }
.draw-row .sub{ font-size:11.5px; color:var(--muted); }

/* draft board */
/* opaque base so the page's own decorative diagonal-line texture can't
   show through a cell's translucent state color (traded/conflict/position
   tints are all rgba, same reason table.lb needed this) */
table.dboard{ width:100%; border-collapse:collapse; table-layout:fixed; font-family:var(--font-body); font-size:12px; background:#fff; }
table.dboard th{ background:var(--gold); color:var(--purple-d); text-align:center; font-family:var(--font-display); font-weight:600;
  font-size:11px; padding:5px; border:1px solid #fff; text-transform:uppercase; letter-spacing:1px; }
.dbcell{ border:1px solid var(--line); padding:4px 5px; vertical-align:top; height:64px; }
table.dboard td.dbcell{ padding:3px 4px; }
.dbpick{ color:var(--muted); font-size:9px; white-space:nowrap; }
.db-base{ background:#faf7ff; color:#8a7fb3; }
.db-traded{ background:rgba(255,206,31,.28); color:var(--gold-d); }
.db-conflict{ background:rgba(214,51,108,.14); color:#b3235a; box-shadow:inset 0 0 0 1px rgba(214,51,108,.4); }
.db-rd{ background:var(--purple); color:var(--gold); font-family:var(--font-display); font-weight:600; text-align:center; white-space:nowrap; }
.db-open{ background:#fff; color:var(--muted); }
.dbtrade{ display:block; margin-top:2px; font-size:8px; color:var(--gold-d); font-weight:600; white-space:nowrap; }
.db-open.db-onclock{ background:rgba(255,206,31,.30); box-shadow:inset 0 0 0 2px var(--gold-d);
  animation:onclock-pulse 2s ease-in-out infinite; }
@keyframes onclock-pulse{ 0%,100%{ box-shadow:inset 0 0 0 2px var(--gold-d);} 50%{ box-shadow:inset 0 0 0 2px rgba(201,151,0,.35);} }
@media (prefers-reduced-motion: reduce){ .db-open.db-onclock{ animation:none !important; } }

/* live draft: on-the-clock banner + pick-entry panel */
.ld-clock{ display:flex; align-items:center; justify-content:space-between; gap:14px;
  background:#fff; border:2px solid var(--gold); border-radius:12px; padding:14px 18px; margin-bottom:14px; }
.ld-clock .who{ font-family:var(--font-display); font-weight:600; font-size:19px; color:var(--purple-d); }
.ld-clock .meta{ font-size:12px; color:var(--muted); margin-top:2px; }
.ld-clock .badge{ font-family:var(--font-display); font-weight:600; font-size:12px; background:var(--gold); color:var(--purple-d);
  padding:6px 12px; border-radius:999px; white-space:nowrap; }
.ld-recent{ display:flex; flex-direction:column; gap:6px; }
.ld-recent-row{ display:flex; align-items:center; gap:10px; padding:7px 10px; border:1px solid var(--line);
  border-radius:9px; font-size:12.5px; }
.ld-recent-row .pk{ font-family:var(--font-display); font-weight:600; color:var(--gold-d); width:34px; flex:none; }
.ld-recent-row .nm{ font-weight:700; flex:1; }

/* top bar — centered script-logo masthead band, on every page, with the
   phase status line underneath; a gold rule closes the whole band off. */
.kbar{ display:flex; flex-direction:column; align-items:center;
  gap:2px; text-align:center; padding:16px 20px 13px; margin-bottom:8px;
  border-bottom:3px solid var(--gold); }
.khome{ text-decoration:none !important; line-height:1; }
.khome .neon-logo{ font-size:30px; -webkit-text-stroke-width:2px; }
.khome .neon-tag{ margin-top:4px; }

/* thin phase status line, persistent on every page, inside the top bar
   band above the gold rule (replaces the old corner liquid-ring chip). */
.status-line{ display:flex; align-items:center; justify-content:center; gap:6px;
  margin-top:9px; font-family:var(--font-body); font-weight:700; font-size:11.5px;
  color:var(--purple-d); text-transform:uppercase; letter-spacing:.4px; }
.status-line .dot{ width:5px; height:5px; border-radius:50%; background:var(--gold-d); flex:none; }
.status-line .muted{ color:var(--muted); font-weight:500; text-transform:none; letter-spacing:0; }

/* fixed bottom pill nav — replaces the old static top bar. Leave room at
   the foot of the page so content never sits under it. */
[data-testid="stAppViewContainer"] .block-container{ padding-bottom:92px !important; }
.bottom-bar-wrap{ position:fixed; left:0; right:0; bottom:max(16px, env(safe-area-inset-bottom)); display:flex;
  justify-content:center; z-index:1000; pointer-events:none; }
.bottom-bar{ pointer-events:auto; display:flex; align-items:center; gap:2px;
  background:rgba(255,255,255,.97); backdrop-filter:blur(10px);
  border:2px solid var(--purple); border-radius:999px; padding:5px 8px;
  box-shadow:0 12px 30px rgba(75,45,159,.28); }
.navlink{ font-family:var(--font-display); font-weight:600; text-transform:uppercase; letter-spacing:.6px; font-size:12px;
  color:var(--purple) !important; text-decoration:none !important; padding:9px 16px !important;
  border-radius:999px !important; border:none !important; background:none; transition:opacity .2s, background .2s;
  white-space:nowrap; opacity:.72; cursor:pointer; touch-action:manipulation;
  -webkit-tap-highlight-color:transparent; user-select:none; }
.navlink:hover{ opacity:1; }
.navlink.active{ opacity:1; background:var(--gold); color:var(--purple-d) !important; }

/* bottom-bar popover — Pre-Season / In-Season drill down into their
   sub-pages from a sheet anchored above the bar, instead of jumping
   straight to a page and landing at the top of a long nested-tabs stack. */
.bb-scrim{ position:fixed; inset:0; background:rgba(42,26,94,0); pointer-events:none;
  transition:background .25s; z-index:998; }
.bb-scrim.on{ background:rgba(42,26,94,.35); pointer-events:auto; }
.bb-pop{ position:fixed; left:50%; bottom:76px; transform:translate(-50%,10px) scale(.96);
  width:min(340px, calc(100% - 32px)); background:#fff; border:2px solid var(--purple);
  border-radius:16px; padding:8px; box-shadow:0 16px 44px rgba(42,26,94,.35); opacity:0;
  pointer-events:none; transition:opacity .2s ease, transform .2s ease; z-index:999; }
.bb-pop.on{ opacity:1; pointer-events:auto; transform:translate(-50%,0) scale(1); }
.bb-pop-head{ display:flex; align-items:center; gap:8px; padding:8px 10px 10px; }
.bb-pop-title{ font-family:var(--font-display); font-weight:600; font-size:12px; text-transform:uppercase;
  letter-spacing:.5px; color:var(--purple); }
/* every leaf in the section, one flat list — no group-then-leaf drill-down */
.bb-pop-list{ max-height:min(360px, 60vh); overflow-y:auto; }
.bb-sec-label{ font-family:var(--font-display); font-weight:600; font-size:10.5px; font-weight:400;
  letter-spacing:.6px; text-transform:uppercase; color:var(--gold-d); padding:10px 12px 3px; }
.bb-sec-label:first-child{ padding-top:4px; }
.bb-pop-item{ display:block; padding:10px 12px;
  border-radius:10px; font-family:var(--font-body); font-size:13.5px; font-weight:600; color:var(--ink) !important;
  text-decoration:none !important; cursor:pointer; transition:background .15s;
  touch-action:manipulation; -webkit-tap-highlight-color:transparent; }
.bb-pop-item:hover{ background:var(--panel2); }
.bb-pop-item.leaf-active{ background:rgba(255,206,31,.22); }
.bb-pop-item.leaf-active .lbl{ color:var(--purple-d); }

/* sub-tabs (st.tabs) -> gold accent */
[data-baseweb="tab-list"]{ border-bottom:2px solid var(--line) !important; }
button[data-baseweb="tab"] [data-testid="stMarkdownContainer"] p{ font-family:var(--font-display); font-weight:600; letter-spacing:1px; text-transform:uppercase; font-size:14px; }
[data-baseweb="tab-highlight"]{ background:var(--gold-d) !important; }
button[data-baseweb="tab"][aria-selected="true"]{ color:var(--gold-d) !important; }

/* ---------------- mobile ---------------- */
/* per-team collapsible contract-card sections — plain HTML <details>/<summary>
   instead of st.expander, so each one can carry its own accent color. */
details.team-details{ border:1px solid var(--line); border-left:4px solid var(--purple);
  background:#fff; margin-bottom:10px; overflow:hidden; box-shadow:0 4px 12px rgba(75,45,159,.06); }
details.team-details summary{ list-style:none; cursor:pointer; padding:13px 16px;
  font-family:var(--font-display); font-weight:600; letter-spacing:.3px; font-size:15px; color:var(--purple-d);
  transition:background .12s; }
details.team-details summary::-webkit-details-marker{ display:none; }
details.team-details summary:hover{ background:rgba(255,206,31,.10); }
details.team-details .team-details-body{ padding:6px 16px 16px; }
details.team-details .empty-note{ color:var(--muted); font-size:13px; padding:0 0 4px; margin:0; }

/* two-tone heading accent — wrap the one word that matters in <span class="g"> */
.g{ background:none; -webkit-text-fill-color:var(--purple-l); color:var(--purple-l); }
/* a bare h2 stays the filled purple/gold panel bar; opt any heading into the
   two-tone look (no filled bar, no white text) with this class instead */
h2.two-tone{ background:none !important; border:none !important; box-shadow:none !important;
  padding:0 !important; display:block !important; color:var(--purple) !important;
  font-size:1.55rem !important; margin-bottom:4px !important; }
h2.two-tone, h2.two-tone *{ color:var(--purple) !important; }
h2.two-tone .g{ -webkit-text-fill-color:var(--purple-l) !important; color:var(--purple-l) !important; }

/* ---------------- glance panel: liquid-fill gauges ---------------- */
.glance{ border:1px solid var(--gold-d); background:#fff; margin:14px 0 26px;
  padding:20px 26px; box-shadow:0 8px 26px rgba(75,45,159,.10); position:relative; }
.glance::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--gold); }
.glance-stats{ display:flex; gap:40px; flex-wrap:wrap; }
.gstat{ display:flex; align-items:center; gap:16px; }
.liq-ring{ position:relative; display:inline-flex; }
.liq-ring svg{ display:block; }
.liq-val{ position:absolute; inset:0; display:flex; flex-direction:column; align-items:center;
  justify-content:center; text-align:center; line-height:1.1; pointer-events:none; }
.liq-val b{ font-family:var(--font-display); font-weight:600; color:var(--purple-d); }
.liq-val small{ font-size:8px; color:var(--muted); text-transform:uppercase; letter-spacing:.4px; }
.gstat .txt .lbl{ font-family:var(--font-display); font-weight:600; font-size:11px; letter-spacing:.8px; text-transform:uppercase; color:var(--purple); }
.gstat .txt .sub{ font-size:12.5px; color:var(--muted); margin-top:3px; max-width:190px; }
.liq-bob{ transform:translateY(var(--sy,0px)); }
.liq-wv.front{ animation:liq-front 7s linear infinite; }
.liq-wv.back{ animation:liq-back 11s linear infinite; }
@keyframes liq-front{ from{ transform:translateX(0);} to{ transform:translateX(-200px);} }
@keyframes liq-back{ from{ transform:translateX(0);} to{ transform:translateX(200px);} }
@media (prefers-reduced-motion: reduce){ .liq-wv.front, .liq-wv.back{ animation:none !important; } }

/* ---------------- lean chips + value coloring (shared) ---------------- */
.val-pos{ color:#1c9b63; font-weight:600; }
.val-neg{ color:var(--red); font-weight:600; }
.chip{ display:inline-block; font-family:var(--font-display); font-weight:600; font-size:10px; letter-spacing:.6px;
  text-transform:uppercase; padding:3px 9px; }
.chip.win-now{ background:rgba(28,155,99,.14); color:#1c9b63; border:1px solid rgba(28,155,99,.4); }
.chip.rebuild{ background:rgba(214,51,108,.12); color:var(--red); border:1px solid rgba(214,51,108,.4); }
.chip.balanced{ background:rgba(75,45,159,.08); color:var(--purple); border:1px solid rgba(75,45,159,.3); }

/* ---------------- draft capital: ranked, expandable cards ---------------- */
.dc-list{ display:flex; flex-direction:column; gap:10px; }
details.dc-row{ background:#fff; border:1px solid var(--line); border-radius:12px; overflow:hidden;
  box-shadow:0 3px 10px rgba(75,45,159,.06); }
details.dc-row summary{ list-style:none; cursor:pointer; display:grid;
  grid-template-columns:2.2rem 1fr auto; align-items:start; gap:14px; padding:14px 18px;
  transition:background .12s; }
details.dc-row summary::-webkit-details-marker{ display:none; }
details.dc-row summary:hover{ background:rgba(255,206,31,.08); }
.dc-rank{ font-family:var(--font-display); font-weight:600; font-size:17px; color:var(--gold-d); text-align:center; }
.dc-main b{ display:block; font-family:var(--font-body); font-weight:700; font-size:15px; color:var(--ink); }
.dc-meta{ display:flex; gap:6px; flex-wrap:wrap; margin-top:7px; }
.dc-stat{ text-align:right; min-width:110px; }
.dc-stat b{ display:block; font-family:var(--font-display); font-weight:600; font-size:19px; line-height:1; }
.dc-stat small{ font-size:9.5px; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
.dc-bar{ display:block; width:90px; height:5px; border-radius:3px; background:var(--panel2);
  overflow:hidden; margin:6px 0 0 auto; }
.dc-bar span{ display:block; height:100%; }
.dc-bar span.val-pos{ background:#1c9b63; }
.dc-bar span.val-neg{ background:var(--red); }
.dc-body{ padding:2px 18px 18px; border-top:1px solid var(--line); margin-top:2px; }

/* ---------------- contract cards (full browse grid) ---------------- */
.kr-section{ margin-bottom:26px; }
.kr-section-head{ display:flex; align-items:baseline; justify-content:space-between; gap:14px; margin-bottom:12px; }
.kr-section-head h3{ font-family:var(--font-display) !important; font-weight:600 !important; font-size:20px !important;
  font-weight:400 !important; letter-spacing:.3px; margin:0 !important; color:var(--purple-d) !important; }
.kr-section-head .tag{ font-family:var(--font-body); font-weight:600; font-size:10.5px; letter-spacing:.6px;
  text-transform:uppercase; color:var(--purple); }
.contract-grid{ display:grid; grid-template-columns:repeat(2,1fr); gap:12px; }
.ccard{ border:1px solid var(--line); border-radius:0; padding:13px 15px 14px; position:relative;
  background:#fff; overflow:hidden; box-shadow:0 4px 12px rgba(75,45,159,.06); transition:box-shadow .15s; }
.ccard:hover{ box-shadow:0 6px 18px rgba(75,45,159,.14); }
.ccard::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--muted); }
.ccard.pos-QB::before{ background:var(--gold-d); }
.ccard.pos-RB::before{ background:var(--purple-l); }
.ccard.pos-WR::before{ background:var(--cyan); }
.ccard.pos-TE::before{ background:var(--red); }
.ccard.wall{ box-shadow:inset 0 0 0 1px rgba(214,51,108,.5); }
.ccard.ineligible{ opacity:.55; }
.ccard-top{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }
.ccard h4{ font-family:var(--font-display); font-weight:600; font-size:17px; color:var(--purple-d); margin:0; letter-spacing:.2px; line-height:1.15; }
.ccard .pos{ font-size:11px; color:var(--muted); margin-top:1px; }
.ccard .cost{ text-align:right; }
.ccard .cost b{ font-family:var(--font-display); font-weight:600; font-size:17px; color:var(--gold-d); display:block; line-height:1; font-weight:400; }
.ccard .cost small{ font-size:9px; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
.ccard .pips{ display:flex; gap:4px; margin:8px 0 7px; }
.ccard .pip{ width:15px; height:6px; background:var(--line); }
.ccard .pip.on{ background:var(--purple); }
.ccard .badges{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:4px; }
.ccard .badge{ font-family:var(--font-body); font-weight:600; font-size:9.5px; letter-spacing:.3px; text-transform:uppercase;
  padding:3px 7px; border:1px solid var(--line); color:var(--muted); background:var(--panel2); }
.ccard .badge.rookie{ background:rgba(123,91,216,.12); border-color:rgba(123,91,216,.35); color:var(--purple); }
.ccard .badge.surplus-pos{ background:rgba(28,155,99,.12); border-color:rgba(28,155,99,.35); color:#1c9b63; }
.ccard .badge.surplus-neg{ background:rgba(214,51,108,.12); border-color:rgba(214,51,108,.35); color:var(--red); }
.ccard .note{ font-size:11.5px; color:var(--muted); margin-top:1px; }

/* ---------------- recent trades ---------------- */
.trades-wrap{ padding:6px 0; }
.trade{ padding:15px 0; border-bottom:1px solid var(--line); }
.trade:last-child{ border-bottom:none; padding-bottom:2px; }
.trade-teams{ font-size:15px; font-weight:600; margin-bottom:10px; color:var(--ink); }
.trade-teams .vs{ color:var(--muted); font-weight:400; font-size:12px; margin:0 6px; }
.trade-assets{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; }
.trade-assets div b{ display:block; font-size:9.5px; color:var(--muted); text-transform:uppercase;
  letter-spacing:.6px; margin-bottom:7px; font-weight:600; }
.chip.asset{ display:inline-block; font-size:11.5px; background:rgba(75,45,159,.06);
  border:1px solid rgba(75,45,159,.28); color:var(--purple-d); padding:4px 10px; border-radius:999px;
  margin:0 6px 6px 0; text-transform:none; font-family:var(--font-body); font-weight:500; letter-spacing:0; }
.trade-date{ font-size:10.5px; color:var(--muted); margin-top:10px; text-transform:uppercase; letter-spacing:.5px; }

/* ---------------- lottery bars ---------------- */
.lot-wrap{ padding:12px 0 18px; border-top:1px solid var(--line); margin-bottom:8px; }
.lot-head{ display:flex; align-items:baseline; justify-content:space-between; gap:14px; margin-bottom:14px; }
.lot-head h4{ font-family:var(--font-display); font-weight:600; font-size:16px; color:var(--purple-d); margin:0; letter-spacing:.3px; }
.lot-eyebrow{ font-family:var(--font-body); font-weight:600; font-size:10.5px; letter-spacing:.5px; text-transform:uppercase; color:var(--muted); }
.lot-row{ display:flex; align-items:center; gap:14px; padding:8px 0; }
.lot-label{ width:170px; flex:0 0 auto; }
.lot-label b{ display:block; font-size:13.5px; font-weight:600; color:var(--ink); }
.lot-label small{ display:block; font-size:10px; color:var(--muted); margin-top:1px; }
.lot-track{ flex:1; height:20px; background:var(--panel2); border-radius:2px; position:relative; overflow:hidden; }
.lot-fill{ height:100%; background:linear-gradient(90deg, var(--purple), var(--purple-l) 55%, var(--gold-d));
  display:flex; align-items:center; justify-content:flex-end; padding-right:8px; font-size:10.5px;
  color:#fff; font-weight:600; font-variant-numeric:tabular-nums; min-width:2px; }
.lot-pos{ width:26px; text-align:right; font-family:var(--font-display); font-weight:600; color:var(--gold-d); font-size:13px; }

/* ---------------- mobile ---------------- */
/* Kept last in the stylesheet on purpose: every rule in here overrides a
   same-specificity base rule declared earlier (e.g. table.lb, .dc-stat,
   .lot-row), and CSS breaks ties by source order, not by media-query
   presence — a mobile override placed before its base rule loses. */
@media (max-width: 640px){
  /* hide Streamlit's own in-app chrome — the bottom bar is the site's only
     nav here and this stuff just eats space over it. */
  [data-testid="stToolbar"], [data-testid="stDecoration"],
  [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"],
  #MainMenu, footer{ display:none !important; }

  .neon-logo{ font-size:40px !important; -webkit-text-stroke-width:2px; }
  .neon-tag{ font-size:8px; letter-spacing:4px; }
  [data-testid="stAppViewContainer"] .block-container{ padding-bottom:84px !important; }
  .bottom-bar-wrap{ bottom:max(10px, env(safe-area-inset-bottom)); }
  .bottom-bar{ gap:0; padding:4px; }
  .navlink{ font-size:10px; padding:8px 11px !important; letter-spacing:.3px; }
  .bb-pop{ bottom:68px; }
  h1{ font-size:1.5rem !important; }
  h2{ font-size:1.25rem !important; }
  h3{ font-size:1.15rem !important; }
  .block-container{ padding-left:.6rem !important; padding-right:.6rem !important; padding-top:2.5rem !important; }
  .neonwrap{ max-height:none !important; }

  

  table.lb{ font-size:11px; }
  table.lb th{ padding:5px 5px; font-size:9px; }
  table.lb td{ padding:4px 5px; }
  .hs{ width:24px; height:24px; margin-right:5px; }
  .lb .rk{ width:20px; }
  .lb .kept-badge, .lb .rk-badge{ font-size:8px; padding:1px 4px; margin-left:3px; }
  .lb-value th:nth-child(5), .lb-value td:nth-child(5),
  .lb-value th:nth-child(7), .lb-value td:nth-child(7){ display:none; }
  .lb-rook th:nth-child(6), .lb-rook td:nth-child(6){ display:none; }
  .lb-odds th:nth-child(8), .lb-odds td:nth-child(8){ display:none; }

  .kcards{ grid-template-columns:1fr 1fr; gap:8px; }
  .kcard{ padding:10px 11px; }
  .kcard .who{ font-size:14px; }

  table.dboard{ font-size:9px; }
  table.dboard th{ padding:3px 2px; font-size:8px; }
  .dbcell{ height:auto; }
  table.dboard td.dbcell{ padding:2px 3px; }
  .db-rd{ font-size:10px; }
  .hs-sm{ display:none; }
  .dbplayer{ gap:0; }
  .dbplayer-txt b{ font-size:9.5px; }
  .dbplayer-txt .pos{ font-size:8px; }

  .glance-stats{ gap:20px !important; }
  .contract-grid{ grid-template-columns:1fr !important; }
  details.team-details summary{ font-size:13px; padding:11px 13px; }
  details.dc-row summary{ grid-template-columns:1.6rem 1fr; padding:12px 14px; }
  .dc-stat{ grid-column:1 / -1; text-align:left; margin-top:8px; }
  .dc-bar{ margin:6px 0 0; }

  .trade-assets{ grid-template-columns:1fr; gap:10px; }

  /* lottery bar rows: stack label above the bar, like kreeper's mobile fix */
  .lot-head{ flex-direction:column; align-items:flex-start; gap:2px; }
  .lot-row{ flex-wrap:wrap; row-gap:4px; }
  .lot-label{ width:auto; flex:1 1 100%; }
  .lot-track{ flex:1 1 auto; }
}
/* masthead — a full-bleed gradient band, not an inset bar. Streamlit caps its
   content column and pads it, so the band is pushed back out to the viewport
   edges with negative margins sized off that padding; 100vw would overflow by
   the scrollbar's width and produce a horizontal scroll. */
.masthead{ display:flex; align-items:center; justify-content:space-between; gap:24px;
  flex-wrap:wrap; background:var(--grad); border-bottom:4px solid var(--trim);
  margin:0 calc(-1 * var(--block-pad)) 26px;
  padding:14px var(--block-pad); }
.mh-home{ text-decoration:none !important; line-height:1; }
.mh-home .neon-logo{ font-size:26px; margin:0; }
/* on the gradient the wordmark is solid white — the logo's own gradient fill
   would be invisible against it */
.masthead .neon-logo .kl-unused{ background:none !important; -webkit-text-fill-color:#fff !important;
  color:#fff !important; text-shadow:0 2px 12px rgba(0,0,0,.28); }
/* season line — the in-season stand-in for the phase chip */
.mh-meta{ font-family:var(--font-body); font-size:11px; letter-spacing:2.4px;
  text-transform:uppercase; color:rgba(255,255,255,.88); white-space:nowrap; }
.masthead .topbar-chip{ background:rgba(0,0,0,.24); border-color:rgba(255,255,255,.26); }
.masthead .topbar-chip .txt .lbl{ color:#fff; }
.masthead .topbar-chip .txt .sub{ color:rgba(255,255,255,.8); }

/* ---- Home: the mock's own surfaces ---- */

/* money bowls — four big liquid rings across, each with a label and a line
   of explanation under it */
.money-bowls{ display:grid; grid-template-columns:repeat(4,1fr); gap:18px; margin-bottom:18px; }
.money-bowls .bowl{ text-align:center; }
.money-bowls .bowl .liq-ring{ margin:0 auto 10px; }
.money-bowls .bowl .liq-val b{ font-size:23px !important; }
.money-bowls .bl{ font-size:10.5px; letter-spacing:1.8px; text-transform:uppercase; color:var(--ink); }
.money-bowls .bn{ font-size:11px; color:var(--muted); margin-top:4px; line-height:1.4; }
@media (max-width: 760px){
  .money-bowls{ grid-template-columns:repeat(2,1fr); gap:14px; }
}

/* two-line table cell: the thing in bold, who owns it underneath */
table.lb td.two{ padding-top:9px; padding-bottom:9px; }
table.lb td.two b{ display:block; font-weight:700; font-size:13.5px; color:var(--ink); }
table.lb td.two span{ display:block; font-size:11px; color:var(--muted); margin-top:1px; }
table.lb td.two.w b{ color:var(--teal); }
table.lb td.two b .pos{ display:inline !important; color:var(--muted); font-size:10.5px;
  font-weight:400; margin-left:5px; }

/* power bar inside a table row */
/* a plain table cell: display:flex on a <td> drops it out of the row's
   table layout, which floated the bar above its row on phones */
table.lb td.pw{ vertical-align:middle; min-width:56px; }
table.lb th{ white-space:nowrap; }
.pbar{ flex:1; height:5px; background:rgba(36,26,64,.08); border-radius:3px;
  overflow:hidden; min-width:60px; }
.pbar i{ display:block; height:100%; background:var(--hl); }

/* movement / status chip */
.chip{ display:inline-block; font-size:9.5px; letter-spacing:1.1px; text-transform:uppercase;
  border:1px solid var(--line); border-radius:999px; padding:3px 9px; color:var(--muted);
  white-space:nowrap; }
.chip.good{ color:var(--teal); border-color:rgba(31,138,91,.4); }
.chip.bad{ color:var(--red); border-color:rgba(214,51,108,.4); }

/* the explanatory paragraph that follows a dense table */
.sec-note{ font-size:12px; color:var(--muted); line-height:1.6; margin:10px 0 0; max-width:780px; }
.sec-note b{ color:var(--ink); font-weight:600; }

/* section header — title, a hairline rule running to the right edge, and a
   right-aligned micro-caption. Replaces bare <h2> + st.caption stacked, which
   left every section starting with two left-aligned lines and no horizontal
   structure. */
.sechead{ display:flex; align-items:center; gap:16px; margin:34px 0 14px; }
.sechead.page{ margin-top:4px; }
.sechead h2{ font-family:var(--font-display); font-weight:var(--display-wt); font-size:1.55rem; letter-spacing:.4px;
  text-transform:uppercase;
  margin:0 !important; white-space:nowrap; color:var(--ink); }
.sechead .rule{ flex:1; height:1px; background:var(--line); }
.sechead .cap{ font-size:10px; letter-spacing:1.8px; text-transform:uppercase;
  color:var(--muted); white-space:nowrap; }
@media (max-width: 640px){
  .sechead{ gap:10px; margin:24px 0 12px; }
  .sechead .cap{ display:none; }
}

/* the masthead team dropdown: same sheet, hung from the top-right chip */
.bb-pop.bb-pop-me{ top:64px; bottom:auto; left:auto; right:16px; transform:translateY(-8px) scale(.98);
  width:min(300px, calc(100% - 32px)); }
.bb-pop.bb-pop-me.on{ transform:none; }
.bb-pop-item .sub{ font-size:11px; font-weight:500; color:var(--muted); margin-left:12px; white-space:nowrap; }
span.mechip{ cursor:pointer; user-select:none; }
/* ================= This Week: Draft Room layout, Kreeper skin =================
   Hero matchup card, action cards, panel tables, the slate, matchup cards and
   slot-by-slot rows. Ported from the approved remock. */
.mechip{ display:inline-flex; align-items:center; gap:8px; background:rgba(0,0,0,.26);
  border:1px solid rgba(255,255,255,.28); border-radius:999px; padding:4px 12px 4px 4px;
  font-size:12px; font-weight:600; color:#fff !important; text-decoration:none !important; white-space:nowrap; }
.mechip i{ font-style:normal; opacity:.7; }
/* the site-wide link rule ([data-testid=stMarkdownContainer] a, !important)
   would paint the chip, its initials and the picker cards accent-purple */
[data-testid="stMarkdownContainer"] a.mechip{ color:#fff !important; }
[data-testid="stMarkdownContainer"] a.tp{ color:var(--ink) !important; }
[data-testid="stMarkdownContainer"] span.av.av{ color:#fff !important; }   /* .av.av: beats the span reset below */
.mh-right{ display:flex; align-items:center; gap:14px; }
.av{ width:46px; height:46px; border-radius:10px; background:var(--purple); color:#fff; display:inline-flex;
  align-items:center; justify-content:center; font-family:var(--font-display); font-size:17px;
  font-weight:700; flex:0 0 auto; }
.av.sm{ width:24px; height:24px; border-radius:50%; font-size:10px; }
.av.dim{ background:#8f84b3; }
.eyebrow{ font-size:10px; font-weight:600; letter-spacing:1.6px; text-transform:uppercase;
  color:var(--muted); margin:0 0 8px; }
.eyebrow.pad{ margin:16px 0 8px; }

.hero{ position:relative; border:1px solid var(--line); border-radius:14px; overflow:hidden; padding:18px 18px 0;
  background:var(--panel); border-top:3px solid var(--royal); }
.hrow{ display:flex; align-items:center; justify-content:space-between; gap:12px; }
.who{ display:flex; align-items:center; gap:12px; min-width:0; }
.who.r{ text-align:right; }
.who b{ display:block; font-family:var(--font-display); font-size:21px; font-weight:600; line-height:1.1; }
.who em{ font-style:normal; font-size:10px; font-weight:600; letter-spacing:1.2px; text-transform:uppercase; color:var(--muted); }
.wkpill{ font-size:10.5px; font-weight:600; letter-spacing:1.4px; color:var(--purple-d); border:1px solid rgba(255,255,255,.22);
  background:rgba(75,45,159,.22); border-radius:999px; padding:4px 12px; white-space:nowrap; }
.hnum{ display:flex; align-items:baseline; justify-content:space-between; margin:10px 0 8px; }
.hnum .big{ font-family:var(--font-display); font-size:58px; font-weight:600; line-height:1; }
.big.dim{ color:var(--muted); }
.hk{ font-size:10px; font-weight:600; letter-spacing:1.8px; color:var(--muted); text-transform:uppercase; }
.wpbar{ height:10px; border-radius:6px; background:rgba(36,26,64,.08); overflow:hidden; }
.wpbar.sm{ height:6px; margin:10px 0 6px; }
.wpbar i{ display:block; height:100%; background:var(--hl); border-radius:6px; }
.hrow.lab{ margin:8px 0 14px; font-size:11px; color:var(--muted); }
.hrow.lab b{ color:var(--teal); font-size:15px; }
.hcells{ display:grid; grid-template-columns:repeat(4,1fr); margin:0 -18px; border-top:1px solid var(--line); }
.hc{ padding:12px 18px 14px; border-left:1px solid var(--line); }
.hc:first-child{ border-left:none; }
.hc i{ display:block; font-style:normal; font-size:9.5px; font-weight:600; letter-spacing:1.5px; color:var(--muted); text-transform:uppercase; }
.hc b{ display:block; font-family:var(--font-display); font-size:24px; font-weight:600; margin:3px 0 1px; }
.hc b.good{ color:var(--teal); } .hc b.amber{ color:var(--amber); } .hc b.bad{ color:var(--red); }
.hc span{ font-size:11.5px; color:var(--muted); }
.lockline{ font-size:10.5px; font-weight:600; letter-spacing:1.4px; color:var(--muted); margin:14px 0 16px; text-transform:uppercase; }
.lockline b{ color:var(--g1); }

.todo{ --c:var(--amber); display:flex; gap:14px; align-items:center; background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:13px 14px; margin-bottom:8px; box-shadow:inset 3px 0 0 var(--c); }
.todo.bad{ --c:var(--red); } .todo.good{ --c:var(--teal); }
.todo .ic{ width:30px; height:30px; border-radius:8px; border:1px solid var(--c); color:var(--c);
  display:flex; align-items:center; justify-content:center; flex:0 0 auto; }
.todo b{ display:block; font-size:14px; font-weight:600; }
.todo span{ font-size:12px; color:var(--muted); }
.todo span b{ display:inline; color:var(--ink); }
.todo .tv{ margin-left:auto; text-align:right; }
.todo .tv b{ font-family:var(--font-display); font-size:22px; color:var(--c); }
.todo .tv i{ font-style:normal; font-size:9px; font-weight:600; letter-spacing:1.4px; color:var(--muted); }
.todo-foot{ font-size:12px; color:var(--muted); background:var(--panel); border:1px solid var(--line);
  border-radius:10px; padding:11px 14px; }
.todo-foot b{ color:var(--ink); }

table.dt{ width:100%; border-collapse:collapse; background:var(--panel); border:1px solid var(--line);
  border-radius:10px; overflow:hidden; font-size:13.5px; }
table.dt td{ padding:8px 12px; border-top:1px solid var(--line); vertical-align:middle; }
table.dt tr:first-child td{ border-top:none; }
table.dt td.two b{ display:block; font-weight:600; font-size:13.5px; }
table.dt td.two span{ display:block; font-size:10.5px; color:var(--muted); margin-top:2px; }
table.dt td.two.w b{ color:var(--teal); }
table.dt td.two b .pos{ display:inline !important; font-size:10px; color:var(--muted); font-weight:500; margin-left:4px; }
table.dt td.rk{ font-family:var(--font-display); font-weight:600; color:var(--muted); font-size:16px; width:30px; text-align:center; }
table.dt td.num{ text-align:right; white-space:nowrap; font-weight:500; }
table.dt td.mut{ color:var(--muted); }
table.dt tr.swap td{ background:rgba(176,116,0,.08); }
.slot{ display:inline-block; min-width:42px; text-align:center; font-size:10px; font-weight:700;
  border:1px solid; border-radius:6px; padding:3px 6px; }
td.barc{ width:30%; }
.bar{ height:6px; border-radius:4px; background:rgba(36,26,64,.08); overflow:hidden; }
.bar i{ display:block; height:100%; background:var(--hl); border-radius:4px; }

.strip{ display:grid; grid-template-columns:repeat(auto-fill,minmax(118px,1fr)); gap:6px; margin-bottom:6px; }
.gm{ display:grid; grid-template-columns:1fr auto; gap:1px 8px; background:var(--panel); border:1px solid var(--line);
  border-radius:8px; padding:8px 10px; font-size:12px; }
.gm b{ text-align:right; } .gm em{ grid-column:1/-1; font-style:normal; font-size:9.5px; font-weight:600;
  letter-spacing:1.2px; color:var(--muted); margin-top:3px; }
.gm.in{ border-color:rgba(31,138,91,.6); } .gm.in em{ color:var(--teal); }
.gm.pre{ border-color:rgba(201,151,0,.55); } .gm.pre em{ color:var(--g1); }
.gm.post{ opacity:.55; padding:6px 9px; font-size:11px; }

.lcard{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.lcard.mine{ border-color:rgba(75,45,159,.5); box-shadow:0 0 0 1px rgba(75,45,159,.2) inset; margin-bottom:12px; padding-bottom:4px; }
.lhead{ display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:10px; }
.lhead .two b{ font-family:var(--font-display); font-size:17px; font-weight:600; display:block; }
.lhead .two span{ font-size:10.5px; color:var(--muted); display:block; }
.lhead .two:last-child{ text-align:right; }
.lhead .two.w b{ color:var(--teal); }
.ls{ font-family:var(--font-display); font-size:30px; font-weight:600; display:flex; gap:8px; align-items:baseline; }
.ls span{ color:var(--muted); font-size:18px; } .ls .dim{ color:var(--muted); }
.lfoot{ display:flex; justify-content:space-between; font-size:10.5px; color:var(--muted); gap:8px; }
.lfoot b{ color:var(--ink); }
.lgrid{ display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.lgrid .lhead{ grid-template-columns:1fr; gap:4px; }
.lgrid .lhead .two:last-child{ text-align:left; }
.lgrid .ls{ font-size:24px; } .lgrid .lfoot .mid{ display:none; }
.forow{ display:grid; grid-template-columns:1fr 64px 1fr; align-items:center; border-top:1px solid var(--line);
  margin:0 -14px; padding:0 14px; }
.fo{ display:flex; align-items:center; justify-content:space-between; gap:10px; padding:8px 0; }
.fo.r{ flex-direction:row-reverse; text-align:right; }
.fn b{ display:block; font-size:13.5px; font-weight:600; }
.fn em{ font-style:normal; font-size:10px; color:var(--muted); }
.fp{ font-family:var(--font-display); font-size:20px; font-weight:600; }
.fo.live .fn em{ color:var(--g1); } .fo.inplay .fn em{ color:var(--teal); }
.fp .proj{ color:var(--muted); font-size:15px; }
.fp .proj::before{ content:"proj "; font-family:var(--font-body); font-size:9px; }
.fm{ display:flex; flex-direction:column; align-items:center; gap:3px; }
.fm i{ font-style:normal; font-size:10px; color:var(--muted); }
.fm i.pos{ color:var(--teal); } .fm i.neg{ color:var(--red); }
.gs{ display:none; }

.picker h3{ font-family:var(--font-display) !important; font-weight:600 !important; font-size:26px !important;
  text-transform:uppercase; margin:2px 0 6px !important; padding:0 !important; }
.picker p{ margin:0 0 14px; font-size:13px; line-height:1.55; color:var(--muted); }
.tpgrid{ display:grid; grid-template-columns:1fr 1fr; gap:8px; }
a.tp{ display:block; border:1px solid var(--line); border-radius:10px; padding:10px 12px; background:var(--panel2);
  text-decoration:none !important; color:var(--ink) !important; }
a.tp b{ display:block; font-size:13.5px; } a.tp em{ font-style:normal; font-size:11px; color:var(--muted); }
a.tp:hover, a.tp.on{ background:linear-gradient(var(--panel2),var(--panel2)) padding-box, var(--hl) border-box;
  border:1px solid transparent; }
.wk-cols{ display:grid; grid-template-columns:1fr 1.15fr; gap:20px; align-items:start; }

/* The theme forces every markdown <span> to --ink (!important) so Streamlit's
   own greys never leak in. These components colour their spans on purpose,
   so they reset to inherit and re-assert their own colours at a higher
   specificity. Slot chips carry their colour in --c because an inline
   `color` would lose to the !important too. */
[data-testid="stMarkdownContainer"] :is(.hero, .todo, .todo-foot, table.dt, .lcard, .strip, .picker, .mh-right, .lockline, .ktray, .kgrid) span{ color:inherit !important; }
[data-testid="stMarkdownContainer"] .hero .big.dim, [data-testid="stMarkdownContainer"] .ls .dim{ color:var(--muted) !important; }
[data-testid="stMarkdownContainer"] :is(.hk, .hc span, .todo div > span, table.dt td.two span, .lhead .two span, .ls span, .fp .proj, .kt span, .kc-top .pos, .ka){ color:var(--muted) !important; }
[data-testid="stMarkdownContainer"] .kgrid span.chip.amber.amber{ color:var(--amber) !important; border-color:rgba(176,116,0,.4); }
[data-testid="stMarkdownContainer"] span.chip.good.good{ color:var(--teal) !important; }
[data-testid="stMarkdownContainer"] span.chip.bad.bad{ color:var(--red) !important; }
/* .slot.slot: out-ranks the inherit reset above, which carries a table.dt */
[data-testid="stMarkdownContainer"] span.slot.slot{ color:var(--c, var(--muted)) !important; border-color:color-mix(in srgb, var(--c, #8a8a95) 35%, transparent);
  background:color-mix(in srgb, var(--c, #8a8a95) 8%, transparent); }

/* keeper outlook: the five-slot tray, then one card per player with his ladder */
.hero.kh{ padding:0; } .hero.kh .hcells{ margin:0; border-top:none; }
.ktray{ display:grid; grid-template-columns:repeat(5,1fr); gap:8px; }
.kt{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:12px 10px; text-align:center; }
.kt i{ display:block; font-style:normal; font-size:9.5px; font-weight:600; letter-spacing:1.4px; text-transform:uppercase; color:var(--muted); margin-bottom:8px; }
.kt .kh-img{ width:52px; height:52px; border-radius:50%; object-fit:cover; background:var(--panel2); display:block; margin:0 auto 8px; }
.kt b{ display:block; font-size:13px; font-weight:600; line-height:1.2; }
.kt span{ display:block; font-size:11px; margin-top:3px; }
.kt em{ font-style:normal; font-weight:600; } .kt em.good{ color:var(--teal); } .kt em.bad{ color:var(--red); }
.kt.empty{ border-style:dashed; opacity:.6; } .kt.empty b{ font-family:var(--font-display); font-size:20px; margin:18px 0 4px; }
.kgrid{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.kcard2{ display:flex; align-items:center; gap:12px; background:var(--panel); border:1px solid var(--line);
  border-radius:12px; padding:12px 14px; }
.kcard2.keep{ box-shadow:inset 3px 0 0 var(--teal); } .kcard2.next{ box-shadow:inset 3px 0 0 var(--amber); }
.kcard2.blocked{ opacity:.7; } .kcard2.cut{ opacity:.82; }
.kcard2 .kh-img{ width:44px; height:44px; border-radius:50%; object-fit:cover; background:var(--panel2); flex:0 0 auto; }
.kc-main{ flex:1; min-width:0; }
.kc-top{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.kc-top b{ font-size:14px; font-weight:600; } .kc-top .pos{ font-size:11px; }
.kc-top .chip{ margin-left:auto; }
.kladder{ display:flex; align-items:center; gap:6px; margin:8px 0 6px; flex-wrap:wrap; }
.ks{ display:inline-flex; flex-direction:column; align-items:center; background:var(--panel2); border:1px solid var(--line);
  border-radius:8px; padding:3px 9px; min-width:54px; }
.ks i{ font-style:normal; font-size:9px; font-weight:600; letter-spacing:1px; color:var(--muted); }
.ks b{ font-family:var(--font-display); font-size:15px; font-weight:600; }
.ks.now{ border-color:rgba(75,45,159,.55); background:rgba(75,45,159,.12); }
.ka{ font-size:12px; } .kb{ font-size:12px; color:var(--red) !important; font-weight:600; }
.kc-how{ font-size:11px; color:var(--muted); }
.kv{ text-align:right; flex:0 0 auto; }
.kv b{ display:block; font-family:var(--font-display); font-size:24px; font-weight:600; line-height:1; }
.kv i{ font-style:normal; font-size:9px; font-weight:600; letter-spacing:1.2px; color:var(--muted); text-transform:uppercase; }
.kv.good b{ color:var(--teal); } .kv.bad b{ color:var(--red); }

@media (max-width: 760px){
  .wk-cols{ grid-template-columns:1fr; }
  .hero .wkpill, .mh-right .mh-meta{ display:none; }
  .who{ flex:1 1 0; gap:8px; } .who.r{ justify-content:flex-end; }
  .who b{ font-size:15px; } .who em{ font-size:8.5px; letter-spacing:.8px; }
  .av{ width:34px; height:34px; font-size:13px; border-radius:8px; }
  .hnum .big{ font-size:42px; }
  .hcells{ grid-template-columns:1fr 1fr; } .hc:nth-child(3){ border-left:none; }
  .hc:nth-child(n+3){ border-top:1px solid var(--line); } .hc b{ font-size:20px; }
  .lgrid{ grid-template-columns:1fr; }
  .lhead .two b{ font-size:14px; } .ls{ font-size:22px; }
  .gl{ display:none; } .gs{ display:inline; } .fp{ font-size:17px; } .fn b{ font-size:12px; line-height:1.25; }
  .forow{ grid-template-columns:1fr 46px 1fr; } .fo{ gap:6px; } .slot{ min-width:36px; padding:2px 4px; font-size:9px; }
  .tpgrid{ grid-template-columns:1fr; }
  table.lb .pf{ display:none; } .pbar{ min-width:36px; }
  table.lb td.two b{ font-size:12.5px; line-height:1.25; } .chip{ padding:2px 6px; letter-spacing:.4px; }
  .ktray{ grid-template-columns:repeat(3,1fr); } .kgrid{ grid-template-columns:1fr; }
  .kt .kh-img{ width:40px; height:40px; } .kt b{ font-size:12px; }
  td.barc{ width:22%; }
}

/* ---- Kreeper page components used by the ported standings/power pages ---- */
.glance-panel{ border-radius:16px; padding:1px; margin:10px 0 26px; border:1px solid var(--line);
  background:linear-gradient(135deg, rgba(212,177,94,.4), rgba(42,91,176,.28), rgba(106,166,240,.4)); }
.glance-panel-in{ background:var(--panel); border-radius:15px; padding:20px 24px; }
.liquid-stats{ display:flex; gap:36px; flex-wrap:wrap; }
.liquid-stat{ display:flex; align-items:center; gap:14px; }
.liquid-stat .txt .lbl{ font-size:10.5px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); }
.liquid-stat .txt .sub{ font-size:13px; color:var(--ink); margin-top:3px; max-width:180px; }

.faab-pot{ text-align:center; padding:18px 12px; border-radius:12px; border:1px solid transparent;
  background:var(--panel2); border:1px solid var(--line);
  margin-bottom:16px; }
.faab-pot b{ font-family:var(--font-display); font-weight:var(--display-wt); font-size:38px; background:var(--hl); -webkit-background-clip:text;
  background-clip:text; -webkit-text-fill-color:transparent; display:block; line-height:1; }
.faab-pot span{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:1px; }

/* FAAB burn-down chart */
.burn-wrap{ background:var(--panel2); border:1px solid var(--line); border-radius:12px;
  padding:14px 16px 10px; margin-bottom:16px; }
.burn-svg{ width:100%; height:auto; display:block; }
.burn-legend{ display:flex; flex-wrap:wrap; gap:12px; margin-top:10px; padding-top:10px;
  border-top:1px solid var(--line); }
.burn-key{ display:flex; align-items:center; gap:6px; font-size:11px; color:var(--muted);
  white-space:nowrap; }
.burn-key.on{ color:var(--ink); font-weight:600; }
.burn-key b{ font-family:var(--font-display); font-weight:var(--display-wt); color:var(--ink); }
.burn-dot{ width:9px; height:9px; border-radius:2px; flex:0 0 auto; }

/* standings — the playoff cut line sits UNDER the last qualifying row */
tr.playoff-cut td{ border-bottom:2px solid var(--accent) !important; }

/* weekly scoreboard cards */
.matchups{ display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:12px; }
.matchup{ background:var(--panel2); border:1px solid var(--line); border-radius:12px; padding:12px 14px; }
.mu-row{ display:flex; align-items:center; justify-content:space-between; gap:10px;
  padding:5px 0; font-size:13.5px; color:var(--muted); }
.mu-row.win{ color:var(--ink); font-weight:700; }
.mu-row.win .mu-pts{ color:var(--teal); }
.mu-team{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.mu-pts{ font-family:var(--font-display); font-weight:var(--display-wt); font-size:15px; flex:0 0 auto; }
.mu-note{ margin-top:6px; padding-top:6px; border-top:1px solid var(--line);
  font-size:9.5px; text-transform:uppercase; letter-spacing:1px; color:var(--muted); text-align:right; }

/* power ranking movement arrows */
.pr-up{ color:var(--teal); font-weight:700; }
.pr-down{ color:var(--red); font-weight:700; }
.pr-flat{ color:var(--muted); }

.payout-row{ display:flex; align-items:center; gap:14px; background:var(--panel2);
  border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.payout-row .po-amt{ font-family:var(--font-display); font-weight:var(--display-wt); font-size:26px; line-height:1; white-space:nowrap; }
.payout-row .po-lbl{ font-size:9.5px; text-transform:uppercase; letter-spacing:1.2px; color:var(--muted); }
.payout-row .po-who{ font-size:14px; font-weight:600; color:var(--ink); margin-top:2px; line-height:1.2; }
.payout-row .po-sub{ font-size:11px; color:var(--muted); margin-top:2px; line-height:1.3; }
.burnbar-track{ width:100%; height:8px; border-radius:5px; background:var(--bg); overflow:hidden; }
.burnbar-fill{ height:100%; border-radius:5px; }

/* ---- B&B specifics on top of the ported layout ---- */
/* B&B's ink is dark, so anything sitting on the purple masthead must say
   white explicitly (Kreeper's ink is white, so its chip inherited it). The
   doubled classes out-rank the theme's markdown-span colour reset. */
[data-testid="stMarkdownContainer"] .mh-right span.mechip.mechip,
[data-testid="stMarkdownContainer"] .mh-right .mh-meta.mh-meta{ color:#fff !important; }
.lockline b{ color:var(--purple) !important; }
/* the wordmark on the purple band: gold script, purple outline */
.masthead .neon-logo{ color:var(--gold) !important; -webkit-text-stroke:1.5px var(--purple-d);
  text-shadow:0 2px 10px rgba(0,0,0,.25); font-size:28px; }
.masthead .status-line{ margin:0; color:#fff; }
.masthead .status-line .muted{ color:rgba(255,255,255,.75); }
.masthead .status-line .dot{ background:var(--gold); }
/* section headers are plain titles, not B&B's filled purple h2 bar */
.sechead h2{ background:none !important; border:none !important; box-shadow:none !important;
  padding:0 !important; display:block !important; }
.sechead h2, .sechead h2 *{ color:var(--ink) !important; }
.sechead h2 .g{ -webkit-text-fill-color:var(--purple-l) !important; color:var(--purple-l) !important; }
/* the page's content column: 3rem gutters on desktop, 12px on phones (the
   phone rule must use this same selector or it loses on specificity) */
[data-testid="stAppViewContainer"] .block-container{ --block-pad:3rem;
  padding-left:var(--block-pad) !important; padding-right:var(--block-pad) !important; padding-top:2.6rem !important; }
.lb .num{ white-space:nowrap; } table.lb th{ white-space:nowrap; }
@media (max-width: 640px){
  [data-testid="stAppViewContainer"] .block-container{ --block-pad:12px;
    padding-left:var(--block-pad) !important; padding-right:var(--block-pad) !important; padding-top:2.5rem !important; }
  .masthead{ padding-top:10px; padding-bottom:10px; margin-bottom:16px; flex-wrap:nowrap; gap:10px; }
  .mh-home{ min-width:0; display:inline-flex; flex:0 0 auto; }
  .masthead .neon-logo{ font-size:21px !important; }
  .mh-meta{ font-size:9px; letter-spacing:1.2px; flex:0 0 auto; }
  .masthead .status-line{ font-size:10px; }
}

</style>
"""

def headshot(pid: str) -> str:
    return SLEEPER_IMG.format(pid=pid)


def img_tag(pid: str, cls: str = "hs") -> str:
    """Headshot <img>. Source is picked server-side because Streamlit's HTML
    sanitizer strips `onerror`, so an in-browser fallback chain can't run.

    ESPN's headshots cover both veterans and incoming rookies (where Sleeper's
    CDN often has no photo), so we use ESPN whenever we have an id for the
    player and fall back to the Sleeper thumb otherwise.
    """
    eid = _ESPN_BY_PID.get(str(pid))
    src = ESPN_IMG.format(eid=eid) if eid else headshot(pid)
    return f'<img class="{cls}" src="{src}" loading="lazy">'


def logo_html(size: int = 52, tag: str | None = "The Keeper Sportsource", text: str = "B&B") -> str:
    t = f'<div class="neon-tag">{tag}</div>' if tag else ""
    return (f'<div class="neon-logo" style="font-size:{size}px;">{text}</div>{t}')


def _wave_d(amp: float, phase: float, second: float = 0.45) -> str:
    """One seamless wave surface as an SVG path, in local coords where y=0 is
    the still surface and +y is down. Two sine components at 200 and 100
    units — both divide the 200-unit loop distance exactly, so translating
    the path by -200 lands it back on itself with no visible seam.
    (Identical generator to kreeper-league's — proven to tile cleanly.)"""
    pts = []
    x = -200.0
    while x <= 400.0:
        y = (amp * math.sin(2 * math.pi * x / 200.0 + phase)
             + amp * second * math.sin(2 * math.pi * x / 100.0 - phase * 1.7))
        pts.append("%.1f,%.2f" % (x, y))
        x += 8.0
    return "M " + " L ".join(pts) + " L 400,420 L -200,420 Z"


_WAVE_FRONT = _wave_d(6.5, 0.0)
_WAVE_BACK = _wave_d(4.8, 2.1, second=0.3)
_liq_uid_counter = 0


def liquid_ring_html(pct: float, value_html: str, label: str = "", size: int = 78,
                      accent: str = PURPLE) -> str:
    """A small animated liquid-wave-fill circle gauge, with an HTML value
    overlaid in the middle. `pct` in [0, 1]."""
    global _liq_uid_counter
    _liq_uid_counter += 1
    uid = f"liq{_liq_uid_counter}"
    p = max(0.06, min(0.94, pct))
    surface = 200.0 - 200.0 * p
    inner = size - 8
    k = inner / 200.0
    off = (size - inner) / 2
    cx = cy = size / 2
    return (
        f'<span class="liq-ring" style="width:{size}px;height:{size}px;">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" aria-hidden="true">'
        f'<circle cx="{cx}" cy="{cy}" r="{(size-3)/2:.1f}" fill="none" '
        f'stroke="#e3dcf2" stroke-width="1.5"/>'
        f'<defs><clipPath id="{uid}"><circle cx="{cx}" cy="{cy}" r="{inner/2:.1f}"/></clipPath></defs>'
        f'<g clip-path="url(#{uid})">'
        f'<g transform="translate({off:.1f},{off:.1f}) scale({k:.4f})">'
        f'<g class="liq-bob" style="--sy:{surface:.1f}px">'
        f'<path class="liq-wv back" d="{_WAVE_BACK}" fill="{accent}" opacity=".4"/>'
        f'<path class="liq-wv front" d="{_WAVE_FRONT}" fill="{accent}" opacity=".85"/>'
        f'</g></g></g></svg>'
        f'<span class="liq-val"><b>{value_html}</b>'
        + (f'<small>{label}</small>' if label else '') + '</span>'
        f'</span>'
    )


def liquid_stat_html(pct: float, value_html: str, ring_label: str, label: str, sub: str = "",
                      size: int = 78, accent: str = PURPLE) -> str:
    """A quick-glance stat: a liquid ring next to a label/sub text block."""
    ring = liquid_ring_html(pct, value_html, ring_label, size=size, accent=accent)
    return (f'<div class="gstat">{ring}'
            f'<div class="txt"><div class="lbl">{label}</div>'
            + (f'<div class="sub">{sub}</div>' if sub else '') + '</div></div>')


def inject(st) -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def section_head(title_html: str, caption: str = "", page: bool = False) -> str:
    """Title + hairline rule + right-aligned micro-caption (Kreeper's section
    header). `title_html` may carry a `<span class="g">` for the emphasised
    word. `caption` is terse metadata, NOT prose — it's nowrap. `page=True`
    for the title at the top of a page."""
    cap = f'<span class="cap">{caption}</span>' if caption else ""
    cls = "sechead page" if page else "sechead"
    return (f'<div class="{cls}"><h2>{title_html}</h2>'
            f'<span class="rule"></span>{cap}</div>')
