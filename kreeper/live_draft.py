"""Live/offline draft-pick tracking — record picks as they're called out
during the actual draft, entirely independent of Sleeper's own draft room
(this league drafts offline; Sleeper is updated afterward by hand).

Persistence mirrors kreeper/lottery.py's pattern (GitHub-backed JSON with a
local fallback), built on storage's pre-existing private primitives so a
stale cached `storage` module on Streamlit Cloud can't AttributeError here.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _record_path(season: int) -> str:
    return f"data/live_draft_{season}.json"


def _record_local_path(season: int):
    import os
    from pathlib import Path
    from . import config
    base = Path(os.environ.get("KREEPER_DATA", config.DATA_DIR))
    base.mkdir(parents=True, exist_ok=True)
    return base / f"live_draft_{season}.json"


def load_record(season: Optional[int] = None) -> Dict[str, Any]:
    """{"picks": {"<pick_no>": {"player_id","player_name","position","nfl"}}}.
    {} if nothing's been logged yet."""
    from . import config, storage
    season = season or config.current_season()
    if season == config.current_season() and storage._gh_config() is not None:  # noqa: SLF001
        try:
            tok, repo, branch = storage._gh_config()  # noqa: SLF001
            r = storage.requests.get(
                f"{storage._API}/repos/{repo}/contents/{_record_path(season)}",  # noqa: SLF001
                headers=storage._headers(tok), params={"ref": branch}, timeout=15,  # noqa: SLF001
            )
            if r.status_code == 404:
                return {}
            r.raise_for_status()
            import base64 as _b64
            import json as _json
            content = _b64.b64decode(r.json()["content"]).decode()
            return _json.loads(content) if content.strip() else {}
        except Exception:  # noqa: BLE001
            pass
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
            sha = None
            r = storage.requests.get(
                f"{storage._API}/repos/{repo}/contents/{path}",  # noqa: SLF001
                headers=storage._headers(tok), params={"ref": branch}, timeout=15,  # noqa: SLF001
            )
            if r.status_code == 200:
                sha = r.json()["sha"]
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
                return
            if put.status_code != 409:
                put.raise_for_status()
        raise RuntimeError("GitHub save failed after retries")
    import json as _json
    p = _record_local_path(season)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(_json.dumps(data, indent=2))
    tmp.replace(p)
