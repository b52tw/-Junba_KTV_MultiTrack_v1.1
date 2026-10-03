from __future__ import annotations
import json
from pathlib import Path
from .models import TextTrack


def save_project(path: str, audio_path: str, tracks: list[TextTrack], active_index: int = 0, compare_index: int = -1):
    obj = {
        "format": "JunbaKTVProject/1",
        "audio_path": audio_path,
        "active_index": active_index,
        "compare_index": compare_index,
        "tracks": [t.to_dict() for t in tracks],
    }
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def load_project(path: str):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    tracks = [TextTrack.from_dict(t) for t in obj.get("tracks", [])]
    return obj.get("audio_path", ""), tracks, int(obj.get("active_index", 0)), int(obj.get("compare_index", -1))
