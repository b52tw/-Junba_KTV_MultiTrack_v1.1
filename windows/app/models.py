from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class Segment:
    start: float
    end: float
    text: str
    speaker: str = ""
    estimated: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(
            start=float(d.get("start", 0.0)),
            end=float(d.get("end", d.get("start", 0.0))),
            text=str(d.get("text", "")),
            speaker=str(d.get("speaker", "")),
            estimated=bool(d.get("estimated", False)),
        )


@dataclass
class TextTrack:
    name: str
    segments: List[Segment] = field(default_factory=list)
    source_path: str = ""
    format_name: str = "TXT"
    timed: bool = False
    estimated: bool = False

    @property
    def full_text(self) -> str:
        return " ".join(s.text.strip() for s in self.segments if s.text.strip()).strip()

    def to_dict(self):
        return {
            "name": self.name,
            "source_path": self.source_path,
            "format_name": self.format_name,
            "timed": self.timed,
            "estimated": self.estimated,
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            name=str(d.get("name", "文字軌")),
            source_path=str(d.get("source_path", "")),
            format_name=str(d.get("format_name", "TXT")),
            timed=bool(d.get("timed", False)),
            estimated=bool(d.get("estimated", False)),
            segments=[Segment.from_dict(x) for x in d.get("segments", [])],
        )
