from __future__ import annotations
import json, shutil
import html as _html
from pathlib import Path
from .models import TextTrack
from .formats import to_vtt

HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>峻爸 KTV 多文字軌核對器</title>
<style>
body{font-family:"Microsoft JhengHei",system-ui,sans-serif;margin:0;background:#111;color:#eee}.wrap{max-width:1200px;margin:auto;padding:18px}
.card{background:#1e1e1e;border:1px solid #444;border-radius:12px;padding:14px;margin-bottom:14px}select,button,input{font-size:16px;padding:7px;margin:3px;background:#2b2b2b;color:#fff;border:1px solid #555;border-radius:7px}
audio{width:100%}.full{line-height:2.05;font-size:20px;max-height:38vh;overflow:auto;padding:12px;background:#171717;border-radius:8px}
.seg{padding:2px 3px;border-radius:4px;cursor:pointer}.seg.current{background:#5d4d00;color:#fff}.seg .done{background:#ffd54f;color:#111;border-radius:3px}
.timeline{max-height:40vh;overflow:auto}.row{padding:10px;border-bottom:1px solid #3a3a3a;cursor:pointer}.row.current{background:#263238}.time{color:#90caf9;font-family:monospace}.speaker{color:#ffcc80}
.small{color:#aaa;font-size:13px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:800px){.grid{grid-template-columns:1fr}}
</style></head><body><div class="wrap">
<div class="card"><b>峻爸 KTV 多文字軌核對器</b><div class="small">完全離線播放器；點文字可跳到錄音位置。</div>
<audio id="audio" controls preload="metadata" src="__AUDIO__"></audio></div>
<div class="card grid"><div>上方 KTV 文字軌：<select id="active"></select></div><div>下方比較文字軌：<select id="compare"><option value="-1">不比較</option></select></div></div>
<div class="card"><div id="full" class="full"></div></div>
<div class="card"><div id="timeline" class="timeline"></div></div>
</div>
<script id="junba-ktv-data" type="application/json">__DATA__</script>
<script>
const DATA=JSON.parse(document.getElementById('junba-ktv-data').textContent), audio=document.getElementById('audio');
const active=document.getElementById('active'), compare=document.getElementById('compare'), full=document.getElementById('full'), timeline=document.getElementById('timeline');
DATA.tracks.forEach((t,i)=>{let o=new Option(t.name+(t.estimated?'（估算）':''),i);active.add(o);let c=o.cloneNode(true);compare.add(c)});
let cur=-1;function esc(s){return (s||'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}
function render(){let t=DATA.tracks[+active.value];full.innerHTML=t.segments.map((s,i)=>`<span class="seg" data-i="${i}">${esc(s.text)} </span>`).join('');
let c=+compare.value, ct=c>=0?DATA.tracks[c]:null;timeline.innerHTML=t.segments.map((s,i)=>{let other='';if(ct&&ct.segments.length){let mid=(s.start+s.end)/2, hit=ct.segments.find(x=>x.start<=mid&&mid<Math.max(x.end,x.start+.05));if(!hit)hit=ct.segments.reduce((a,b)=>Math.abs(b.start-mid)<Math.abs(a.start-mid)?b:a,ct.segments[0]);other=`<div class="small">${esc(hit.text)}</div>`}return `<div class="row" data-i="${i}"><span class="time">${fmt(s.start)}–${fmt(s.end)}</span> <span class="speaker">${esc(s.speaker)}</span><div>${esc(s.text)}</div>${other}</div>`}).join('');
document.querySelectorAll('[data-i]').forEach(el=>el.onclick=()=>{let s=t.segments[+el.dataset.i];audio.currentTime=s.start;audio.play()});cur=-1;tick()}
function fmt(x){x=Math.max(0,x||0);let h=Math.floor(x/3600),m=Math.floor(x%3600/60),s=Math.floor(x%60);return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`}
function tick(){let t=DATA.tracks[+active.value], now=audio.currentTime||0, i=t.segments.findIndex(s=>now>=s.start&&now<(s.end||s.start+.1));if(i<0&&t.segments.length&&now>=t.segments.at(-1).end)i=t.segments.length-1;
if(i!==cur){document.querySelectorAll('.current').forEach(x=>x.classList.remove('current'));let a=full.querySelector(`[data-i="${i}"]`),r=timeline.querySelector(`[data-i="${i}"]`);if(a){a.classList.add('current');a.scrollIntoView({block:'center',behavior:'smooth'})}if(r){r.classList.add('current');r.scrollIntoView({block:'center',behavior:'smooth'})}cur=i}
if(i>=0){let s=t.segments[i],p=Math.max(0,Math.min(1,(now-s.start)/Math.max(.05,s.end-s.start))),el=full.querySelector(`[data-i="${i}"]`);if(el){let txt=s.text||'',n=Math.floor(txt.length*p);el.innerHTML=`<span class="done">${esc(txt.slice(0,n))}</span>${esc(txt.slice(n))} `}}
requestAnimationFrame(tick)}
active.onchange=render;compare.onchange=render;render();tick();
</script></body></html>'''


def export_html_package(out_dir: str, audio_path: str, tracks: list[TextTrack]) -> Path:
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    audio = Path(audio_path)
    audio_name = audio.name
    dst_audio = out / audio_name
    if audio.exists() and audio.resolve() != dst_audio.resolve():
        shutil.copy2(audio, dst_audio)
    data = {"format":"JunbaKTV/1", "tracks":[t.to_dict() for t in tracks]}
    html = HTML_TEMPLATE.replace("__AUDIO__", _html.escape(audio_name, quote=True)).replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    html_path = out / "峻爸_KTV_多文字軌核對.html"
    html_path.write_text(html, encoding="utf-8")
    for i, tr in enumerate(tracks, 1):
        safe = "".join(c if c not in '\\/:*?\"<>|' else '_' for c in tr.name) or f"track{i}"
        (out / f"{i:02d}_{safe}.vtt").write_text(to_vtt(tr), encoding="utf-8")
    return html_path
