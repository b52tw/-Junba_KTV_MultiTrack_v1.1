from pathlib import Path
from app.models import Segment,TextTrack
from app.html_export import export_html_package


def test_html(tmp_path):
    audio=tmp_path/'a.m4a'; audio.write_bytes(b'fake')
    tr=TextTrack('逐字稿',[Segment(0,2,'你好'),Segment(2,4,'世界')],timed=True)
    p=export_html_package(str(tmp_path/'out'),str(audio),[tr])
    s=p.read_text(encoding='utf-8')
    assert 'junba-ktv-data' in s and '你好' in s and (p.parent/'01_逐字稿.vtt').exists()
