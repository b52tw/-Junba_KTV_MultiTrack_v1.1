package tw.junba.ktvmultitrack

import android.app.*
import android.content.*
import android.graphics.Color
import android.media.MediaPlayer
import android.net.Uri
import android.os.*
import android.text.Spannable
import android.text.SpannableStringBuilder
import android.text.style.BackgroundColorSpan
import android.text.style.ForegroundColorSpan
import android.view.*
import android.widget.*
import java.io.File

class MainActivity : Activity() {
    private val tracks = mutableListOf<TextTrack>()
    private var audioUri: Uri? = null
    private var player: MediaPlayer? = null
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var fullText: TextView
    private lateinit var fullScroll: ScrollView
    private lateinit var timeline: ListView
    private lateinit var activeSpinner: Spinner
    private lateinit var compareSpinner: Spinner
    private lateinit var seek: SeekBar
    private lateinit var timeLabel: TextView
    private lateinit var summary: TextView
    private lateinit var audioLabel: TextView
    private lateinit var apiKey: EditText
    private lateinit var modelSpinner: Spinner
    private lateinit var status: TextView
    private var ranges = mutableListOf<Pair<Int,Int>>()
    private var review = listOf<ReviewResult>()
    private var currentIndex = -1
    private val prefs by lazy { getSharedPreferences("junba_ktv", MODE_PRIVATE) }

