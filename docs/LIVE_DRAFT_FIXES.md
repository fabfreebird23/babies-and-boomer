# Live Draft Board — draft-day fixes to port to the other leagues

Everything below was found and fixed during the Babies and Boomer 2026 offline draft
(2026-09-07). Each item says what broke, why, and the exact change. The Kreeper League and
7 1/2 Men boards share the same architecture (Streamlit Cloud + GitHub-backed JSON via
`kreeper/storage.py`, `st.fragment(run_every=5)` auto-refresh), so the same changes apply.
Reference implementation: this repo, commits `498d418`, `2e86e23`, and the chime fix.

---

## 1. The board blanks under GitHub's REST rate limit  (critical)

**Symptom.** Mid-draft the whole board went empty ("0/160 picks in", no keepers), came back
about an hour later, then blanked again. Picks were still being saved.

**Cause.** Every viewer's auto-refresh fragment reruns every 5 s and each rerun made its own
`api.github.com` call per file. 10 viewers × 12/min × 2 files ≈ 240 calls/min, so the
5,000/hour quota (per GitHub *user*, shared by every token that user owns) was gone in
minutes. A 403 fell through the `except` to the empty local fallback, which renders as a
blank board until the hourly reset.

**Fix (three parts).**

**a) Process-wide short-TTL read cache** — N viewers share one fetch.

```python
# kreeper/live_draft.py  (storage.py already had _CACHE / _CACHE_TTL = 8 for keepers)
import time
_CACHE: Dict[int, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 4  # seconds

def load_record(season=None):
    ...
    if season == config.current_season() and storage._gh_config() is not None:
        now = time.time()
        cached = _CACHE.get(season)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]
        try:
            data, _ = _gh_fetch(season)
            _CACHE[season] = (now, data)
            return data
        except Exception:
            if cached:            # b) stale-on-error, see below
                return cached[1]
    ...local fallback...
```

Streamlit Cloud runs one server process for all viewers, so a module-level dict is shared.
With a 4 s TTL the whole room costs ≤ 900 calls/hour for this file.

**b) Stale-on-error** — a failed refresh serves the last good data, never `{}`.
Shown above for live picks; the same two lines go in `storage.load()`:

```python
def load(season=None):
    ...
    if _use_remote(season):
        try:
            return _gh_load_cached(season)
        except Exception:
            c = _CACHE.get(season)
            if c:
                return c[1]        # last good read beats an empty local fallback
    return _local_load(season)
```

**c) Write-through after a save** — so the saver's own pick shows immediately instead of
after the TTL:

```python
# in save_record, right after a 200/201 from the PUT
_CACHE[season] = (time.time(), data)
```

**d) raw.githubusercontent.com as the *fallback only*.** When the REST API answers 403/429,
read the file from the raw CDN (public repo: no token needed; private: `Authorization: token`).
It does not count against the REST quota. But it lags up to 5 minutes and ignores
cache-busting query strings, so it must **never** be the primary read — as primary it hid
fresh picks and fed saves a stale sha (409 conflicts).

```python
_RAW = "https://raw.githubusercontent.com"

def _raw_get(repo, branch, path) -> Optional[bytes]:
    tok = (_gh_config() or ("",))[0]
    headers = {"Authorization": f"token {tok}"} if tok else {}
    r = requests.get(f"{_RAW}/{repo}/{branch}/{path}", headers=headers,
                     params={"nocache": str(time.time_ns())}, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content

def _blob_sha(raw: bytes) -> str:
    """git blob sha of these bytes == the `sha` the Contents API wants on update."""
    import hashlib
    return hashlib.sha1(b"blob %d\0" % len(raw) + raw).hexdigest()

# in _gh_get / _gh_fetch:
r = requests.get(f"{_API}/repos/{repo}/contents/{path}", headers=_headers(tok),
                 params={"ref": branch}, timeout=15)
if r.status_code == 404:
    return {}, None
if r.status_code in (403, 429):
    raw = _raw_get(repo, branch, path)
    if raw is None:
        return {}, None
    text = raw.decode()
    return (json.loads(text) if text.strip() else {}), _blob_sha(raw)
r.raise_for_status()
...
```

