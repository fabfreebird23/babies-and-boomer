"""Old-school Eastbay '90s theme: purple/gold/black duotone magazine look —
brush-script wordmark, yellow cut-out frames, white/black label tags, gritty
halftone field. Shared CSS for the custom HTML surfaces (leaderboard, team
cards, draft board) plus purple-duotone, gold-framed Sleeper headshots.
"""
from __future__ import annotations

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
  --bg:#0d0a14; --panel:#100b1d; --panel2:#150e26;
  --purple:#4b2d9f; --purple-d:#28184f; --purple-l:#7a5bd8;
  --gold:#ffce1f; --gold-d:#e0a400; --cyan:#3fd0e8; --red:#ff4f4f;
  --ink:#f3eefe; --muted:#9b8fc4; --line:#2a1f47;
}

/* gritty purple/gold/black magazine field */
.stApp{
  background-color:#0d0a14;
  background-image:
    radial-gradient(60% 45% at 16% 6%, rgba(123,91,216,.30), transparent 46%),
    radial-gradient(56% 42% at 100% 92%, rgba(255,206,31,.10), transparent 48%),
    repeating-radial-gradient(circle at 0 0, rgba(255,255,255,.030) 0 1px, transparent 1px 4px),
    linear-gradient(165deg,#170f2b 0%, #0a0712 62%);
  background-attachment:fixed;
}
html, body, [class*="css"]{ font-family:'Oswald', sans-serif; color:var(--ink); }

/* faint scratch/scanline grit */
.stApp::before{ content:""; position:fixed; inset:0; pointer-events:none; z-index:9998; opacity:.5;
  background:repeating-linear-gradient(to bottom, transparent 0 3px, rgba(0,0,0,.18) 3px 4px); }

[data-testid="stHeader"]{ background:transparent; }
[data-testid="stSidebar"]{ background:rgba(13,10,20,.92); border-right:3px solid var(--gold); }

/* headings — heavy condensed caps. h2 = magazine "panel" bar. */
h1,h2,h3{ font-family:'Anton', sans-serif !important; letter-spacing:2px; text-transform:uppercase; }
h1{ color:var(--gold); }
h2{ color:#fff; background:var(--purple); border-bottom:3px solid var(--gold);
  padding:9px 14px; display:flex; align-items:center; box-shadow:5px 5px 0 rgba(40,24,79,.55); }
h3{ color:#fff; }

/* brush-script wordmark — purple fill, gold outline, drop shadow */
.neon-logo{ font-family:'Pacifico', cursive; color:var(--purple-l); line-height:1;
  -webkit-text-stroke:3px var(--gold);
  text-shadow:5px 5px 0 var(--purple-d), 0 0 18px rgba(123,91,216,.5);
  transform:rotate(-3deg); display:inline-block; white-space:nowrap; }
.neon-tag{ font-family:'Oswald'; letter-spacing:6px; font-weight:700; font-size:11px;
  color:var(--gold); text-transform:uppercase; margin-top:8px; }
/* let the sidebar mark spell the league name out across two lines */
[data-testid="stSidebar"] .neon-logo{ white-space:normal; line-height:.92; -webkit-text-stroke-width:2px; }

/* ---- magazine masthead + hero band (Home) ---- */
.eb-mast{ display:flex; align-items:flex-start; justify-content:space-between; gap:18px;
  border-bottom:3px solid var(--gold); padding-bottom:12px; margin-bottom:4px; }
.eb-issue{ text-align:right; font-weight:700; white-space:nowrap; padding-top:6px; }
.eb-issue .vol{ font-family:'Anton'; font-size:15px; color:var(--gold); letter-spacing:3px; }
.eb-issue .sub{ font-size:11px; letter-spacing:3px; color:var(--purple-l); text-transform:uppercase; margin-top:3px; }
.eb-issue .px{ display:inline-block; margin-top:8px; background:var(--gold); color:#000;
  font-family:'Anton'; font-size:12px; letter-spacing:2px; padding:3px 9px; transform:skewX(-8deg); }

.eb-hero{ position:relative; margin:14px 0 22px; border:1px solid #1d1430;
  background:linear-gradient(120deg,#1b1130,#0a0712 70%); overflow:hidden; }
.eb-hwrap{ display:grid; grid-template-columns:1.2fr 1fr; }
.eb-left{ padding:26px 26px 30px; }
.eb-left .kicker{ font-weight:700; letter-spacing:6px; font-size:12px; color:var(--gold); text-transform:uppercase; }
.eb-headline{ font-family:'Anton'; text-transform:uppercase; line-height:.9; margin:8px 0 2px; }
.eb-headline .l1{ font-size:54px; letter-spacing:2px; color:#fff; }
.eb-headline .l2{ font-size:54px; letter-spacing:13px; color:var(--gold); text-shadow:4px 4px 0 var(--purple); }
.eb-deck{ margin-top:12px; max-width:380px; color:#d7ccf5; font-size:14px; line-height:1.45; font-weight:500; }
.eb-deck b{ color:var(--gold); }
.eb-cuts{ position:relative; min-height:230px;
  background:repeating-linear-gradient(180deg, rgba(75,45,159,.18) 0 2px, transparent 2px 6px); }
.cut{ position:absolute; border:2px solid var(--gold); overflow:hidden; box-shadow:0 0 0 3px #000; }
.cut svg{ display:block; width:100%; height:100%; }
.cut.a{ width:128px; height:108px; top:44px; right:30px; }
.cut.b{ width:108px; height:134px; top:96px; right:140px; }
.cut.c{ width:136px; height:108px; bottom:18px; right:34px; }
.lab{ position:absolute; display:inline-flex; font-family:'Oswald'; font-weight:700;
  font-size:11px; letter-spacing:2px; text-transform:uppercase; z-index:3; }
.lab span{ padding:3px 8px; }
.lab .w{ background:#fff; color:#000; }
.lab .k{ background:#000; color:#fff; border:1px solid #fff; }
.lab.t1{ top:8px; right:26px; }
.lab.t2{ top:78px; right:140px; }
.lab.t3{ bottom:0; right:40px; }
a.lab{ text-decoration:none; cursor:pointer; }
a.lab:hover .w{ background:var(--gold); }
a.lab:hover .k{ background:var(--purple); border-color:var(--gold); color:#fff; }

/* sidebar nav radio -> Eastbay white/black label tags (gold when selected) */
[data-testid="stSidebar"] [role="radiogroup"] label{ border:1px solid #fff; border-radius:0;
  padding:6px 11px; margin-bottom:7px; background:#000; transition:.12s; }
[data-testid="stSidebar"] [role="radiogroup"] label:hover{ border-color:var(--gold); }
[data-testid="stSidebar"] [role="radiogroup"] label p{ font-weight:700; text-transform:uppercase;
  letter-spacing:2px; font-size:13px; color:#fff; }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){ background:var(--gold); border-color:var(--gold); }
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) p{ color:#000; }
/* hide the radio dot so it reads as a pure tag */
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child{ display:none; }

.stButton>button{ font-family:'Anton'; letter-spacing:2px; text-transform:uppercase;
  background:var(--gold); color:#000; border:none; border-radius:0; }
.stButton>button:hover{ background:var(--purple); color:#fff; box-shadow:0 0 0 2px var(--gold); }

/* ---- shared custom tables ---- */
.neonwrap{ overflow:auto; max-height:72vh; border:2px solid var(--gold); border-radius:0;
  background:#080611; box-shadow:0 12px 34px rgba(0,0,0,.5); }
table.lb{ width:100%; border-collapse:collapse; font-family:'Oswald'; font-size:14px; }
table.lb th{ background:var(--gold); color:#0a0712; text-transform:uppercase; letter-spacing:1px;
  font-family:'Anton'; font-weight:400; font-size:12px; text-align:left; padding:8px 10px;
  position:sticky; top:0; }
table.lb th.r{ text-align:right; }
table.lb td{ padding:6px 10px; border-bottom:1px solid var(--line); color:var(--ink); }
table.lb tr:nth-child(odd) td{ background:rgba(75,45,159,.10); }
table.lb tr:hover td{ background:rgba(255,206,31,.10); }
table.lb tr.kept td{ background:linear-gradient(90deg, rgba(255,206,31,.22), rgba(255,206,31,.05)); }
table.lb tr.kept td:first-child{ box-shadow:inset 4px 0 0 var(--gold); }
.lb .rk{ font-family:'Anton'; color:var(--gold); width:34px; text-align:center; }
.lb .pl{ font-weight:600; color:#fff; }
.lb .pos{ color:var(--muted); font-size:11px; font-weight:600; white-space:nowrap; }
.lb .val{ font-family:'Anton'; color:#7CFFB0; text-align:right; letter-spacing:1px; }
.lb .num{ text-align:right; color:var(--ink); }
.lb .kept-badge{ color:#000; background:var(--gold); font-weight:700; font-size:10px;
  font-family:'Anton'; padding:1px 6px; text-transform:uppercase; letter-spacing:1px; }
.lb .rk-badge{ color:#000; background:var(--gold); font-weight:700; font-size:10px;
  font-family:'Anton'; padding:1px 6px; text-transform:uppercase; letter-spacing:1px; margin-left:4px; }
.lb .fa-tag{ color:var(--cyan); font-weight:600; font-size:12px; font-style:italic; }
table.lb tr.fa td{ background:rgba(63,208,232,.06); }

/* purple-duotone, gold-framed headshots (full colour on hover) */
.hs{ width:32px; height:32px; border-radius:4px; object-fit:cover; vertical-align:middle;
  background:#1c1140; border:2px solid var(--gold); margin-right:9px;
  filter:grayscale(1) contrast(1.05) sepia(.55) hue-rotate(205deg) saturate(1.9) brightness(.98);
  transition:filter .15s; }
.hs:hover{ filter:none; }
.posdot{ display:inline-block; width:7px;height:7px;border-radius:50%;margin-right:5px;vertical-align:middle;}
.p-QB{background:var(--gold);} .p-RB{background:var(--purple-l);} .p-WR{background:var(--cyan);} .p-TE{background:#ff79c6;}

/* team cards — black panels, gold top rule */
.kcards{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; }
.kcard{ border:1px solid var(--line); border-top:3px solid var(--gold); border-radius:0;
  background:#0b0818; padding:10px 12px; min-height:96px; box-shadow:0 6px 18px rgba(0,0,0,.45); }
.kcard h4{ font-family:'Anton'; font-size:15px; margin:0 0 6px; color:var(--gold); letter-spacing:1px; text-transform:uppercase; }
.kcard .kp{ display:flex; align-items:center; font-size:13px; padding:2px 0; color:#ece6fb; }
.kcard .kp img{ width:24px;height:24px;border-radius:4px;margin-right:7px;object-fit:cover;background:#1c1140;
  border:1.5px solid var(--gold-d);
  filter:grayscale(1) sepia(.55) hue-rotate(205deg) saturate(1.9) brightness(.98); }
.kcard .kp .rd{ margin-left:auto; color:var(--gold); font-weight:700; font-family:'Anton'; }
.kcard .empty{ color:var(--muted); font-style:italic; font-size:12px; }
.kcard .rk-tag{ color:#000; background:var(--gold); font-size:9px; font-weight:700;
  font-family:'Anton'; padding:0 4px; margin-left:5px; letter-spacing:1px; }

/* draft board */
table.dboard{ width:100%; border-collapse:collapse; table-layout:fixed; font-family:'Oswald'; font-size:12px; }
table.dboard th{ background:var(--gold); color:#0a0712; text-align:center; font-family:'Anton'; font-weight:400;
  font-size:11px; padding:5px; border:1px solid #0a0712; text-transform:uppercase; letter-spacing:1px; }
.dbcell{ border:1px solid var(--line); padding:3px 4px; vertical-align:top; height:48px; }
table.dboard td.dbcell{ padding:3px 4px; }
.dbpick{ color:#6b5f93; font-size:9px; white-space:nowrap; }
.db-base{ background:#0b0818; color:#8a7fb3; }
.db-traded{ background:rgba(255,206,31,.16); color:var(--gold); }
.db-keep{ background:rgba(124,255,176,.14); color:#7CFFB0; box-shadow:inset 0 0 0 1px rgba(124,255,176,.4); }
.db-conflict{ background:rgba(255,79,79,.18); color:#ff8a8a; box-shadow:inset 0 0 0 1px rgba(255,79,79,.5); }
.db-rd{ background:var(--purple); color:var(--gold); font-family:'Anton'; text-align:center; white-space:nowrap; }

/* section header — duotone football (a colourway per section) */
.sneak{ display:inline-block; vertical-align:middle; height:42px; margin:0 14px 6px 0;
  filter:drop-shadow(3px 3px 0 rgba(40,24,79,.9)); }

/* ---------------- mobile ---------------- */
@media (max-width: 640px){
  .neon-logo{ font-size:40px !important; -webkit-text-stroke-width:2px; }
  .neon-tag{ font-size:8px; letter-spacing:4px; }
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
}
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


def hero(kicker: str, line1: str, line2: str, deck_html: str,
         tags=(("Draft", "Board", "Draft Board"),
               ("Set", "Keepers", "Set My Keepers"),
               ("Title", "Odds", "Title Odds"))) -> str:
    """Cover-style hero band: big headline + football cut-outs + clickable label
    tags. Each tag links to ?nav=<page>, which the sidebar radio reads to switch.
    A tag whose second segment is empty renders as a single label."""
    from urllib.parse import quote

    def _tag(i, a, b, nav):
        inner = f'<span class="w">{a}</span>'
        if b:
            inner += f'<span class="k">{b}</span>'
        return (f'<a class="lab t{i+1}" href="?nav={quote(nav)}" target="_self">'
                f'{inner}</a>')

    labs = "".join(_tag(i, a, b, nav) for i, (a, b, nav) in enumerate(tags))
    cuts = (
        f'<div class="cut a">{_football(128, 108, GOLD, "#1c1140")}</div>'
        f'<div class="cut b">{_football(108, 134, PURPLE, GOLD)}</div>'
        f'<div class="cut c">{_football(136, 108, GOLD, "#1c1140")}</div>'
    )
    return (
        '<div class="eb-hero"><div class="eb-hwrap">'
        f'<div class="eb-left"><div class="kicker">{kicker}</div>'
        f'<div class="eb-headline"><div class="l1">{line1}</div><div class="l2">{line2}</div></div>'
        f'<div class="eb-deck">{deck_html}</div></div>'
        f'<div class="eb-cuts">{cuts}{labs}</div>'
        '</div></div>'
    )


def inject(st) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
