package engine

import com.kazumaproject.graph.Node
import com.kazumaproject.mozc.ConnectionMatrix
import com.kazumaproject.viterbi.FindPath
import kotlin.test.*

class FindPathSentenceTest {
    private fun node(value:String,start:Int,cost:Int=0,left:Int=0,right:Int=0)=Node(left.toShort(),right.toShort(),cost,0,tango=value,len=1,sPos=start,wcost=cost)
    @Test fun negativeLaterCostsAreIncludedInCandidateOrdering() {
        val bos=node("BOS",0).copy(len=0)
        val a=node("A",0,0,right=1);val b=node("B",0,5,right=2)
        val c=node("C",1,0,left=1);val d=node("D",1,-100,left=2)
        val eos=node("EOS",2).copy(len=0)
        val graph=listOf(mutableListOf(mutableListOf(bos)),mutableListOf(mutableListOf(a,b)),mutableListOf(mutableListOf(c,d)),mutableListOf(mutableListOf(eos)))
        val costs=ShortArray(9);costs[1*3+2]=200;costs[2*3+1]=200
        val matrix=ConnectionMatrix(3,costs)
        val candidates=FindPath().backwardAStar(graph,2,matrix,4)
        assertEquals(listOf("BD","AC","AD","BC"),candidates)
        assertEquals(candidates.first(),FindPath().viterbi(graph,2,matrix))
    }
    @Test fun longIdenticalOutputPathsDoNotExpandExponentially() {
        val length=24
        val graph=MutableList(length+2) { mutableListOf<MutableList<Node>>() }
        graph[0].add(mutableListOf(node("BOS",0).copy(len=0)))
        for(i in 0 until length) {
            graph[i+1].add(MutableList(32) { node("字",i,it) })
            if(i==length-1) graph[i+1].single().add(node("別",i,50))
        }
        graph.last().add(mutableListOf(node("EOS",length).copy(len=0)))
        assertEquals(listOf("字".repeat(length),"字".repeat(length-1)+"別"),FindPath().backwardAStar(graph,length,ConnectionMatrix(1,shortArrayOf(0)),10))
    }
}
