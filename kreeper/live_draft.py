"""Live/offline draft-pick tracking — record picks as they're called out
during the actual draft, entirely independent of Sleeper's own draft room
(this league drafts offline; Sleeper is updated afterward by hand).

Persistence mirrors kreeper/lottery.py's pattern (GitHub-backed JSON with a
local fallback), built on storage's pre-existing private primitives so a
stale cached `storage` module on Streamlit Cloud can't AttributeError here.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

# Process-wide read cache: season -> (fetched_at, record). Every viewer's
# auto-refresh fragment reruns every few seconds; without this each rerun is
# its own GitHub API call (10 viewers = ~120 calls/min on one file). Also the
# stale-on-error source: a transient GitHub failure must serve the last good
# record, never an empty one, or the whole board blanks mid-draft.
_CACHE: Dict[int, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL = 4  # seconds


def _record_path(season: int) -> str:
    return f"data/live_draft_{season}.json"


def _record_local_path(season: int):
    import os
    from pathlib import Path
    from . import config
    base = Path(os.environ.get("KREEPER_DATA", config.DATA_DIR))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"live_draft_{season}.json"


def _gh_fetch(season: int) -> Tuple[Dict[str, Any], Optional[str]]:
    """(record, git blob sha). raw.githubusercontent.com first — it's off the
    REST quota — with the Contents API as the fallback."""
    import base64 as _b64
    import json as _json
    from . import storage
    tok, repo, branch = storage._gh_config()  # noqa: SLF001
    path = _record_path(season)
    # REST API first (always current; the shared cache keeps volume low). The
    # raw CDN is only the rate-limit fallback: it lags up to 5 minutes and
    # query strings don't bust it, so as a primary read it hides fresh picks
    # and hands saves a stale sha (409 conflicts).
    r = storage.requests.get(
        f"{storage._API}/repos/{repo}/contents/{path}",  # noqa: SLF001
        headers=storage._headers(tok), params={"ref": branch}, timeout=15,  # noqa: SLF001
    )
    if r.status_code == 404:
        return {}, None
    if r.status_code in (403, 429):
        raw = storage._raw_get(repo, branch, path)  # noqa: SLF001
        if raw is None:
            return {}, None
        text = raw.decode()
        return (_json.loads(text) if text.strip() else {}), storage._blob_sha(raw)  # noqa: SLF001
    r.raise_for_status()
    j = r.json()
    content = _b64.b64decode(j["content"]).decode()
    return (_json.loads(content) if content.strip() else {}), j["sha"]


def load_record(season: Optional[int] = None) -> Dict[str, Any]:
    """{"picks": {"<pick_no>": {"player_id","player_name","position","nfl"}}}.
    {} if nothing's been logged yet."""
    from . import config, storage
    season = season or config.current_season()
    if season == config.current_season() and storage._gh_config() is not None:  # noqa: SLF001
        now = time.time()
        cached = _CACHE.get(season)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]
        try:
            data, _ = _gh_fetch(season)
            _CACHE[season] = (now, data)
            return data
        except Exception:  # noqa: BLE001
            # Transient GitHub failure (rate limit, network blip): serve the
            # last good record rather than blanking the board.
            if cached:
                return cached[1]
    p = _record_local_path(season)
    if not p.exists():
        return {}
    try:
        import json as _json
        return _json.loads(p.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_record(data: Dict[str, Any], season: Optional[int] = None) -> None:
    from . import config, storage
    season = season or config.current_season()
    if season == config.current_season() and storage._gh_config() is not None:  # noqa: SLF001
        import base64 as _b64
        import json as _json
        tok, repo, branch = storage._gh_config()  # noqa: SLF001
        storage._ensure_branch(repo, branch, tok)  # noqa: SLF001
        path = _record_path(season)
        for _ in range(3):  # retry on a concurrent-write SHA conflict
            try:
                _, sha = _gh_fetch(season)  # sha from raw bytes: no API GET spent
            except Exception:  # noqa: BLE001
                sha = None
            body = {
                "message": f"live draft: {season} pick update",
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
                _CACHE[season] = (time.time(), data)  # write-through: own pick shows at once
                return
            if put.status_code != 409:
                put.raise_for_status()
        raise RuntimeError("GitHub save failed after retries")
    import json as _json
    p = _record_local_path(season)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(_json.dumps(data, indent=2))
    tmp.replace(p)
