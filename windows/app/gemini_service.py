from __future__ import annotations
import json, re, time
from pathlib import Path
from typing import Callable

from .models import Segment, TextTrack

DEFAULT_TEXT_MODEL = 'gemini-3.8-flash'


def _json_from_text(text: str):
    raw = (text or '').strip()
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.I)
    raw = re.sub(r'\s*```$', '', raw)
    a, b = raw.find('['), raw.rfind(']')
    if a >= 0 and b > a:
        raw = raw[a:b+1]
    return json.loads(raw)


def _client(api_key: str):
    if not api_key.strip():
        raise RuntimeError('請先輸入 Gemini API Key。')
    from google import genai
    return genai.Client(api_key=api_key.strip())


def polish_track(track: TextTrack, api_key: str, model: str = DEFAULT_TEXT_MODEL,
                 style: str = '繁體台灣用語、保留原意、修正錯字與口語贅詞',
                 progress: Callable[[str], None] | None = None) -> TextTrack:
    client = _client(api_key)
    segs: list[Segment] = []
    batch = 24
    for offset in range(0, len(track.segments), batch):
        part = track.segments[offset:offset+batch]
        if progress: progress(f'Gemini 順稿 {offset+1}–{offset+len(part)} / {len(track.segments)}')
        payload = [{'id': i, 'speaker': s.speaker, 'text': s.text} for i, s in enumerate(part)]
        prompt = (
            '你是繁體中文會議逐字稿校稿助理。請只回傳 JSON 陣列，不要 markdown。\n'
            f'規則：{style}。不得新增原錄音沒有的事實；專有名詞不確定就保留原文；每個 id 必須保留。\n'
            '輸入：' + json.dumps(payload, ensure_ascii=False)
        )
        resp = client.models.generate_content(model=model, contents=prompt)
        arr = _json_from_text(getattr(resp, 'text', '') or '')
        mapping = {int(x.get('id', -1)): str(x.get('text', '')).strip() for x in arr if isinstance(x, dict)}
        for i, s in enumerate(part):
            txt = mapping.get(i, s.text) or s.text
            segs.append(Segment(s.start, s.end, txt, s.speaker, s.estimated))
    return TextTrack(track.name + '｜Gemini順稿', segs, '', 'Gemini', track.timed, track.estimated)


def transcribe_audio_for_review(audio_path: str, api_key: str, model: str = DEFAULT_TEXT_MODEL,
                                progress: Callable[[str], None] | None = None) -> TextTrack:
    client = _client(api_key)
    p = Path(audio_path)
    if not p.exists(): raise RuntimeError('錄音檔不存在。')
    if progress: progress('上傳錄音至 Gemini（只有啟用智慧核對時才會上傳）…')
    f = client.files.upload(file=str(p))
    # Some files need processing before use.
    for _ in range(120):
        state = str(getattr(getattr(f, 'state', None), 'name', getattr(f, 'state', ''))).upper()
        if 'FAILED' in state:
            raise RuntimeError('Gemini 音檔處理失敗。')
        if not state or 'ACTIVE' in state or 'READY' in state:
            break
        time.sleep(1)
        try: f = client.files.get(name=f.name)
        except Exception: break
    if progress: progress('Gemini 正在辨識講者、時間與逐字內容…')
    prompt = '''
請完整聽這段錄音，建立「核對用逐字稿」。
要求：
1. 請辨識不同說話者，以「講者1、講者2…」標示；若無法確定真實姓名，不要猜姓名。
2. 每段需有 start、end（秒數，可含小數）、speaker、text。
3. 保留中文、台語、英文、日文原意；中文輸出使用繁體中文（台灣用語）。
4. 只輸出 JSON 陣列，不要 markdown，不要解釋。
格式：[{"start":0.0,"end":3.2,"speaker":"講者1","text":"..."}]
'''
    resp = client.models.generate_content(model=model, contents=[f, prompt])
    arr = _json_from_text(getattr(resp, 'text', '') or '')
    segs=[]
    for x in arr:
        if not isinstance(x, dict): continue
        txt=str(x.get('text','')).strip()
        if not txt: continue
        start=float(x.get('start',0) or 0); end=float(x.get('end',start) or start)
        segs.append(Segment(start, max(start,end), txt, str(x.get('speaker','')).strip(), False))
    if not segs: raise RuntimeError('Gemini 沒有回傳可用的時間軸逐字稿。')
    return TextTrack(p.stem+'｜Gemini智慧核對', segs, str(p), 'Gemini Audio', True, False)