**e) Cheaper saves.** Saves used two API calls (GET for sha, then PUT) plus a branch check.
Get the sha from the same `_gh_fetch` (API-first, so it's current) and memoize the branch
check; treat 403/429 on the branch check as "branch exists":

```python
_BRANCH_SEEN: set = set()

def _ensure_branch(repo, branch, tok):
    if (repo, branch) in _BRANCH_SEEN:
        return
    st = requests.get(f"{_API}/repos/{repo}/branches/{branch}", headers=_headers(tok), timeout=15).status_code
    if st == 200 or st in (403, 429):
        _BRANCH_SEEN.add((repo, branch))
        return
    ...create branch as before...
```

**How to verify.** While the room is polling, call `GET https://api.github.com/rate_limit`
with the app token every minute: `remaining` should drop by a handful, not by ~100+.

---

## 2. A failed save crashes the fragment instead of showing a message

**Symptom.** Undo / Reset raised straight through Streamlit; the board disappeared for that
viewer until the next rerun.

**Fix.** Wrap every `save_record` call site and say what's happening:

```python
try:
    live_draft.save_record(record, SEASON)
    st.rerun(scope="fragment")
except Exception as e:
    st.error("Couldn't save this pick — GitHub is throttling writes right now. "
             "Jot it down and log it again in a few minutes; the board itself stays live. "
             f"({type(e).__name__})")
```

Same wrapper on the Undo button and the Reset expander.

---

## 3. The page jumps to the top whenever anyone picks

**Symptom.** Every time a pick landed, every viewer's page scrolled to the top.

**Cause.** The sound-chime `components.html(...)` was rendered *only* on the rerun where a new
pick was detected. Inserting a brand-new component iframe mid-page forces a re-layout and
the browser jumps to the top. (Re-rendering an element that is already there does not.)

**Fix.** Render the chime slot on every rerun with `height=0` and gate the sound in JS:

```python
last_seen = st.session_state.get("ld_seen_picks")
play = st.session_state.get("ld_sound", True) and last_seen is not None and made > last_seen
components.html(
    "<script>(function(){"
    f"if(!{'true' if play else 'false'}) return;"
    "try{ ...oscillator chime... }catch(e){}"
    "})();</script>",
    height=0,
)
st.session_state["ld_seen_picks"] = made
```

Rule of thumb for any Streamlit page that auto-refreshes: never make a `components.html`
appear or disappear between reruns — keep the element present and change its content.

---

## 4. Draft-day operating rules (not code)

- **Don't push to `main` during the draft.** Every push redeploys Streamlit Cloud, which
  blanks the app for ~30–60 s. Ship UI tweaks the day before.
- **Bots count too.** The daily ADP refresh workflow commits to `main` (`[skip ci]` only skips
  GitHub Actions, not Streamlit's redeploy). Either run it at a time that can't collide with
  a draft or, better, have it commit to a data branch the app reads.
- **Never test writes against the real repo.** `.streamlit/secrets.toml` carries a live
  token; an interactive `streamlit run` there saves to production. Use an rsync'd `/tmp`
  copy with an empty `secrets.toml` for anything that clicks Log / Undo / Reset.
- **Entering the draft into Sleeper afterward:** the live board's CSV export
  (Pick, Round, Slot, Team, Traded From, Type, Player, Pos, NFL) is the source list. In
  Sleeper's draft room the commissioner clicks a board cell → *Set Player*. Check keeper
  pre-loads — Sleeper missed one keeper this year.

---

## Checklist to apply elsewhere

- [ ] `live_draft.py`: `_CACHE` + TTL, `_gh_fetch` (API first, raw on 403/429), stale-on-error,
      write-through in `save_record`, sha from `_gh_fetch`
- [ ] `storage.py`: `_raw_get`, `_blob_sha`, memoized `_ensure_branch`, raw fallback in
      `_gh_get`, stale-on-error in `load()`
- [ ] `app.py`: try/except + message on every `save_record` call (log, undo, reset)
- [ ] `app.py`: chime `components.html` rendered every rerun, gated in JS
- [ ] Freeze `main` on draft day; check the ADP bot's schedule
