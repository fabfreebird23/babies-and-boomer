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

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Anton&family=Oswald:wght@400;500;600;700&family=Pacifico&display=swap');

:root{
  --bg:#f4f0e6; --panel:#ffffff; --panel2:#f3eef9;
  --purple:#4b2d9f; --purple-d:#2a1a5e; --purple-l:#7a5bd8;
  --gold:#ffce1f; --gold-d:#c99700; --cyan:#2390c0; --red:#d6336c;
  --ink:#241a40; --muted:#6f6593; --line:#e3dcf2;
}

/* light cream/lavender magazine field */
.stApp{
  background-color:#f4f0e6;
  background-image:
    radial-gradient(60% 45% at 14% 4%, rgba(123,91,216,.14), transparent 46%),
    radial-gradient(54% 40% at 100% 96%, rgba(255,206,31,.18), transparent 50%),
    repeating-radial-gradient(circle at 0 0, rgba(75,45,159,.05) 0 1px, transparent 1px 5px),
    linear-gradient(170deg,#faf6ec 0%, #efe9f7 70%);
  background-attachment:fixed;
}
html, body, [class*="css"]{ font-family:'Oswald', sans-serif; color:var(--ink); }

[data-testid="stHeader"]{ background:transparent; }
[data-testid="stSidebar"]{ background:rgba(255,255,255,.85); border-right:3px solid var(--gold); }

/* headings — heavy condensed caps. h2 = magazine "panel" bar. */
h1,h2,h3{ font-family:'Anton', sans-serif !important; letter-spacing:2px; text-transform:uppercase; }
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
.neon-tag{ font-family:'Oswald'; letter-spacing:6px; font-weight:700; font-size:11px;
  color:var(--purple); text-transform:uppercase; margin-top:8px; }
/* let the sidebar mark spell the league name out across two lines */
[data-testid="stSidebar"] .neon-logo{ white-space:normal; line-height:.92; -webkit-text-stroke-width:2px; }

/* sidebar nav radio (unused now) -> light label tags */
[data-testid="stSidebar"] [role="radiogroup"] label{ border:1.5px solid var(--purple); border-radius:0;
  padding:6px 11px; margin-bottom:7px; background:#fff; transition:.12s; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover{ border-color:var(--gold-d); }
[data-testid="stSidebar"] [role="radiogroup"] label p{ font-weight:700; text-transform:uppercase;
  letter-spacing:2px; font-size:13px; color:var(--purple); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){ background:var(--gold); border-color:var(--gold); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{ color:var(--purple-d); }
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child{ display:none; }

.stButton>button{ font-family:'Anton'; letter-spacing:2px; text-transform:uppercase;
  background:var(--gold); color:var(--purple-d); border:none; border-radius:0; }
.stButton>button:hover{ background:var(--purple); color:#fff; box-shadow:0 0 0 2px var(--gold); }

/* ---- shared custom tables ---- */
/* No boxed card around tables — the gold header row + striped rows carry
   the structure, so the table sits directly on the page like everything else. */
.neonwrap{ overflow:auto; max-height:72vh; }
/* Plain rows on a bottom border, no card/box around the table — the gold
   underline on th and the row dividers are the only structure, so it reads
   as a list that sits on the page rather than a boxed data-grid. */
table.lb{ width:100%; border-collapse:collapse; font-family:'Oswald'; font-size:14px; }
table.lb th{ color:var(--muted); text-transform:uppercase; letter-spacing:1px;
  font-family:'Anton'; font-weight:400; font-size:11px; text-align:left; padding:8px 10px;
  border-bottom:2px solid var(--gold); position:sticky; top:0; z-index:5; background:var(--bg); }
table.lb th.r{ text-align:right; }
table.lb td{ padding:7px 10px; border-bottom:1px solid var(--line); color:var(--ink); }
table.lb tr:hover td{ background:rgba(75,45,159,.04); }
table.lb tr.kept td{ background:linear-gradient(90deg, rgba(255,206,31,.30), rgba(255,206,31,.06)); }
table.lb tr.kept td:first-child{ box-shadow:inset 4px 0 0 var(--gold-d); }
.lb .rk{ font-family:'Anton'; color:var(--gold-d); width:34px; text-align:center; }
.lb .pl{ font-weight:600; color:var(--ink); }
.lb .pos{ color:var(--muted); font-size:11px; font-weight:600; white-space:nowrap; }
.lb .val{ font-family:'Anton'; color:#1c9b63; text-align:right; letter-spacing:1px; }
.lb .num{ text-align:right; color:var(--ink); }
.lb .kept-badge{ color:var(--purple-d); background:var(--gold); font-weight:700; font-size:10px;
  font-family:'Anton'; padding:1px 6px; text-transform:uppercase; letter-spacing:1px; }
.lb .rk-badge{ color:var(--purple-d); background:var(--gold); font-weight:700; font-size:10px;
  font-family:'Anton'; padding:1px 6px; text-transform:uppercase; letter-spacing:1px; margin-left:4px; }
.lb .fa-tag{ color:var(--cyan); font-weight:600; font-size:12px; font-style:italic; }
table.lb tr.fa td{ background:rgba(35,144,192,.08); }
table.lb tr.rd-sep td{ background:var(--purple-d); color:var(--gold); font-family:'Anton';
  letter-spacing:2px; text-transform:uppercase; font-size:12px; padding:5px 12px;
  position:sticky; top:38px; z-index:4; }

/* purple-duotone, gold-framed headshots (full colour on hover) */
.hs{ width:32px; height:32px; border-radius:4px; object-fit:cover; vertical-align:middle;
  background:#ece5fb; border:2px solid var(--gold-d); margin-right:9px;
  filter:grayscale(1) contrast(1.05) sepia(.55) hue-rotate(205deg) saturate(1.9) brightness(1.02);
  transition:filter .15s; }
.hs:hover{ filter:none; }
.posdot{ display:inline-block; width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;}
.p-QB{background:var(--gold-d);} .p-RB{background:var(--purple-l);} .p-WR{background:var(--cyan);} .p-TE{background:var(--red);}

/* stat cards (Superlatives, lottery draw order) — thin border + left accent
   rail, no drop shadow or gold top-bar, echoing the Draft Capital rows and
   contract cards rather than a heavier boxed style of its own. */
.kcards{ display:grid; grid-template-columns:repeat(4,1fr); gap:10px; }
.kcard{ border:1px solid var(--line); border-radius:10px; background:#fff;
  padding:12px 14px; position:relative; overflow:hidden; box-shadow:0 2px 6px rgba(75,45,159,.05); }
.kcard::before{ content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--gold-d); }
.kcard h4{ font-family:'Anton'; font-weight:400; font-size:10.5px; letter-spacing:.6px;
  text-transform:uppercase; color:var(--muted); margin:0 0 4px; }
.kcard .who{ font-family:'Anton'; font-weight:400; font-size:16px; color:var(--purple-d); }
.kcard .sub{ font-size:11.5px; color:var(--muted); margin-top:3px; }

/* lottery draw-order reveal — a single-line row list, same idea as the
   Draft Capital rows, instead of a grid of boxed cards. */
.draw-list{ display:flex; flex-direction:column; gap:6px; }
.draw-row{ display:flex; align-items:center; gap:12px; border:1px solid var(--line);
  border-radius:10px; background:#fff; padding:10px 14px; box-shadow:0 2px 6px rgba(75,45,159,.05); }
.draw-row .pickno{ font-family:'Anton'; font-weight:400; font-size:18px; color:var(--gold-d);
  width:28px; text-align:center; flex:none; }
.draw-row .who{ font-family:'Anton'; font-weight:400; font-size:15px; color:var(--purple-d); }
.draw-row .sub{ font-size:11.5px; color:var(--muted); }

/* draft board */
table.dboard{ width:100%; border-collapse:collapse; table-layout:fixed; font-family:'Oswald'; font-size:12px; }
table.dboard th{ background:var(--gold); color:var(--purple-d); text-align:center; font-family:'Anton'; font-weight:400;
  font-size:11px; padding:5px; border:1px solid #fff; text-transform:uppercase; letter-spacing:1px; }
.dbcell{ border:1px solid var(--line); padding:3px 4px; vertical-align:top; height:48px; }
table.dboard td.dbcell{ padding:3px 4px; }
.dbpick{ color:var(--muted); font-size:9px; white-space:nowrap; }
.db-base{ background:#faf7ff; color:#8a7fb3; }
.db-traded{ background:rgba(255,206,31,.28); color:var(--gold-d); }
.db-keep{ background:rgba(28,155,99,.14); color:#15824f; box-shadow:inset 0 0 0 1px rgba(28,155,99,.4); }
.db-conflict{ background:rgba(214,51,108,.14); color:#b3235a; box-shadow:inset 0 0 0 1px rgba(214,51,108,.4); }
.db-rd{ background:var(--purple); color:var(--gold); font-family:'Anton'; text-align:center; white-space:nowrap; }

/* top bar — centered script-logo masthead band, on every page. The phase
   chip tucks into the corner; a gold rule closes the band off, echoing the
   Home masthead's own gold underline. */
.kbar{ position:relative; display:flex; flex-direction:column; align-items:center;
  gap:2px; text-align:center; padding:16px 20px 13px; margin-bottom:8px;
  border-bottom:3px solid var(--gold); }
.khome{ text-decoration:none !important; line-height:1; }
.khome .neon-logo{ font-size:30px; -webkit-text-stroke-width:2px; }
.khome .neon-tag{ margin-top:4px; }

/* compact liquid-wave phase indicator, tucked top-right, persistent on every page */
.topbar-chip{ position:absolute; top:12px; right:20px; background:var(--panel2);
  border:1px solid var(--line); border-radius:999px; padding:6px 16px 6px 6px; }
.topbar-chip .liquid-stat, .topbar-chip .gstat{ gap:10px; }
.topbar-chip .liq-ring{ margin-bottom:0; }
.topbar-chip .gstat .txt .lbl{ font-size:11.5px; font-weight:600; letter-spacing:.4px; color:var(--purple-d); }
.topbar-chip .gstat .txt .sub{ font-size:9.5px; color:var(--muted); margin-top:1px; max-width:none; }

/* Home's thin status line — same phase info as the top-bar chip, echoed
   at the top of the content instead of tucked in the corner. */
.status-line{ background:var(--panel2); border-bottom:1px solid var(--line); margin:0 0 18px;
  padding:9px 20px; display:flex; align-items:center; justify-content:center; gap:8px;
  font-family:'Oswald'; font-weight:700; font-size:12.5px; color:var(--purple-d);
  text-transform:uppercase; letter-spacing:.4px; }
.status-line .dot{ width:6px; height:6px; border-radius:50%; background:var(--gold-d); flex:none; }
.status-line .muted{ color:var(--muted); font-weight:500; text-transform:none; letter-spacing:0; }

@media (max-width: 640px){
  /* the phase chip drops out entirely on mobile — Home already echoes the
     same phase info in its status-line, and a fixed top-right pin doesn't
     leave enough room next to a centered 30px script logo besides. */
  .topbar-chip{ display:none; }
}

/* fixed bottom pill nav — replaces the old static top bar. Leave room at
   the foot of the page so content never sits under it. */
[data-testid="stAppViewContainer"] .block-container{ padding-bottom:92px !important; }
.bottom-bar-wrap{ position:fixed; left:0; right:0; bottom:16px; display:flex;
  justify-content:center; z-index:1000; pointer-events:none; }
.bottom-bar{ pointer-events:auto; display:flex; align-items:center; gap:2px;
  background:rgba(255,255,255,.97); backdrop-filter:blur(10px);
  border:2px solid var(--purple); border-radius:999px; padding:5px 8px;
  box-shadow:0 12px 30px rgba(75,45,159,.28); }
.navlink{ font-family:'Anton'; text-transform:uppercase; letter-spacing:.6px; font-size:12px;
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
.bb-pop-panel{ display:none; }
.bb-pop-panel.on{ display:block; }
.bb-pop-head{ display:flex; align-items:center; gap:8px; padding:8px 10px 10px; }
.bb-pop-back{ font-family:'Oswald'; font-weight:600; font-size:11px; color:var(--muted); cursor:pointer;
  touch-action:manipulation; -webkit-tap-highlight-color:transparent; }
.bb-pop-back:hover{ color:var(--purple); }
.bb-pop-title{ font-family:'Anton', sans-serif; font-size:12px; text-transform:uppercase;
  letter-spacing:.5px; color:var(--purple); }
.bb-pop-item{ display:flex; align-items:center; justify-content:space-between; padding:12px 12px;
  border-radius:10px; font-family:'Oswald'; font-size:13.5px; font-weight:600; color:var(--ink) !important;
  text-decoration:none !important; cursor:pointer; transition:background .15s;
  touch-action:manipulation; -webkit-tap-highlight-color:transparent; }
.bb-pop-item:hover{ background:var(--panel2); }
.bb-pop-item .chev{ color:var(--muted); font-size:11px; }
.bb-pop-item.leaf-active{ background:rgba(255,206,31,.22); }
.bb-pop-item.leaf-active .lbl{ color:var(--purple-d); }

/* sub-tabs (st.tabs) -> gold accent */
[data-baseweb="tab-list"]{ border-bottom:2px solid var(--line) !important; }
button[data-baseweb="tab"] [data-testid="stMarkdownContainer"] p{ font-family:'Anton'; letter-spacing:1px; text-transform:uppercase; font-size:14px; }
[data-baseweb="tab-highlight"]{ background:var(--gold-d) !important; }
button[data-baseweb="tab"][aria-selected="true"]{ color:var(--gold-d) !important; }

/* ---------------- mobile ---------------- */
/* per-team collapsible contract-card sections — plain HTML <details>/<summary>
   instead of st.expander, so each one can carry its own accent color. */
details.team-details{ border:1px solid var(--line); border-left:4px solid var(--purple);
  background:#fff; margin-bottom:10px; overflow:hidden; box-shadow:0 4px 12px rgba(75,45,159,.06); }
details.team-details summary{ list-style:none; cursor:pointer; padding:13px 16px;
  font-family:'Anton', sans-serif; letter-spacing:.3px; font-size:15px; color:var(--purple-d);
  transition:background .12s; }
details.team-details summary::-webkit-details-marker{ display:none; }
details.team-details summary:hover{ background:rgba(255,206,31,.10); }
details.team-details .team-details-body{ padding:6px 16px 16px; }
details.team-details .empty-note{ color:var(--muted); font-size:13px; padding:0 0 4px; margin:0; }

/* two-tone heading accent — wrap the one word that matters in <span class="g"> */
.g{ background:linear-gradient(90deg, var(--purple), var(--purple-l) 55%, var(--gold-d));
  -webkit-background-clip:text; background-clip:text; -webkit-text-fill-color:transparent; }
/* a bare h2 stays the filled purple/gold panel bar; opt any heading into the
   two-tone look (no filled bar, no white text) with this class instead */
h2.two-tone{ background:none !important; border:none !important; box-shadow:none !important;
  padding:0 !important; display:block !important; color:var(--purple) !important;
  font-size:1.55rem !important; margin-bottom:4px !important; }
h2.two-tone, h2.two-tone *{ color:var(--purple) !important; }
h2.two-tone .g{ -webkit-text-fill-color:transparent !important; }

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
.liq-val b{ font-family:'Anton'; font-weight:400; color:var(--purple-d); }
.liq-val small{ font-size:8px; color:var(--muted); text-transform:uppercase; letter-spacing:.4px; }
.gstat .txt .lbl{ font-family:'Anton'; font-size:11px; letter-spacing:.8px; text-transform:uppercase; color:var(--purple); }
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
.chip{ display:inline-block; font-family:'Anton'; font-size:10px; letter-spacing:.6px;
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
.dc-rank{ font-family:'Anton'; font-size:17px; color:var(--gold-d); text-align:center; }
.dc-main b{ display:block; font-family:'Oswald'; font-weight:700; font-size:15px; color:var(--ink); }
.dc-meta{ display:flex; gap:6px; flex-wrap:wrap; margin-top:7px; }
.dc-stat{ text-align:right; min-width:110px; }
.dc-stat b{ display:block; font-family:'Anton'; font-weight:400; font-size:19px; line-height:1; }
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
.kr-section-head h3{ font-family:'Anton', sans-serif !important; font-size:20px !important;
  font-weight:400 !important; letter-spacing:.3px; margin:0 !important; color:var(--purple-d) !important; }
.kr-section-head .tag{ font-family:'Oswald'; font-weight:600; font-size:10.5px; letter-spacing:.6px;
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
.ccard h4{ font-family:'Anton'; font-weight:400; font-size:17px; color:var(--purple-d); margin:0; letter-spacing:.2px; line-height:1.15; }
.ccard .pos{ font-size:11px; color:var(--muted); margin-top:1px; }
.ccard .cost{ text-align:right; }
.ccard .cost b{ font-family:'Anton'; font-size:17px; color:var(--gold-d); display:block; line-height:1; font-weight:400; }
.ccard .cost small{ font-size:9px; color:var(--muted); text-transform:uppercase; letter-spacing:.5px; }
.ccard .pips{ display:flex; gap:4px; margin:8px 0 7px; }
.ccard .pip{ width:15px; height:6px; background:var(--line); }
.ccard .pip.on{ background:var(--purple); }
.ccard .badges{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:4px; }
.ccard .badge{ font-family:'Oswald'; font-weight:600; font-size:9.5px; letter-spacing:.3px; text-transform:uppercase;
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
  margin:0 6px 6px 0; text-transform:none; font-family:'Oswald'; font-weight:500; letter-spacing:0; }
.trade-date{ font-size:10.5px; color:var(--muted); margin-top:10px; text-transform:uppercase; letter-spacing:.5px; }

/* ---------------- lottery bars ---------------- */
.lot-wrap{ padding:12px 0 18px; border-top:1px solid var(--line); margin-bottom:8px; }
.lot-head{ display:flex; align-items:baseline; justify-content:space-between; gap:14px; margin-bottom:14px; }
.lot-head h4{ font-family:'Anton'; font-weight:400; font-size:16px; color:var(--purple-d); margin:0; letter-spacing:.3px; }
.lot-eyebrow{ font-family:'Oswald'; font-weight:600; font-size:10.5px; letter-spacing:.5px; text-transform:uppercase; color:var(--muted); }
.lot-row{ display:flex; align-items:center; gap:14px; padding:8px 0; }
.lot-label{ width:170px; flex:0 0 auto; }
.lot-label b{ display:block; font-size:13.5px; font-weight:600; color:var(--ink); }
.lot-label small{ display:block; font-size:10px; color:var(--muted); margin-top:1px; }
.lot-track{ flex:1; height:20px; background:var(--panel2); border-radius:2px; position:relative; overflow:hidden; }
.lot-fill{ height:100%; background:linear-gradient(90deg, var(--purple), var(--purple-l) 55%, var(--gold-d));
  display:flex; align-items:center; justify-content:flex-end; padding-right:8px; font-size:10.5px;
  color:#fff; font-weight:600; font-variant-numeric:tabular-nums; min-width:2px; }
.lot-pos{ width:26px; text-align:right; font-family:'Anton'; color:var(--gold-d); font-size:13px; }

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
  .bottom-bar-wrap{ bottom:10px; }
  .bottom-bar{ gap:0; padding:4px; }
  .navlink{ font-size:10px; padding:8px 11px !important; letter-spacing:.3px; }
  .bb-pop{ bottom:68px; }
  h1{ font-size:1.5rem !important; }
  h2{ font-size:1.25rem !important; }
  h3{ font-size:1.15rem !important; }
  .block-container{ padding-left:.6rem !important; padding-right:.6rem !important; padding-top:2.5rem !important; }
  .neonwrap{ max-height:none !important; }

  .khome .neon-logo{ font-size:24px; }

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
