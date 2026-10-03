package tw.junba.ktvmultitrack

import android.content.ContentResolver
import android.net.Uri
import android.provider.OpenableColumns
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.zip.ZipInputStream
import kotlin.math.max

object TrackParser {
    private val timeRe = Regex("(?:(\\d{1,2}):)?(\\d{1,2}):(\\d{2})(?:[,.](\\d{1,3}))?")
    private val rangeRe = Regex("((?:\\d{1,2}:)?\\d{1,2}:\\d{2}(?:[,.]\\d{1,3})?)\\s*(?:-->|-|–|—|~|至)\\s*((?:\\d{1,2}:)?\\d{1,2}:\\d{2}(?:[,.]\\d{1,3})?)")

    fun displayName(cr: ContentResolver, uri: Uri): String {
        cr.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c -> if (c.moveToFirst()) return c.getString(0) ?: "文字軌" }
        return uri.lastPathSegment ?: "文字軌"
    }
    fun parseTime(s: String): Double {
        val m=timeRe.find(s.trim()) ?: return s.toDoubleOrNull() ?: 0.0
        val h=m.groupValues[1].toIntOrNull() ?: 0; val min=m.groupValues[2].toIntOrNull() ?: 0; val sec=m.groupValues[3].toIntOrNull() ?: 0
        val ms=(m.groupValues[4].ifBlank{"0"}.padEnd(3,'0').take(3)).toIntOrNull() ?: 0
        return h*3600.0+min*60+sec+ms/1000.0
    }
    fun fmt(t: Double): String { val x=max(0.0,t).toInt(); return "%02d:%02d:%02d".format(x/3600,(x%3600)/60,x%60) }
    fun load(cr: ContentResolver, uri: Uri): TextTrack {
        val name=displayName(cr,uri); val ext=name.substringAfterLast('.',"").lowercase()
        if(ext=="docx") return parseDocx(cr,uri,name.substringBeforeLast('.'))
        val text=cr.openInputStream(uri)!!.bufferedReader(Charsets.UTF_8).use(BufferedReader::readText)
        return when(ext){"srt"->parseSrt(text,name.substringBeforeLast('.'),"SRT");"vtt"->parseSrt(text.replace(Regex("^WEBVTT.*?\\n\\s*\\n",RegexOption.DOT_MATCHES_ALL),""),name.substringBeforeLast('.'),"VTT");"json"->parseJson(text,name.substringBeforeLast('.'));else->parseTxt(text,name.substringBeforeLast('.'))}.also{it.source=uri.toString()}
    }
    fun parseSrt(text:String,name:String,fmt:String):TextTrack{
        val segs= mutableListOf<Segment>()
        text.trim().split(Regex("\\r?\\n\\s*\\r?\\n")).forEach{block->
            val lines=block.lines().filter{it.isNotBlank()}; val idx=lines.indexOfFirst{it.contains("-->")}; if(idx<0)return@forEach
            val m=rangeRe.find(lines[idx])?:return@forEach; var payload=lines.drop(idx+1).joinToString(" ").trim(); var sp=""
            val sm=Regex("^([^：:]{1,30})[：:]\\s*(.+)$").find(payload); if(sm!=null && listOf("speaker","講者","說話者","主持","老師","同學").any{sm.groupValues[1].lowercase().contains(it)}){sp=sm.groupValues[1];payload=sm.groupValues[2]}
            segs+=Segment(parseTime(m.groupValues[1]),parseTime(m.groupValues[2]),payload,sp)
        }
        return TextTrack(name,segs,fmt,segs.isNotEmpty(),false)
    }
    fun parseTxt(text:String,name:String):TextTrack{
        val timed= mutableListOf<Segment>(); val plain= mutableListOf<String>()
        text.lines().map{it.trim()}.filter{it.isNotBlank()}.forEach{line->
            val m=rangeRe.find(line); if(m!=null){var p=(line.substring(0,m.range.first)+" "+line.substring(m.range.last+1)).trim(' ','[',']','｜','|',':','-','–','—');var sp="";val sm=Regex("^([^：:]{1,30})[：:]\\s*(.+)$").find(p);if(sm!=null){sp=sm.groupValues[1];p=sm.groupValues[2]};timed+=Segment(parseTime(m.groupValues[1]),parseTime(m.groupValues[2]),p,sp)} else plain+=line
        }
        if(timed.isNotEmpty()) return TextTrack(name,timed,"TXT",true,false)
        val parts=splitSentences(plain.joinToString("\n")); return TextTrack(name,parts.map{Segment(0.0,0.0,it,"",true)}.toMutableList(),"TXT",false,true)
    }
    fun splitSentences(text:String):List<String>{
        val t=text.replace(Regex("\\s+")," ").trim(); if(t.isBlank())return emptyList(); val p=t.split(Regex("(?<=[。！？!?；;.])\\s*|\\n+")).filter{it.isNotBlank()}; if(p.size>1)return p
        return if(t.length>100)t.chunked(70) else listOf(t)
    }
    fun parseJson(text:String,name:String):TextTrack{
        val arr= if(text.trim().startsWith("[")) JSONArray(text) else JSONObject(text).optJSONArray("segments") ?: JSONArray()
        val segs= mutableListOf<Segment>(); for(i in 0 until arr.length()){val o=arr.optJSONObject(i)?:continue;val tx=o.optString("text",o.optString("content",""));if(tx.isBlank())continue;val st=o.optDouble("start",o.optDouble("start_time",0.0));val en=o.optDouble("end",o.optDouble("end_time",st));segs+=Segment(st,en,tx,o.optString("speaker",o.optString("speaker_label","")),o.optBoolean("estimated",false))}
        val tm=segs.any{it.end>it.start}; return TextTrack(name,segs,"JSON",tm,!tm)
    }
    fun parseDocx(cr:ContentResolver,uri:Uri,name:String):TextTrack{
        var xml=""; ZipInputStream(cr.openInputStream(uri)!!).use{z-> while(true){val e=z.nextEntry?:break;if(e.name=="word/document.xml"){xml=z.readBytes().toString(Charsets.UTF_8);break}}}
        if(xml.isBlank()) return TextTrack(name, mutableListOf(),"DOCX",false,true)
        val rows=Regex("<w:tr[\\s\\S]*?</w:tr>").findAll(xml).toList(); val segs= mutableListOf<Segment>()
        for(r in rows){val cells=Regex("<w:tc[\\s\\S]*?</w:tc>").findAll(r.value).map{stripXml(it.value)}.toList();if(cells.isEmpty())continue;val tm=rangeRe.find(cells[0])?:continue;val sp=if(cells.size>=3)cells[1] else "";val tx=if(cells.size>=3)cells[2] else cells.getOrElse(1){""};if(tx.isNotBlank())segs+=Segment(parseTime(tm.groupValues[1]),parseTime(tm.groupValues[2]),tx,sp)}
        if(segs.isNotEmpty())return TextTrack(name,segs,"DOCX",true,false,uri.toString())
        return parseTxt(stripXml(xml),name).also{it.format="DOCX";it.source=uri.toString()}
    }
    private fun stripXml(x:String)=x.replace("</w:p>","\n").replace("</w:tc>","\t").replace(Regex("<[^>]+>"),"").replace("&amp;","&").replace("&lt;","<").replace("&gt;",">").replace(Regex("[ \\t]+")," ").trim()
}
