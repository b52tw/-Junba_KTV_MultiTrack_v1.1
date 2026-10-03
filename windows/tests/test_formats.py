from pathlib import Path
from app.formats import parse_srt, parse_vtt, parse_txt, parse_json_text, parse_time, to_vtt


def test_time():
    assert abs(parse_time("01:02:03,500") - 3723.5) < 0.001


def test_srt():
    t=parse_srt("1\n00:00:01,000 --> 00:00:03,000\n講者1：你好\n\n2\n00:00:03,000 --> 00:00:05,000\n世界")
    assert t.timed and len(t.segments)==2 and t.segments[0].text=="你好"


def test_vtt():
    t=parse_vtt("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\n測試")
    assert t.segments[0].end==2


def test_txt_untimed():
    t=parse_txt("第一句。第二句！第三句？")
    assert not t.timed and len(t.segments)>=3


def test_json():
    t=parse_json_text('{"segments":[{"start":0,"end":1.2,"text":"哈囉"}]}')
    assert t.timed and t.segments[0].text=="哈囉"