    companion object { const val REQ_AUDIO=101; const val REQ_TRACK=102 }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        title="峻爸 KTV 多文字軌核對器 v1.1"
        setContentView(buildUi())
        handler.post(ticker)
    }

    private fun buildUi(): View {
        val root=LinearLayout(this).apply{orientation=LinearLayout.VERTICAL;setPadding(18,18,18,18)}
        fun button(t:String, f:()->Unit)=Button(this).apply{text=t;setOnClickListener{f()}}
        val title=TextView(this).apply{text="峻爸 KTV 多文字軌核對器 v1.1｜Android";textSize=22f;setTextColor(Color.rgb(25,80,150));setPadding(0,0,0,12)};root.addView(title)
        val arow=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL}
        audioLabel=TextView(this).apply{text="尚未選擇錄音檔";layoutParams=LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f)}
        arow.addView(audioLabel);arow.addView(button("選擇錄音"){openAudio()});arow.addView(button("加入文字/字幕"){openTrack()});root.addView(arow)

        val prow=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL}
        prow.addView(button("▶ 播放"){play()});prow.addView(button("⏸ 暫停"){player?.pause()});prow.addView(button("⏹ 停止"){player?.pause();player?.seekTo(0);updateViews()});prow.addView(button("↶5秒"){seekDelta(-5000)});prow.addView(button("5秒↷"){seekDelta(5000)})
        timeLabel=TextView(this).apply{text="00:00:00 / 00:00:00";gravity=Gravity.CENTER_VERTICAL;setPadding(10,0,10,0)};prow.addView(timeLabel)
        val sp=Spinner(this);sp.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,listOf("0.75x","1.0x","1.25x","1.5x","2.0x"));sp.setSelection(1);sp.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onNothingSelected(p:android.widget.AdapterView<*>?){ };override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){if(Build.VERSION.SDK_INT>=23) player?.let { mp -> val pp=mp.playbackParams; pp.speed=listOf(.75f,1f,1.25f,1.5f,2f)[pos]; mp.playbackParams=pp }}};prow.addView(sp)
        root.addView(prow)
        seek=SeekBar(this);seek.max=1000;seek.setOnSeekBarChangeListener(object:SeekBar.OnSeekBarChangeListener{override fun onProgressChanged(s:SeekBar?,p:Int,from:Boolean){if(from){val d=player?.duration?:0;if(d>0)player?.seekTo((d*p/1000.0).toInt())}};override fun onStartTrackingTouch(s:SeekBar?){ };override fun onStopTrackingTouch(s:SeekBar?){ }});root.addView(seek)

        val srow=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL}
        activeSpinner=Spinner(this);compareSpinner=Spinner(this);summary=TextView(this).apply{setPadding(10,0,0,0)}
        srow.addView(TextView(this).apply{text="KTV文字軌"});srow.addView(activeSpinner,LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f));srow.addView(TextView(this).apply{text="比較軌"});srow.addView(compareSpinner,LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f));srow.addView(summary)
        root.addView(srow)
        val listener=object:android.widget.AdapterView.OnItemSelectedListener{override fun onNothingSelected(p:android.widget.AdapterView<*>?){ };override fun onItemSelected(p:android.widget.AdapterView<*>?,v:View?,pos:Int,id:Long){rebuild()}}
        activeSpinner.onItemSelectedListener=listener;compareSpinner.onItemSelectedListener=listener

        fullText=TextView(this).apply{textSize=19f;setTextColor(Color.DKGRAY);setPadding(12,12,12,12);setTextIsSelectable(true)}
        fullScroll=ScrollView(this).apply{addView(fullText);layoutParams=LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,0.38f)};root.addView(fullScroll)
        timeline=ListView(this).apply{dividerHeight=1;layoutParams=LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,0,0.42f)};root.addView(timeline)
        timeline.setOnItemClickListener{_,_,pos,_->val t=activeTrack()?:return@setOnItemClickListener;player?.seekTo((t.segments[pos].start*1000).toInt());play()}

        val grow=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL}
        apiKey=EditText(this).apply{hint="Gemini API Key";setSingleLine(true);inputType=android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_PASSWORD;setText(prefs.getString("api_key","")?:"");layoutParams=LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f)};grow.addView(apiKey)
        modelSpinner=Spinner(this);modelSpinner.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,listOf("gemini-3.8-flash","gemini-3.7-flash","gemini-3.6-flash"));grow.addView(modelSpinner)
        grow.addView(button("儲存Key"){prefs.edit().putString("api_key",apiKey.text.toString().trim()).apply();toast("已儲存在本機 App 設定")});root.addView(grow)
        val grow2=LinearLayout(this).apply{orientation=LinearLayout.HORIZONTAL}
        grow2.addView(button("✨ Gemini順稿"){geminiPolish()});grow2.addView(button("🎧 Gemini聽錄音核對/多人講者"){confirmAudioGemini()});grow2.addView(button("🔎 重新比對"){rebuild()});status=TextView(this).apply{text="待命";setPadding(12,0,0,0)};grow2.addView(status,LinearLayout.LayoutParams(0,ViewGroup.LayoutParams.WRAP_CONTENT,1f));root.addView(grow2)
        root.addView(TextView(this).apply{text="紅色＝疑似不一致；黃色＝建議人工核對；綠色＝高度吻合。若比較軌是 Gemini 智慧核對軌，即為錄音內容 vs 文字稿的比對。";textSize=13f;setPadding(0,8,0,0)})
        return root
    }

    private fun openAudio(){startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply{addCategory(Intent.CATEGORY_OPENABLE);type="audio/*"},REQ_AUDIO)}
    private fun openTrack(){startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply{addCategory(Intent.CATEGORY_OPENABLE);type="*/*";putExtra(Intent.EXTRA_ALLOW_MULTIPLE,true)},REQ_TRACK)}
    override fun onActivityResult(req:Int,res:Int,data:Intent?){super.onActivityResult(req,res,data);if(res!=RESULT_OK||data==null)return
        if(req==REQ_AUDIO){data.data?.let{u->audioUri=u;contentResolver.takePersistableUriPermission(u,Intent.FLAG_GRANT_READ_URI_PERMISSION);audioLabel.text=TrackParser.displayName(contentResolver,u);preparePlayer(u)}}
        if(req==REQ_TRACK){val uris=mutableListOf<Uri>();data.clipData?.let{for(i in 0 until it.itemCount)uris+=it.getItemAt(i).uri}?:data.data?.let{uris+=it};uris.forEach{u->try{contentResolver.takePersistableUriPermission(u,Intent.FLAG_GRANT_READ_URI_PERMISSION)}catch(_:Exception){};try{tracks+=TrackParser.load(contentResolver,u)}catch(e:Exception){toast("讀取失敗：${e.message}")}};autoAlign();refreshSpinners()}
    }
    private fun preparePlayer(u:Uri){player?.release();player=MediaPlayer().apply{setDataSource(this@MainActivity,u);setOnPreparedListener{autoAlign();updateViews()};setOnErrorListener{_,_,_->toast("音訊無法播放");true};prepareAsync()}}
    private fun play(){val p=player;if(p==null){toast("請先選擇錄音");return};p.start()}
    private fun seekDelta(ms:Int){player?.let{it.seekTo((it.currentPosition+ms).coerceIn(0,it.duration))}}
    private fun activeTrack():TextTrack?=tracks.getOrNull(activeSpinner.selectedItemPosition)
    private fun compareTrack():TextTrack?{val i=compareSpinner.selectedItemPosition-1;return tracks.getOrNull(i)}
    private fun refreshSpinners(){val names=tracks.map{it.name+(if(it.estimated)"（估算）" else "")};activeSpinner.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,names);compareSpinner.adapter=ArrayAdapter(this,android.R.layout.simple_spinner_dropdown_item,listOf("不比較")+names);if(tracks.isNotEmpty())activeSpinner.setSelection(0);rebuild()}
    private fun autoAlign(){val d=(player?.duration?:0)/1000.0;if(d<=0)return;val base=tracks.firstOrNull{it.timed&&it.segments.isNotEmpty()};tracks.forEach{t->if(!t.timed&&t.segments.isNotEmpty()){val texts=t.segments.map{it.text};if(base!=null){val joined=texts.joinToString(" ");val n=base.segments.size;val step=(joined.length.toDouble()/n).coerceAtLeast(1.0);val ns=mutableListOf<Segment>();for(i in 0 until n){val a=(i*step).toInt().coerceAtMost(joined.length);val b=if(i==n-1)joined.length else ((i+1)*step).toInt().coerceAtMost(joined.length);ns+=Segment(base.segments[i].start,base.segments[i].end,joined.substring(a,b).trim(),"",true)};t.segments=ns;t.timed=true;t.estimated=true}else{val w=texts.map{it.length.coerceAtLeast(1)};val total=w.sum().toDouble();var cur=0.0;t.segments=texts.mapIndexed{i,x->val span=d*w[i]/total;val s=Segment(cur,(cur+span).coerceAtMost(d),x,"",true);cur+=span;s}.toMutableList();if(t.segments.isNotEmpty())t.segments.last().end=d;t.timed=true;t.estimated=true}}};rebuild()}

    private fun rebuild(){val t=activeTrack()?:run{fullText.text="";timeline.adapter=null;summary.text="尚無文字軌";return};val c=compareTrack();review=if(c!=null)Review.compare(t,c)else emptyList();val cnt=review.groupingBy{it.level}.eachCount();summary.text=if(c==null)"未比較" else "綠${cnt["green"]?:0} 黃${cnt["yellow"]?:0} 紅${cnt["red"]?:0}";ranges.clear();val b=StringBuilder();t.segments.forEach{s->val a=b.length;b.append(s.text.trim()).append(" ");ranges+=a to b.length};fullText.text=b.toString();timeline.adapter=TimelineAdapter(this,t,review);currentIndex=-1;updateViews()}

    private fun updateViews(){val p=player?:return;val d=p.duration.coerceAtLeast(0);val pos=p.currentPosition.coerceAtLeast(0);if(d>0)seek.progress=(pos*1000.0/d).toInt();timeLabel.text="${TrackParser.fmt(pos/1000.0)} / ${TrackParser.fmt(d/1000.0)}";val t=activeTrack()?:return;val now=pos/1000.0;var idx=t.segments.indexOfLast{it.start<=now};if(idx<0)return;val s=t.segments[idx];if(s.end>s.start && now>s.end && idx<t.segments.lastIndex)return;val sb=SpannableStringBuilder(fullText.text);if(idx<ranges.size){val (a,b)=ranges[idx];sb.setSpan(BackgroundColorSpan(Color.rgb(110,95,0)),a,b,Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);val f=((now-s.start)/(s.end-s.start).coerceAtLeast(.08)).coerceIn(0.0,1.0);val m=(a+(b-a)*f).toInt().coerceIn(a,b);if(m>a){sb.setSpan(BackgroundColorSpan(Color.rgb(255,213,79)),a,m,Spannable.SPAN_EXCLUSIVE_EXCLUSIVE);sb.setSpan(ForegroundColorSpan(Color.BLACK),a,m,Spannable.SPAN_EXCLUSIVE_EXCLUSIVE)}};fullText.text=sb;if(idx!=currentIndex){currentIndex=idx;(timeline.adapter as? TimelineAdapter)?.current=idx;(timeline.adapter as? TimelineAdapter)?.notifyDataSetChanged();timeline.setSelection(idx);fullText.layout?.let{lay->if(idx<ranges.size){val line=lay.getLineForOffset(ranges[idx].first);fullScroll.smoothScrollTo(0,(lay.getLineTop(line)-fullScroll.height/3).coerceAtLeast(0))}}}}
    private val ticker=object:Runnable{override fun run(){updateViews();handler.postDelayed(this,220)}}

    private fun geminiPolish(){val t=activeTrack()?:run{toast("請先加入文字軌");return};val key=apiKey.text.toString().trim();if(key.isBlank()){toast("請輸入 API Key");return};status.text="Gemini 順稿中…";Thread{try{val n=GeminiApi.polish(t,key,modelSpinner.selectedItem.toString());runOnUiThread{tracks+=n;refreshSpinners();activeSpinner.setSelection(tracks.lastIndex);status.text="完成"}}catch(e:Exception){runOnUiThread{status.text="失敗";showError(e)}}}.start()}
    private fun confirmAudioGemini(){val u=audioUri?:run{toast("請先選擇錄音");return};AlertDialog.Builder(this).setTitle("確認上傳音訊").setMessage("此功能會將目前錄音檔上傳 Google Gemini，以建立多人講者與核對時間軸。其他播放與比對功能不會上傳音訊。要繼續嗎？").setNegativeButton("取消",null).setPositiveButton("繼續"){_,_->geminiAudio(u)}.show()}
    private fun geminiAudio(u:Uri){val key=apiKey.text.toString().trim();if(key.isBlank()){toast("請輸入 API Key");return};status.text="上傳並辨識錄音中…";Thread{try{val n=GeminiApi.transcribeForReview(contentResolver,u,key,modelSpinner.selectedItem.toString());runOnUiThread{tracks+=n;val old=activeSpinner.selectedItemPosition;refreshSpinners();if(old>=0&&old<tracks.size)activeSpinner.setSelection(old);compareSpinner.setSelection(tracks.size);status.text="完成";rebuild()}}catch(e:Exception){runOnUiThread{status.text="失敗";showError(e)}}}.start()}
    private fun toast(s:String)=Toast.makeText(this,s,Toast.LENGTH_LONG).show()
    private fun showError(e:Exception)=AlertDialog.Builder(this).setTitle("處理失敗").setMessage(e.message?:e.toString()).setPositiveButton("OK",null).show()
    override fun onDestroy(){handler.removeCallbacksAndMessages(null);player?.release();super.onDestroy()}
}

