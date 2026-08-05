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

/* ---- magazine masthead + hero band (Home) ---- */
.eb-mast{ display:flex; align-items:flex-start; justify-content:space-between; gap:18px;
  border-bottom:3px solid var(--gold); padding-bottom:12px; margin-bottom:4px; }
.eb-issue{ text-align:right; font-weight:700; white-space:nowrap; padding-top:6px; }
.eb-issue .vol{ font-family:'Anton'; font-size:15px; color:var(--gold-d); letter-spacing:3px; }
.eb-issue .sub{ font-size:11px; letter-spacing:3px; color:var(--purple-l); text-transform:uppercase; margin-top:3px; }
.eb-issue .px{ display:inline-block; margin-top:8px; background:var(--gold); color:var(--purple-d);
  font-family:'Anton'; font-size:12px; letter-spacing:2px; padding:3px 9px; transform:skewX(-8deg); }

.eb-hero{ position:relative; margin:14px 0 22px; border:1px solid var(--line);
  background:linear-gradient(120deg,#efe8fb,#fbf7ee 75%); overflow:hidden; box-shadow:0 8px 26px rgba(75,45,159,.10); }
.eb-hwrap{ display:grid; grid-template-columns:1.2fr 1fr; }
.eb-left{ padding:26px 26px 30px; }
.eb-left .kicker{ font-weight:700; letter-spacing:6px; font-size:12px; color:var(--gold-d); text-transform:uppercase; }
.eb-headline{ font-family:'Anton'; text-transform:uppercase; line-height:.9; margin:8px 0 2px; }
.eb-headline .l1{ font-size:54px; letter-spacing:2px; color:var(--purple); }
.eb-headline .l2{ font-size:54px; letter-spacing:13px; color:var(--gold-d); text-shadow:3px 3px 0 rgba(123,91,216,.25); }
.eb-deck{ margin-top:12px; max-width:380px; color:#4a4070; font-size:14px; line-height:1.45; font-weight:500; }
.eb-deck b{ color:var(--gold-d); }
.eb-cuts{ position:relative; min-height:230px;
  background:repeating-linear-gradient(180deg, rgba(75,45,159,.08) 0 2px, transparent 2px 6px); }
.cut{ position:absolute; border:2px solid var(--gold-d); overflow:hidden; box-shadow:0 0 0 3px #fff, 0 6px 14px rgba(75,45,159,.18); }
.cut svg{ display:block; width:100%; height:100%; }
.cut.a{ width:128px; height:108px; top:44px; right:30px; }
.cut.b{ width:108px; height:134px; top:96px; right:140px; }
.cut.c{ width:136px; height:108px; bottom:18px; right:34px; }
.lab{ position:absolute; display:inline-flex; font-family:'Oswald'; font-weight:700;
  font-size:11px; letter-spacing:2px; text-transform:uppercase; z-index:3; }
.lab span{ padding:3px 8px; }
.lab .w{ background:#fff; color:var(--purple-d); border:1px solid var(--purple-d); }
.lab .k{ background:var(--purple-d); color:#fff; }
.lab.t1{ top:8px; right:26px; }
.lab.t2{ top:78px; right:140px; }
.lab.t3{ bottom:0; right:40px; }
a.lab{ text-decoration:none; cursor:pointer; }
a.lab:hover .w{ background:var(--gold); }
a.lab:hover .k{ background:var(--purple); color:#fff; }

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
.neonwrap{ overflow:auto; max-height:72vh; border:2px solid var(--gold); border-radius:0;
  background:#fff; box-shadow:0 10px 28px rgba(75,45,159,.12); }
table.lb{ width:100%; border-collapse:collapse; font-family:'Oswald'; font-size:14px; }
table.lb th{ background:var(--gold); color:var(--purple-d); text-transform:uppercase; letter-spacing:1px;
  font-family:'Anton'; font-weight:400; font-size:12px; text-align:left; padding:8px 10px;
  position:sticky; top:0; z-index:5; box-shadow:0 2px 0 var(--gold); }
table.lb th.r{ text-align:right; }
table.lb td{ padding:6px 10px; border-bottom:1px solid var(--line); color:var(--ink); }
table.lb tr:nth-child(odd) td{ background:rgba(123,91,216,.05); }
table.lb tr:hover td{ background:rgba(255,206,31,.16); }
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

/* team cards — white panels, gold top rule */
.kcards{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
.kcard{ border:1px solid var(--line); border-top:3px solid var(--gold); border-radius:0;
  background:#fff; padding:10px 12px; min-height:96px; box-shadow:0 6px 18px rgba(75,45,159,.10); }
.kcard h4{ font-family:'Anton'; font-size:15px; margin:0 0 6px; color:var(--purple); letter-spacing:1px; text-transform:uppercase; }
.kcard .kp{ display:flex; align-items:center; font-size:13px; padding:2px 0; color:var(--ink); }
.kcard .kp img{ width:24px;height:24px;border-radius:4px;margin-right:7px;object-fit:cover;background:#ece5fb;
  border:1.5px solid var(--gold-d);
  filter:grayscale(1) sepia(.55) hue-rotate(205deg) saturate(1.9) brightness(1.02); }
.kcard .kp .rd{ margin-left:auto; color:var(--gold-d); font-weight:700; font-family:'Anton'; }
.kcard .empty{ color:var(--muted); font-style:italic; font-size:12px; }
.kcard .rk-tag{ color:var(--purple-d); background:var(--gold); font-size:9px; font-weight:700;
  font-family:'Anton'; padding:0 4px; margin-left:5px; letter-spacing:1px; }

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

/* section header — duotone football (a colourway per section) */
.sneak{ display:inline-block; vertical-align:middle; height:42px; margin:0 14px 6px 0;
  filter:drop-shadow(2px 3px 0 rgba(123,91,216,.35)); }

/* fixed bottom pill nav — replaces the old static top bar. Leave room at
   the foot of the page so content never sits under it. */
[data-testid="stAppViewContainer"] .block-container{ padding-bottom:92px !important; }
.bottom-bar-wrap{ position:fixed; left:0; right:0; bottom:16px; display:flex;
  justify-content:center; z-index:1000; pointer-events:none; }
.bottom-bar{ pointer-events:auto; display:flex; align-items:center; gap:2px;
  background:rgba(255,255,255,.97); backdrop-filter:blur(10px);
  border:2px solid var(--purple); border-radius:999px; padding:5px 5px 5px 8px;
  box-shadow:0 12px 30px rgba(75,45,159,.28); }
.bb-logo{ display:inline-flex; align-items:center; margin-right:2px; text-decoration:none !important; }
.bb-logo .neon-logo{ font-size:20px; -webkit-text-stroke-width:1.5px; }
.navlink{ font-family:'Anton'; text-transform:uppercase; letter-spacing:.6px; font-size:12px;
  color:var(--purple) !important; text-decoration:none !important; padding:9px 16px !important;
  border-radius:999px !important; border:none !important; background:none; transition:opacity .2s, background .2s;
  white-space:nowrap; opacity:.72; }
.navlink:hover{ opacity:1; }
.navlink.active{ opacity:1; background:var(--gold); color:var(--purple-d) !important; }

/* sub-tabs (st.tabs) -> gold accent */
[data-baseweb="tab-list"]{ border-bottom:2px solid var(--line) !important; }
button[data-baseweb="tab"] [data-testid="stMarkdownContainer"] p{ font-family:'Anton'; letter-spacing:1px; text-transform:uppercase; font-size:14px; }
[data-baseweb="tab-highlight"]{ background:var(--gold-d) !important; }
button[data-baseweb="tab"][aria-selected="true"]{ color:var(--gold-d) !important; }

/* ---------------- mobile ---------------- */
@media (max-width: 640px){
  .neon-logo{ font-size:40px !important; -webkit-text-stroke-width:2px; }
  .neon-tag{ font-size:8px; letter-spacing:4px; }
  [data-testid="stAppViewContainer"] .block-container{ padding-bottom:84px !important; }
  .bottom-bar-wrap{ bottom:10px; }
  .bottom-bar{ gap:0; padding:4px; }
  .bb-logo{ display:none; }
  .navlink{ font-size:10px; padding:8px 11px !important; letter-spacing:.3px; }
  h1{ font-size:1.5rem !important; }
  h2{ font-size:1.25rem !important; }
  h3{ font-size:1.15rem !important; }
  .sneak{ height:28px; margin:0 8px 2px 0; }
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
  .kcard{ min-height:auto; padding:8px 9px; }
  .kcard h4{ font-size:13px; }
  .kcard .kp{ font-size:12px; }

  table.dboard{ font-size:9px; }
  table.dboard th{ padding:3px 2px; font-size:8px; }
  .dbcell{ height:auto; }
  table.dboard td.dbcell{ padding:2px 3px; }
  .db-rd{ font-size:10px; }

  .glance-stats{ gap:20px !important; }
  .stepper .sub{ display:none; }
  .cap-wrap{ overflow-x:auto; }
  .contract-grid{ grid-template-columns:1fr !important; }
  .lot-label{ width:100px !important; }
  .lot-label small{ display:none; }
}

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

/* ---------------- season-phase stepper ---------------- */
.stepper{ display:flex; align-items:flex-start; }
.step{ flex:1; position:relative; text-align:center; }
.step .dot{ width:30px; height:30px; border-radius:50%; margin:0 auto 8px; display:flex;
  align-items:center; justify-content:center; font-family:'Anton', sans-serif; font-size:12px;
  background:var(--panel2); border:2px solid var(--line); color:var(--muted); position:relative; z-index:2; }
.step .line{ position:absolute; top:15px; left:-50%; width:100%; height:2px; background:var(--line); z-index:1; }
.step:first-child .line{ display:none; }
.step .lbl{ font-family:'Anton', sans-serif; font-size:11px; letter-spacing:.6px; text-transform:uppercase; color:var(--muted); }
.step .sub{ font-size:9.5px; color:var(--muted); opacity:.75; margin-top:2px; }
.step.done .dot{ background:#1c9b63; border-color:#1c9b63; color:#fff; }
.step.done .dot::after{ content:"\2713"; }
.step.done .line{ background:#1c9b63; }
.step.now .dot{ background:var(--gold); border-color:var(--gold-d); color:var(--purple-d);
  box-shadow:0 0 0 4px rgba(255,206,31,.35); animation:step-pulse 2.2s ease-in-out infinite; }
.step.now .lbl{ color:var(--purple); }
@keyframes step-pulse{ 0%,100%{ box-shadow:0 0 0 4px rgba(255,206,31,.35);} 50%{ box-shadow:0 0 0 9px rgba(255,206,31,.08);} }
@media (prefers-reduced-motion: reduce){ .step.now .dot{ animation:none !important; } }

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

/* ---------------- de-blocked capital table + lean chips ---------------- */
.cap-wrap{ background:#fff; border:2px solid var(--gold); padding:6px 16px; box-shadow:0 8px 26px rgba(75,45,159,.10); }
table.cap{ width:100%; border-collapse:collapse; font-family:'Oswald'; font-size:14px; }
table.cap th{ text-align:left; font-family:'Anton'; font-weight:400; font-size:11.5px;
  text-transform:uppercase; letter-spacing:1px; color:var(--muted); padding:0 10px 10px; border-bottom:2px solid var(--gold); }
table.cap th.num{ text-align:right; }
table.cap td{ padding:11px 10px; border-bottom:1px solid var(--line); color:var(--ink); }
table.cap td.num{ text-align:right; font-variant-numeric:tabular-nums; }
table.cap tr:hover td{ background:rgba(255,206,31,.10); }
table.cap .rk{ font-family:'Anton'; color:var(--gold-d); width:26px; }
table.cap .team{ font-weight:600; }
.val-pos{ color:#1c9b63; font-weight:600; }
.val-neg{ color:var(--red); font-weight:600; }
.chip{ display:inline-block; font-family:'Anton'; font-size:10px; letter-spacing:.6px;
  text-transform:uppercase; padding:3px 9px; }
.chip.win-now{ background:rgba(28,155,99,.14); color:#1c9b63; border:1px solid rgba(28,155,99,.4); }
.chip.rebuild{ background:rgba(214,51,108,.12); color:var(--red); border:1px solid rgba(214,51,108,.4); }
.chip.balanced{ background:rgba(75,45,159,.08); color:var(--purple); border:1px solid rgba(75,45,159,.3); }

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
.trades-wrap{ background:#fff; border:2px solid var(--gold); padding:18px 24px; box-shadow:0 8px 26px rgba(75,45,159,.10); }
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
.lot-wrap{ background:#fff; border:2px solid var(--gold); padding:18px 24px; box-shadow:0 8px 26px rgba(75,45,159,.10); }
.lot-row{ display:flex; align-items:center; gap:14px; padding:8px 0; }
.lot-label{ width:170px; flex:0 0 auto; }
.lot-label b{ display:block; font-size:13.5px; font-weight:600; color:var(--ink); }
.lot-label small{ display:block; font-size:10px; color:var(--muted); margin-top:1px; }
.lot-track{ flex:1; height:20px; background:var(--panel2); border-radius:2px; position:relative; overflow:hidden; }
.lot-fill{ height:100%; background:linear-gradient(90deg, var(--purple), var(--purple-l) 55%, var(--gold-d));
  display:flex; align-items:center; justify-content:flex-end; padding-right:8px; font-size:10.5px;
  color:#fff; font-weight:600; font-variant-numeric:tabular-nums; min-width:2px; }
.lot-pos{ width:26px; text-align:right; font-family:'Anton'; color:var(--gold-d); font-size:13px; }
</style>
"""

# A football "colourway" per section (echoes the old per-section icon idea).
_SECTION_FILL = {
    "top": "#ffce1f", "board": "#7a5bd8", "draft": "#ffce1f",
    "adp": "#7a5bd8", "keepers": "#ffce1f", "rookies": "#7a5bd8",
}


def crt(key: str = "top") -> str:
    """Section-header icon: a duotone football, gold or purple per section."""
    fill = _SECTION_FILL.get(key, "#ffce1f")
    seam = "#0a0712" if fill == "#ffce1f" else "#1c1140"
    return (
        f'<svg class="sneak" viewBox="0 0 72 44" xmlns="http://www.w3.org/2000/svg">'
        f'<g transform="translate(36 22) rotate(-18)">'
        f'<ellipse rx="33" ry="17" fill="{fill}"/>'
        f'<ellipse rx="33" ry="17" fill="none" stroke="{seam}" stroke-width="2.5"/>'
        f'<line x1="-13" y1="0" x2="13" y2="0" stroke="{seam}" stroke-width="2.5"/>'
        f'<line x1="-9" y1="-4" x2="-9" y2="4" stroke="{seam}" stroke-width="2"/>'
        f'<line x1="-1" y1="-5" x2="-1" y2="5" stroke="{seam}" stroke-width="2"/>'
        f'<line x1="7" y1="-5" x2="7" y2="5" stroke="{seam}" stroke-width="2"/>'
        f'</g></svg>'
    )


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


def _football(w: int, h: int, fill: str, bg: str) -> str:
    seam = "#0a0712" if fill == GOLD else "#1c1140"
    rot = -30 if w >= h else 58
    return (
        f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">'
        f'<rect width="{w}" height="{h}" fill="{bg}"/>'
        f'<g transform="translate({w//2} {h//2}) rotate({rot})">'
        f'<ellipse rx="{int(w*0.42)}" ry="{int(h*0.26)}" fill="{fill}"/>'
        f'<ellipse rx="{int(w*0.42)}" ry="{int(h*0.26)}" fill="none" stroke="{seam}" stroke-width="3"/>'
        f'<line x1="-16" y1="0" x2="16" y2="0" stroke="{seam}" stroke-width="3"/>'
        f'<line x1="-11" y1="-5" x2="-11" y2="5" stroke="{seam}" stroke-width="2.4"/>'
        f'<line x1="-2" y1="-6" x2="-2" y2="6" stroke="{seam}" stroke-width="2.4"/>'
        f'<line x1="7" y1="-6" x2="7" y2="6" stroke="{seam}" stroke-width="2.4"/>'
        f'</g></svg>'
    )


def masthead(name: str, tagline: str, vol: str, sub: str, px: str) -> str:
    """Magazine masthead: brush-script league name + tagline, right issue block."""
    return (
        '<div class="eb-mast">'
        f'<div>{logo_html(58, tagline, name)}</div>'
        f'<div class="eb-issue"><div class="vol">{vol}</div>'
        f'<div class="sub">{sub}</div><div class="px">{px}</div></div>'
        '</div>'
    )


def hero(kicker: str, line1: str, line2: str, deck_html: str) -> str:
    """Cover-style hero band: big headline + football cut-outs. (The section
    label tags were removed — the top nav already links to those pages.)"""
    cuts = (
        f'<div class="cut a">{_football(128, 108, GOLD, "#ece5fb")}</div>'
        f'<div class="cut b">{_football(108, 134, PURPLE, GOLD)}</div>'
        f'<div class="cut c">{_football(136, 108, GOLD, "#ece5fb")}</div>'
    )
    return (
        '<div class="eb-hero"><div class="eb-hwrap">'
        f'<div class="eb-left"><div class="kicker">{kicker}</div>'
        f'<div class="eb-headline"><div class="l1">{line1}</div><div class="l2">{line2}</div></div>'
        f'<div class="eb-deck">{deck_html}</div></div>'
        f'<div class="eb-cuts">{cuts}</div>'
        '</div></div>'
    )


def bottom_nav_html(sections: list, current: str) -> str:
    """Fixed bottom pill nav: B&B mark + section links. `sections` is
    [(key, label), ...]; `current` is the active section key."""
    links = "".join(
        f'<a class="navlink{" active" if k == current else ""}" href="?p={k}" target="_self">{label}</a>'
        for k, label in sections
    )
    return (
        '<div class="bottom-bar-wrap"><div class="bottom-bar">'
        '<a class="bb-logo" href="?p=home" target="_self">'
        + logo_html(20, None, "B&amp;B") + '</a>'
        + links + '</div></div>'
    )


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


def phase_stepper_html(current: str, keeper_sub: str = "", draft_sub: str = "") -> str:
    """Horizontal season-phase progress. `current` is one of
    kreeper.phase.PHASES; a synthetic "draft_event" milestone is inserted
    between pre_draft and pre_season so the draft gets its own node."""
    order = ["keepers_open", "pre_draft", "draft_event", "pre_season", "in_season", "offseason"]
    labels = {
        "keepers_open": ("Keepers", keeper_sub),
        "pre_draft": ("Draft Prep", ""),
        "draft_event": ("Draft", draft_sub),
        "pre_season": ("Pre-Season", ""),
        "in_season": ("In-Season", ""),
        "offseason": ("Offseason", ""),
    }
    cur_idx = order.index(current) if current in order else 1
    cells = []
    for i, key in enumerate(order):
        label, sub = labels[key]
        state = "done" if i < cur_idx else ("now" if i == cur_idx else "")
        dot = "" if state == "done" else ("●" if state == "now" else str(i + 1))
        cells.append(
            f'<div class="step {state}"><div class="line"></div><div class="dot">{dot}</div>'
            f'<div class="lbl">{label}</div><div class="sub">{sub}</div></div>'
        )
    return '<div class="stepper">' + "".join(cells) + '</div>'


def inject(st) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
