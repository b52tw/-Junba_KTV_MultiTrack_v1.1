from __future__ import annotations
import re
from difflib import SequenceMatcher
from dataclasses import dataclass
from .models import Segment, TextTrack


def normalize_text(text: str) -> str:
    text = (text or '').lower()
    text = re.sub(r'[\s\u3000]+', '', text)
    text = re.sub(r'[，。！？；：、,.!?;:"“”‘’()（）\[\]【】<>《》…—\-]+', '', text)
    return text


def similarity(a: str, b: str) -> float:
    a = normalize_text(a); b = normalize_text(b)
    if not a and not b: return 1.0
    if not a or not b: return 0.0
    return SequenceMatcher(None, a, b).ratio()


def find_time_match(seg: Segment, track: TextTrack) -> Segment | None:
    if not track.segments:
        return None
    mid = (seg.start + seg.end) / 2 if seg.end > seg.start else seg.start
    overlap = [x for x in track.segments if x.start <= mid < max(x.end, x.start + .05)]
    if overlap:
        return overlap[0]
    return min(track.segments, key=lambda x: abs(x.start - mid))


@dataclass
class ReviewResult:
    index: int
    score: float
    level: str
    other_text: str
    note: str


def compare_tracks(base: TextTrack, other: TextTrack, good: float = .82, warn: float = .55) -> list[ReviewResult]:
    out: list[ReviewResult] = []
    for i, seg in enumerate(base.segments):
        hit = find_time_match(seg, other)
        if hit is None:
            out.append(ReviewResult(i, 0.0, 'red', '', '找不到對應文字'))
            continue
        score = similarity(seg.text, hit.text)
        level = 'green' if score >= good else ('yellow' if score >= warn else 'red')
        note = '高度吻合' if level == 'green' else ('建議人工核對' if level == 'yellow' else '可能漏字、錯字或內容不一致')
        out.append(ReviewResult(i, score, level, hit.text, note))
    return out
