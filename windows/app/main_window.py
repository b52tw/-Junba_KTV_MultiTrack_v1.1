from __future__ import annotations
import bisect
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QSettings, QThread, Signal
from PySide6.QtGui import QColor, QDesktopServices, QTextCharFormat, QTextCursor
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSlider, QSplitter,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget
)

from .alignment import align_untimed_to_base, align_untimed_to_duration
from .formats import load_track, fmt_time, to_srt, to_vtt
from .gemini_service import polish_track, transcribe_audio_for_review
from .html_export import export_html_package
from .models import TextTrack
from .project import load_project, save_project
from .review import compare_tracks

AUDIO_FILTER = "音訊 (*.m4a *.mp3 *.wav *.aac *.flac *.ogg *.wma *.mp4);;所有檔案 (*.*)"
TRACK_FILTER = "逐字稿/字幕 (*.srt *.vtt *.txt *.json *.csv *.docx *.html *.htm);;所有檔案 (*.*)"


class JobThread(QThread):
    status = Signal(str)
    done = Signal(object)
    failed = Signal(str)
    def __init__(self, fn, parent=None):
        super().__init__(parent); self.fn = fn
    def run(self):
        try:
            self.done.emit(self.fn(lambda s: self.status.emit(str(s))))
        except Exception as e:
            self.failed.emit(f"{type(e).__name__}: {e}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("峻爸 KTV 多文字軌核對器 v1.1｜智慧核對版")
        self.resize(1380, 900)
        self.audio_path = ""
        self.tracks: list[TextTrack] = []
        self._ranges = []
        self._last_index = -1
        self._review = []
        self._job: JobThread | None = None
        self.settings = QSettings("Junba", "JunbaKTVMultiTrack")

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.audio.setVolume(0.9)
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(self._state_changed)
        self.player.errorOccurred.connect(self._player_error)

        root = QWidget(); self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        g_audio = QGroupBox("1. 錄音檔")
        la = QHBoxLayout(g_audio)
        self.audio_label = QLabel("尚未選擇錄音檔"); self.audio_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        b_audio = QPushButton("選擇錄音檔"); b_audio.clicked.connect(self.choose_audio)
        la.addWidget(self.audio_label, 1); la.addWidget(b_audio)
        layout.addWidget(g_audio)

        g_tracks = QGroupBox("2. 多文字軌（本程式或其他軟體輸出的逐字稿／翻譯稿）")
        lt = QVBoxLayout(g_tracks)
        top = QHBoxLayout()
        for text, cb in [("加入文字/字幕", self.add_tracks), ("移除選取", self.remove_track), ("自動對齊未定時文字", self.align_tracks)]:
            b=QPushButton(text); b.clicked.connect(cb); top.addWidget(b)
        top.addStretch(1)
        lt.addLayout(top)
        self.track_table = QTableWidget(0, 5)
        self.track_table.setHorizontalHeaderLabels(["名稱", "格式", "時間軸", "對齊精度", "來源"])
        self.track_table.horizontalHeader().setStretchLastSection(True)
        self.track_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.track_table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.track_table.itemChanged.connect(self._track_item_changed)
        lt.addWidget(self.track_table)
        layout.addWidget(g_tracks)

        ctrl = QHBoxLayout()
        self.play_btn = QPushButton("▶ 播放"); self.play_btn.clicked.connect(self.play_audio)
        self.pause_btn = QPushButton("⏸ 暫停"); self.pause_btn.clicked.connect(self.player.pause)
        self.stop_btn = QPushButton("⏹ 停止"); self.stop_btn.clicked.connect(self.stop_audio)
        back = QPushButton("↶ 5秒"); back.clicked.connect(lambda: self.seek_delta(-5000))
        fwd = QPushButton("5秒 ↷"); fwd.clicked.connect(lambda: self.seek_delta(5000))
        self.pos_label = QLabel("00:00:00 / 00:00:00")
        self.slider = QSlider(Qt.Horizontal); self.slider.setRange(0, 0); self.slider.sliderMoved.connect(self.player.setPosition)
        self.speed = QComboBox(); self.speed.addItems(["0.75x","1.0x","1.25x","1.5x","2.0x"]); self.speed.setCurrentText("1.0x"); self.speed.currentTextChanged.connect(self._speed_changed)
        for w in [self.play_btn,self.pause_btn,self.stop_btn,back,fwd,self.pos_label]: ctrl.addWidget(w)
        ctrl.addWidget(self.slider, 1); ctrl.addWidget(QLabel("速度")); ctrl.addWidget(self.speed)
        layout.addLayout(ctrl)

        sel = QHBoxLayout()
        self.active_combo = QComboBox(); self.active_combo.currentIndexChanged.connect(self.rebuild_views)
        self.compare_combo = QComboBox(); self.compare_combo.currentIndexChanged.connect(self.rebuild_views)
        sel.addWidget(QLabel("上方 KTV 文字軌")); sel.addWidget(self.active_combo, 1)
        sel.addWidget(QLabel("核對／比較文字軌")); sel.addWidget(self.compare_combo, 1)
        self.review_summary = QLabel("尚未選擇比較軌")
        sel.addWidget(self.review_summary)
        layout.addLayout(sel)

        splitter = QSplitter(Qt.Vertical)
        self.full_text = QTextEdit(); self.full_text.setReadOnly(True); self.full_text.setPlaceholderText("完整全文會顯示在這裡；播放時目前句段會像 KTV 一樣反白。")
        self.full_text.setStyleSheet("QTextEdit { font-size: 18px; line-height: 1.7; }")
        splitter.addWidget(self.full_text)
        self.timeline = QTableWidget(0, 6)
        self.timeline.setHorizontalHeaderLabels(["開始", "結束", "講者", "目前文字軌", "比較文字軌", "核對結果"])
        self.timeline.horizontalHeader().setStretchLastSection(True)
        self.timeline.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.timeline.cellDoubleClicked.connect(self._timeline_seek)
        splitter.addWidget(self.timeline); splitter.setSizes([360, 320])
        layout.addWidget(splitter, 1)

        g_ai = QGroupBox("3. Gemini 智慧功能（可選；只有『聽錄音核對』會上傳音訊）")
        gai = QVBoxLayout(g_ai)
        row1 = QHBoxLayout()
        self.api_key = QLineEdit(str(self.settings.value("gemini_api_key", ""))); self.api_key.setEchoMode(QLineEdit.Password); self.api_key.setPlaceholderText("Google AI Studio API Key")
        self.show_key = QCheckBox("顯示 Key"); self.show_key.toggled.connect(lambda on: self.api_key.setEchoMode(QLineEdit.Normal if on else QLineEdit.Password))
        save_key = QPushButton("儲存 Key"); save_key.clicked.connect(self.save_api_key)
        ai_studio = QPushButton("前往 AI Studio"); ai_studio.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://aistudio.google.com/apikey")))
        self.model_combo = QComboBox(); self.model_combo.addItems(["gemini-3.8-flash","gemini-3.7-flash","gemini-3.6-flash"])
        row1.addWidget(QLabel("API Key")); row1.addWidget(self.api_key,1); row1.addWidget(self.show_key); row1.addWidget(save_key); row1.addWidget(ai_studio); row1.addWidget(QLabel("模型")); row1.addWidget(self.model_combo)
        gai.addLayout(row1)
        row2 = QHBoxLayout()
        polish = QPushButton("✨ Gemini 順稿（保留時間軸）"); polish.clicked.connect(self.gemini_polish)
        smart = QPushButton("🎧 Gemini 聽錄音建立核對軌／多人講者"); smart.clicked.connect(self.gemini_audio_review)
        diff = QPushButton("🔎 比對目前兩個文字軌"); diff.clicked.connect(self.rebuild_views)
        self.ai_status = QLabel("待命")
        row2.addWidget(polish); row2.addWidget(smart); row2.addWidget(diff); row2.addWidget(self.ai_status,1)
        gai.addLayout(row2)
        hint = QLabel("提示：若『比較文字軌』選 Gemini 智慧核對軌，紅／黃標示可視為『錄音內容 vs 原文字稿』的疑似差異。Gemini 只辨識講者編號，不猜真實姓名。")
        hint.setWordWrap(True); gai.addWidget(hint)
        layout.addWidget(g_ai)

        foot = QHBoxLayout()
        for text, cb in [("開啟專案", self.open_project), ("儲存專案", self.save_project), ("匯出目前軌 SRT", lambda: self.export_track("srt")), ("匯出目前軌 VTT", lambda: self.export_track("vtt")), ("產生離線 KTV 網頁包", self.export_html)]:
            b=QPushButton(text); b.clicked.connect(cb); foot.addWidget(b)
        foot.addStretch(1); layout.addLayout(foot)

    def choose_audio(self):
        p, _ = QFileDialog.getOpenFileName(self, "選擇錄音檔", "", AUDIO_FILTER)
        if not p: return
        self.audio_path = p; self.audio_label.setText(p); self.player.setSource(QUrl.fromLocalFile(p))

    def add_tracks(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "加入文字/字幕", "", TRACK_FILTER)
        for p in paths:
            try: self.tracks.append(load_track(p))
            except Exception as e: QMessageBox.warning(self, "讀取失敗", f"{Path(p).name}\n{e}")
        self.refresh_tracks(); self.align_tracks(auto_only=True)

    def remove_track(self):
        rows = sorted({x.row() for x in self.track_table.selectedItems()}, reverse=True)
        for r in rows:
            if 0 <= r < len(self.tracks): self.tracks.pop(r)
        self.refresh_tracks()

    def refresh_tracks(self):
        self.track_table.blockSignals(True); self.track_table.setRowCount(len(self.tracks))
        for r,t in enumerate(self.tracks):
            vals=[t.name,t.format_name,"有" if t.timed else "無","估算" if t.estimated else "原始時間碼",t.source_path]
            for c,v in enumerate(vals): self.track_table.setItem(r,c,QTableWidgetItem(v))
        self.track_table.blockSignals(False)
        active = self.active_combo.currentIndex(); comp = self.compare_combo.currentIndex()-1
        self.active_combo.blockSignals(True); self.compare_combo.blockSignals(True)
        self.active_combo.clear(); self.compare_combo.clear(); self.compare_combo.addItem("不比較")
        for t in self.tracks:
            suffix="（估算）" if t.estimated else ""
            self.active_combo.addItem(t.name+suffix); self.compare_combo.addItem(t.name+suffix)
        if self.tracks: self.active_combo.setCurrentIndex(min(max(active,0),len(self.tracks)-1))
        if comp >= 0: self.compare_combo.setCurrentIndex(min(comp+1,len(self.tracks)))
        self.active_combo.blockSignals(False); self.compare_combo.blockSignals(False); self.rebuild_views()

    def _track_item_changed(self, item):
        if item.column()==0 and 0<=item.row()<len(self.tracks):
            self.tracks[item.row()].name=item.text().strip() or self.tracks[item.row()].name; self.refresh_tracks()

    def _base_track(self):
        return next((t for t in self.tracks if t.timed and not t.estimated and t.segments), next((t for t in self.tracks if t.timed and t.segments), None))

    def align_tracks(self, auto_only=False):
        if not self.tracks: return
        base = self._base_track(); duration = self.player.duration()/1000.0 if self.player.duration()>0 else 0.0; changed=False
        for i,t in enumerate(list(self.tracks)):
            if t.timed: continue
            if base and base is not t: self.tracks[i]=align_untimed_to_base(t,base); changed=True
            elif duration>0: self.tracks[i]=align_untimed_to_duration(t,duration); changed=True
        if changed: self.refresh_tracks()
        elif not auto_only: QMessageBox.information(self,"對齊","目前沒有需要對齊的未定時文字，或尚未載入可用時間軸/音訊長度。")

    def rebuild_views(self):
        self._ranges=[]; self._last_index=-1; self._review=[]
        if not self.tracks or self.active_combo.currentIndex()<0:
            self.full_text.clear(); self.timeline.setRowCount(0); self.review_summary.setText("尚未選擇文字軌"); return
        tr=self.tracks[self.active_combo.currentIndex()]
        self.full_text.clear(); cur=self.full_text.textCursor()
        for s in tr.segments:
            start=cur.position(); cur.insertText(s.text.strip()+" "); end=cur.position(); self._ranges.append((start,end))
        self.full_text.setTextCursor(QTextCursor(self.full_text.document()))
        comp_idx=self.compare_combo.currentIndex()-1; comp=self.tracks[comp_idx] if 0<=comp_idx<len(self.tracks) else None
        if comp: self._review=compare_tracks(tr,comp)
        self.timeline.setRowCount(len(tr.segments)); counts={'green':0,'yellow':0,'red':0}
        for r,s in enumerate(tr.segments):
            other=""; status="—"; level=""
            if comp and r < len(self._review):
                rr=self._review[r]; other=rr.other_text; level=rr.level; counts[level]+=1; status=f"{rr.score*100:.0f}%｜{rr.note}"
            vals=[fmt_time(s.start)[:8],fmt_time(s.end)[:8],s.speaker,s.text,other,status]
            for c,v in enumerate(vals):
                it=QTableWidgetItem(v); it.setData(Qt.UserRole,s.start)
                if level=='green': it.setBackground(QColor('#173b23'))
                elif level=='yellow': it.setBackground(QColor('#5a4900'))
                elif level=='red': it.setBackground(QColor('#5a1d1d'))
                self.timeline.setItem(r,c,it)
        if comp: self.review_summary.setText(f"核對：綠 {counts['green']}｜黃 {counts['yellow']}｜紅 {counts['red']}")
        else: self.review_summary.setText("未選比較軌")
        self.timeline.resizeColumnsToContents(); self.timeline.horizontalHeader().setStretchLastSection(True); self._position_changed(self.player.position())

    def play_audio(self):
        if not self.audio_path: QMessageBox.information(self,"尚未選擇音訊","請先選擇錄音檔。"); return
        self.player.play()
    def stop_audio(self): self.player.stop(); self.player.setPosition(0)
    def seek_delta(self, ms): self.player.setPosition(max(0,min(self.player.duration(),self.player.position()+ms)))
    def _state_changed(self,state):
        self.play_btn.setEnabled(state!=QMediaPlayer.PlayingState); self.pause_btn.setEnabled(state==QMediaPlayer.PlayingState)
    def _duration_changed(self,d): self.slider.setRange(0,max(0,d)); self.align_tracks(auto_only=True)
    def _speed_changed(self,s): self.player.setPlaybackRate(float(s.rstrip('x')))
    def _player_error(self,*_):
        if self.player.error()!=QMediaPlayer.NoError: self.statusBar().showMessage("播放器無法直接開啟此音訊格式；可先轉 WAV/MP3 後再載入。",10000)

    def _position_changed(self,ms):
        self.slider.blockSignals(True); self.slider.setValue(ms); self.slider.blockSignals(False)
        self.pos_label.setText(f"{fmt_time(ms/1000)[:8]} / {fmt_time(self.player.duration()/1000)[:8]}")
        if not self.tracks or self.active_combo.currentIndex()<0: return
        tr=self.tracks[self.active_combo.currentIndex()]; now=ms/1000.0; starts=[s.start for s in tr.segments]; i=bisect.bisect_right(starts,now)-1
        if i<0 or i>=len(tr.segments): return
        seg=tr.segments[i]
        if seg.end>seg.start and now>seg.end and i+1<len(tr.segments): return
        self._highlight(i,now)

    def _highlight(self,i,now):
        if i>=len(self._ranges): return
        start,end=self._ranges[i]; seg=self.tracks[self.active_combo.currentIndex()].segments[i]
        p=max(0.0,min(1.0,(now-seg.start)/max(.08,seg.end-seg.start))) if seg.end>seg.start else 1.0; mid=start+int((end-start)*p); sels=[]
        c=QTextCursor(self.full_text.document()); c.setPosition(start); c.setPosition(end,QTextCursor.KeepAnchor)
        s=self.full_text.ExtraSelection(); s.cursor=c; f=QTextCharFormat(); f.setBackground(QColor("#665500")); s.format=f; sels.append(s)
        c2=QTextCursor(self.full_text.document()); c2.setPosition(start); c2.setPosition(mid,QTextCursor.KeepAnchor)
        s2=self.full_text.ExtraSelection(); s2.cursor=c2; f2=QTextCharFormat(); f2.setBackground(QColor("#ffd54f")); f2.setForeground(QColor("#111111")); s2.format=f2; sels.append(s2)
        self.full_text.setExtraSelections(sels)
        if i!=self._last_index:
            self.timeline.selectRow(i); self.timeline.scrollToItem(self.timeline.item(i,0),QAbstractItemView.PositionAtCenter)
            c3=QTextCursor(self.full_text.document()); c3.setPosition(start); self.full_text.setTextCursor(c3); self.full_text.ensureCursorVisible(); self._last_index=i

    def _timeline_seek(self,row,col):
        it=self.timeline.item(row,0)
        if it: self.player.setPosition(int(float(it.data(Qt.UserRole) or 0)*1000)); self.player.play()

    def save_api_key(self):
        self.settings.setValue("gemini_api_key", self.api_key.text().strip()); QMessageBox.information(self,"完成","API Key 已儲存在本機使用者設定，不會寫入 EXE。")

    def _start_job(self, label, fn, done):
        if self._job and self._job.isRunning(): QMessageBox.information(self,"工作進行中","請等待目前 Gemini 工作完成。"); return
        self.ai_status.setText(label); self._job=JobThread(fn,self); self._job.status.connect(self.ai_status.setText)
        self._job.failed.connect(lambda e: (self.ai_status.setText("失敗"), QMessageBox.critical(self,"Gemini 工作失敗",e)))
        self._job.done.connect(lambda obj: (self.ai_status.setText("完成"), done(obj)))
        self._job.start()

    def gemini_polish(self):
        if not self.tracks or self.active_combo.currentIndex()<0: QMessageBox.information(self,"沒有文字軌","請先加入文字軌。"); return
        tr=self.tracks[self.active_combo.currentIndex()]; key=self.api_key.text().strip(); model=self.model_combo.currentText()
        self._start_job("Gemini 順稿中…", lambda cb: polish_track(tr,key,model,progress=cb), self._add_polished)
    def _add_polished(self,tr):
        self.tracks.append(tr); self.refresh_tracks(); self.active_combo.setCurrentIndex(len(self.tracks)-1)

    def gemini_audio_review(self):
        if not self.audio_path: QMessageBox.information(self,"沒有錄音","請先選擇錄音檔。"); return
        yes=QMessageBox.question(self,"確認上傳音訊","此功能會將目前錄音檔上傳到 Google Gemini，用於講者分段、時間軸與核對。\n\n要繼續嗎？",QMessageBox.Yes|QMessageBox.No)
        if yes!=QMessageBox.Yes: return
        key=self.api_key.text().strip(); model=self.model_combo.currentText()
        self._start_job("Gemini 聽錄音中…", lambda cb: transcribe_audio_for_review(self.audio_path,key,model,progress=cb), self._add_review_track)
    def _add_review_track(self,tr):
        self.tracks.append(tr); self.refresh_tracks()
        # Keep user's existing transcript active and set Gemini as comparison; if no previous track, make Gemini active.
        if len(self.tracks)>=2:
            self.compare_combo.setCurrentIndex(len(self.tracks))
        else: self.active_combo.setCurrentIndex(0)
        self.rebuild_views()

    def save_project(self):
        p,_=QFileDialog.getSaveFileName(self,"儲存 KTV 專案","峻爸_KTV專案.jktv","峻爸 KTV 專案 (*.jktv)")
        if p: save_project(p,self.audio_path,self.tracks,self.active_combo.currentIndex(),self.compare_combo.currentIndex()-1)
    def open_project(self):
        p,_=QFileDialog.getOpenFileName(self,"開啟 KTV 專案","","峻爸 KTV 專案 (*.jktv)")
        if not p:return
        try:
            audio,tracks,a,c=load_project(p); self.audio_path=audio; self.tracks=tracks; self.audio_label.setText(audio or "尚未指定錄音檔")
            if audio and Path(audio).exists(): self.player.setSource(QUrl.fromLocalFile(audio))
            self.refresh_tracks();
            if tracks: self.active_combo.setCurrentIndex(max(0,min(a,len(tracks)-1)))
            self.compare_combo.setCurrentIndex(c+1 if 0<=c<len(tracks) else 0)
        except Exception as e: QMessageBox.critical(self,"專案讀取失敗",str(e))

    def export_track(self,kind):
        if not self.tracks or self.active_combo.currentIndex()<0:return
        tr=self.tracks[self.active_combo.currentIndex()]; ext=kind.lower(); p,_=QFileDialog.getSaveFileName(self,"匯出文字軌",f"{tr.name}.{ext}",f"{ext.upper()} (*.{ext})")
        if p: Path(p).write_text(to_srt(tr) if ext=="srt" else to_vtt(tr),encoding="utf-8")

    def export_html(self):
        if not self.audio_path or not self.tracks: QMessageBox.information(self,"資料不足","請先選擇錄音檔並加入至少一個文字軌。"); return
        out=QFileDialog.getExistingDirectory(self,"選擇 KTV 網頁包輸出資料夾")
        if not out:return
        try:
            p=export_html_package(out,self.audio_path,self.tracks); QMessageBox.information(self,"完成",f"已建立離線核對網頁：\n{p}")
            if sys.platform.startswith("win"): os.startfile(str(p))
            else: subprocess.Popen(["xdg-open",str(p)])
        except Exception as e: QMessageBox.critical(self,"匯出失敗",str(e))
