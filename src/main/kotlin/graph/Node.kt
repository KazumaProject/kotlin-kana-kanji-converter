package com.kazumaproject.graph

data class Node(
    val l: Short,
    val r: Short,
    var score: Int,
    var f: Int,
    var g: Int = 0,
    val tango: String,
    val len: Short,
    var sPos: Int,
    val key: String = "",
    val wcost: Int = score,
    var totalCost: Int = Int.MAX_VALUE,
    var prev: Node? = null,
    var next: Node? = null,
){
    override fun toString(): String {
        return this.tango
    }
}
