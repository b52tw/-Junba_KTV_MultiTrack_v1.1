from app.models import Segment, TextTrack
from app.review import similarity, compare_tracks

def test_similarity_identical():
    assert similarity('你好，世界。', '你好世界') > 0.95

def test_compare_red_on_mismatch():
    a=TextTrack('a',[Segment(0,2,'今天討論績效管理')],timed=True)
    b=TextTrack('b',[Segment(0,2,'明天放假去旅行')],timed=True)
    r=compare_tracks(a,b)[0]
    assert r.level == 'red'

def test_compare_green_on_close_text():
    a=TextTrack('a',[Segment(0,2,'今天討論績效管理')],timed=True)
    b=TextTrack('b',[Segment(0,2,'今天討論績效管理。')],timed=True)
    r=compare_tracks(a,b)[0]
    assert r.level == 'green'
