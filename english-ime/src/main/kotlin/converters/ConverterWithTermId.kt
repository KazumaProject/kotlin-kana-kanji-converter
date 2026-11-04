package converters

import louds.louds_with_term_id.LOUDSWithTermId
import prefix.prefix_with_term_id.PrefixNodeWithTermId
import java.util.*
import java.util.ArrayDeque

class ConverterWithTermId {

    fun convert(
        rootNode: PrefixNodeWithTermId,
    ): LOUDSWithTermId {

        val louds = LOUDSWithTermId()
        val queue: Queue<PrefixNodeWithTermId> = ArrayDeque()
        queue.add(rootNode)

        while (!queue.isEmpty()) {
            processQueue(queue, louds)
        }
        return louds
    }

    private fun processQueue(queue: Queue<PrefixNodeWithTermId>, louds: LOUDSWithTermId) {
        val node: PrefixNodeWithTermId = queue.poll()
        if (node.hasChild()) {
            node.children.forEach { entry ->
                queue.add(entry.value.second)
                louds.apply {
                    LBSTemp.add(true)
                    labelsTemp.add(entry.key)
                    isLeafTemp.add(entry.value.second.isWord)
                    if (entry.value.second.isWord) {
                        termIds.add(entry.value.second.termId)
                    }
                }
            }
        }

        louds.apply {
            LBSTemp.add(false)
            isLeafTemp.add(false)
        }

    }

}
