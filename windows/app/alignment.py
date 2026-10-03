from __future__ import annotations
from typing import List
from .models import Segment, TextTrack


def align_untimed_to_base(track: TextTrack, base: TextTrack) -> TextTrack:
    """Estimate timing for an untimed text track using a timed base track.
    Keeps the imported wording intact; only assigns approximate intervals.
    """
    if track.timed or not track.segments or not base.segments:
        return track
    texts = [s.text.strip() for s in track.segments if s.text.strip()]
    if not texts:
        return track
    n = len(base.segments)
    joined = " ".join(texts)
    # Allocate imported text proportionally by characters into exactly n buckets.
    total = max(1, len(joined))
    targets = [round(total * (i + 1) / n) for i in range(n)]
    buckets, pos = [], 0
    for tgt in targets:
        cut = min(len(joined), max(pos + 1, tgt))
        if cut < len(joined):
            # Seek a nearby natural boundary.
            for delta in range(0, 40):
                for candidate in (cut + delta, cut - delta):
                    if pos < candidate < len(joined) and joined[candidate-1] in "。！？!?；;,.， ":
                        cut = candidate; break
                else:
                    continue
                break
        buckets.append(joined[pos:cut].strip())
        pos = cut
    if pos < len(joined) and buckets:
        buckets[-1] = (buckets[-1] + " " + joined[pos:]).strip()
    segs = []
    for i, b in enumerate(base.segments):
        txt = buckets[i] if i < len(buckets) else ""
        segs.append(Segment(b.start, b.end, txt, "", True))
    return TextTrack(track.name, segs, track.source_path, track.format_name, True, True)


def align_untimed_to_duration(track: TextTrack, duration: float) -> TextTrack:
    if track.timed or not track.segments or duration <= 0:
        return track
    texts = [s.text.strip() for s in track.segments if s.text.strip()]
    weights = [max(1, len(t)) for t in texts]
    total = sum(weights)
    cur = 0.0
    segs = []
    for txt, w in zip(texts, weights):
        span = duration * w / total
        segs.append(Segment(cur, min(duration, cur + span), txt, "", True))
        cur += span
    if segs:
        segs[-1].end = duration
    return TextTrack(track.name, segs, track.source_path, track.format_name, True, True)
