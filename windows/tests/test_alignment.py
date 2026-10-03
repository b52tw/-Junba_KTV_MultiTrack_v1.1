from app.models import Segment,TextTrack
from app.alignment import align_untimed_to_base, align_untimed_to_duration


def test_align_base():
    base=TextTrack("base",[Segment(0,5,"a"),Segment(5,10,"b")],timed=True)
    t=TextTrack("x",[Segment(0,0,"甲乙丙丁戊己庚辛")],timed=False,estimated=True)
    r=align_untimed_to_base(t,base)
    assert r.timed and r.estimated and len(r.segments)==2 and r.segments[-1].end==10


def test_align_duration():
    t=TextTrack("x",[Segment(0,0,"甲"),Segment(0,0,"乙乙乙")],timed=False,estimated=True)
    r=align_untimed_to_duration(t,40)
    assert abs(r.segments[-1].end-40)<1e-6
