package com.kazumaproject.classification

import kotlinx.serialization.json.*
import java.io.File

/** Applied once when packaging raw category records, including kampo and medical. */
internal data class CategoryCostPolicy(
    val unpenalizedReadingLength: Int,
    val costPerExtraCharacter: Int,
    val maximumPenalty: Int,
) {
    init {
        require(unpenalizedReadingLength >= 0 && costPerExtraCharacter >= 0 && maximumPenalty >= 0)
    }

    fun cost(reading: String, sourceCost: Short): Short {
        val extraLength = (reading.length - unpenalizedReadingLength).coerceAtLeast(0)
        val penalty = minOf(maximumPenalty.toLong(), extraLength.toLong() * costPerExtraCharacter)
        val result = sourceCost.toLong() + penalty
        require(result in Short.MIN_VALUE..Short.MAX_VALUE) {
            "Category cost outside Short range: reading=$reading sourceCost=$sourceCost penalty=$penalty"
        }
        return result.toShort()
    }

    companion object {
        fun load(file: File = File("src/main/classification/runtime-cost-policy.json")): CategoryCostPolicy {
            val json = Json.parseToJsonElement(file.readText()).jsonObject
            require(json.getValue("schemaVersion").jsonPrimitive.int == 1) { "Unsupported category cost policy" }
            return CategoryCostPolicy(
                json.getValue("unpenalizedReadingLength").jsonPrimitive.int,
                json.getValue("costPerExtraCharacter").jsonPrimitive.int,
                json.getValue("maximumPenalty").jsonPrimitive.int,
            )
        }
    }
}
