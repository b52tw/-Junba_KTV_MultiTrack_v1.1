package tw.junba.ktvmultitrack

import kotlin.math.abs
import kotlin.math.max

object Review {
    private fun norm(s:String)=s.lowercase().replace(Regex("[\\s　，。！？；：、,.!?;:\"“”‘’()（）\\[\\]【】<>《》…—-]+"),"")
    private fun levenshtein(a:String,b:String):Int{if(a.isEmpty())return b.length;if(b.isEmpty())return a.length;var prev=IntArray(b.length+1){it};for(i in a.indices){val cur=IntArray(b.length+1);cur[0]=i+1;for(j in b.indices){cur[j+1]=minOf(cur[j]+1,prev[j+1]+1,prev[j]+if(a[i]==b[j])0 else 1)};prev=cur};return prev[b.length]}
    fun similarity(a:String,b:String):Double{val x=norm(a);val y=norm(b);if(x.isEmpty()&&y.isEmpty())return 1.0;if(x.isEmpty()||y.isEmpty())return 0.0;return 1.0-levenshtein(x,y).toDouble()/max(x.length,y.length)}
    fun match(s:Segment,t:TextTrack):Segment?{if(t.segments.isEmpty())return null;val mid=if(s.end>s.start)(s.start+s.end)/2 else s.start;return t.segments.firstOrNull{it.start<=mid && mid<max(it.end,it.start+.05)} ?: t.segments.minByOrNull{abs(it.start-mid)}}
    fun compare(a:TextTrack,b:TextTrack)=a.segments.map{s->val h=match(s,b);if(h==null)ReviewResult(0.0,"red","","找不到對應文字") else {val sc=similarity(s.text,h.text);val lv=if(sc>=.82)"green" else if(sc>=.55)"yellow" else "red";ReviewResult(sc,lv,h.text,if(lv=="green")"高度吻合" else if(lv=="yellow")"建議人工核對" else "可能漏字、錯字或內容不一致")}}
}