class TimelineAdapter(private val ctx:Context,private val track:TextTrack,private val rev:List<ReviewResult>):BaseAdapter(){var current=-1;override fun getCount()=track.segments.size;override fun getItem(p:Int)=track.segments[p];override fun getItemId(p:Int)=p.toLong();override fun getView(p:Int,cv:View?,parent:ViewGroup?):View{val box=(cv as? LinearLayout)?:LinearLayout(ctx).apply{orientation=LinearLayout.VERTICAL;setPadding(12,10,12,10)};box.removeAllViews();val s=track.segments[p];val r=rev.getOrNull(p);val head=TextView(ctx).apply{text="${TrackParser.fmt(s.start)}–${TrackParser.fmt(s.end)}  ${s.speaker}";setTextColor(Color.rgb(30,100,170));textSize=13f};val txt=TextView(ctx).apply{text=s.text;textSize=17f;setTextColor(Color.DKGRAY)};box.addView(head);box.addView(txt);if(r!=null){box.addView(TextView(ctx).apply{text="比較：${r.other}";textSize=14f;setTextColor(Color.GRAY)});box.addView(TextView(ctx).apply{text="${(r.score*100).toInt()}%｜${r.note}";textSize=13f})};box.setBackgroundColor(if(p==current)Color.rgb(220,235,250) else when(r?.level){"green"->Color.rgb(230,248,234);"yellow"->Color.rgb(255,249,220);"red"->Color.rgb(255,230,230);else->Color.WHITE});return box}}
