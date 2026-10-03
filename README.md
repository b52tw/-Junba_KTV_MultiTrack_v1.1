# 峻爸 KTV 多文字軌核對器 v1.1｜Windows Single EXE + Android APK

這是一支**獨立於「峻爸 AI Transcriber」**的核對／學習工具。它不修改原本語音轉文字程式，也不依賴其輸出流程。

## 這版產出
GitHub Actions 一次產出兩個 Artifact：

1. `Junba-KTV-MultiTrack-v1.1-Single-EXE-Windows-x64`
   - Windows 10/11 單一 EXE 版
   - **不再產 Portable**
2. `Junba-KTV-MultiTrack-v1.1-Android-APK`
   - Android APK
   - 未設定 Android release keystore 時，自動產生可安裝的 debug APK
   - 有設定 keystore Secrets 時，改產正式簽署 release APK

## Windows / Android 共通功能
- 選擇錄音檔並播放
- **播放 / 暫停 / 停止** 分開按鈕
- ±5 秒、0.75x～2.0x
- 上方完整全文 KTV 同步反白
- 下方時間軸逐句核對
- 多文字軌：原始稿、翻譯稿、AI 順稿、Gemini 核對軌可互相比較
- SRT / VTT / TXT / JSON
- Windows 另支援 CSV / DOCX / HTML
- Android 支援 DOCX 基本讀取（含本程式時間軸表格的常見格式）
- 沒有時間碼的文字可依既有時間軸或音訊長度估算對齊
- 文字軌差異標示：
  - 綠色：高度吻合
  - 黃色：建議人工核對
  - 紅色：疑似漏字、錯字或內容不一致

## 多人會議／講者
若匯入的 SRT/VTT/DOCX 已含講者標籤，會直接顯示。

另可選擇「Gemini 聽錄音建立核對軌／多人講者」：
- 會將錄音上傳 Google Gemini
- 產生新的時間軸文字軌
- 講者只標記為「講者1、講者2…」，不猜真實姓名
- 將此軌選為「比較軌」後，即可把原文字稿與 Gemini 從錄音聽到的結果做差異提示

> 其他一般播放、KTV 反白、文字軌互相比對都不會上傳音訊。

## Gemini 順稿
「Gemini 順稿」只送文字，不送錄音，並建立**新的文字軌**：
- 保留原始時間軸
- 使用繁體中文／台灣用語
- 修正錯字、贅詞與閱讀性
- 原文字軌不會被覆蓋

預設模型選單：`gemini-3.8-flash / 3.7-flash / 3.6-flash`。

## GitHub 使用
把 ZIP 內容直接放在 Repository 根目錄，確認：

```text
.github/workflows/build-windows-android-v1.1.yml
windows/
android/
README.md
```

進入 GitHub → Actions → `Build Junba KTV v1.1 Windows Single + Android APK` → Run workflow。

### Windows 簽章（選用）
設定 Secrets：
- `WINDOWS_CERT_PFX_BASE64`
- `WINDOWS_CERT_PASSWORD`

### Android 正式 APK 簽章（選用）
設定 Secrets：
- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

未設定 Android keystore 時，Workflow 會產生 debug APK，仍可手動安裝測試。

## API Key
API Key 不寫死在程式碼或 APK。Windows 與 Android 都由使用者自行輸入。
