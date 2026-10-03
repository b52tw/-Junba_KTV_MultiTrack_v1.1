package tw.junba.ktvmultitrack

data class Segment(var start: Double, var end: Double, var text: String, var speaker: String = "", var estimated: Boolean = false)
data class TextTrack(var name: String, var segments: MutableList<Segment>, var format: String, var timed: Boolean, var estimated: Boolean, var source: String = "")
data class ReviewResult(val score: Double, val level: String, val other: String, val note: String)
