package com.kazumaproject.quantity

import kotlin.math.abs
import kotlin.math.max
import kotlin.math.roundToInt

/** Deterministic L2-regularized least squares and pairwise squared-hinge ranking. */
object QuantityRankCalibrator {
    data class Anchor(val features: DoubleArray, val target: Double)
    /** Positive delta means the desired interpretation currently costs more. */
    data class Preference(val difference: DoubleArray, val baseCostDifference: Double, val margin: Double = 200.0)
    fun fit(size: Int, anchors: List<Anchor>, preferences: List<Preference>, regularization: Double = 0.05): IntArray {
        require(size > 0 && regularization > 0 && regularization.isFinite())
        require(anchors.all { it.features.size == size && it.target.isFinite() && it.features.all(Double::isFinite) })
        require(preferences.all { it.difference.size == size && it.baseCostDifference.isFinite() &&
            it.margin >= 0 && it.margin.isFinite() && it.difference.all(Double::isFinite) })
        val weights = DoubleArray(size)
        fun dot(features: DoubleArray): Double = features.indices.sumOf { features[it] * weights[it] }
        fun objective(): Double = regularization * weights.sumOf { it * it } +
            anchors.sumOf { val error = dot(it.features) - it.target; error * error } +
            preferences.sumOf { val error = max(0.0, it.margin + it.baseCostDifference + dot(it.difference)); error * error }
        repeat(4000) {
            var largestChange = 0.0
            for (column in weights.indices) {
                var gradient = regularization * weights[column]
                var curvature = regularization
                for (row in anchors) {
                    gradient += row.features[column] * (dot(row.features) - row.target)
                    curvature += row.features[column] * row.features[column]
                }
                for (row in preferences) {
                    val error = row.margin + row.baseCostDifference + dot(row.difference)
                    if (error > 0.0) {
                        gradient += row.difference[column] * error
                        curvature += row.difference[column] * row.difference[column]
                    }
                }
                val before = weights[column]
                val loss = objective()
                var step = gradient / curvature
                for (attempt in 0 until 30) {
                    weights[column] = (before - step).coerceIn(-20000.0, 20000.0)
                    if (objective() <= loss + 1e-8) break
                    weights[column] = before
                    step *= 0.5
                }
                largestChange = max(largestChange, abs(weights[column] - before))
            }
            if (largestChange < 1e-5) return weights.map(Double::roundToInt).toIntArray()
        }
        return weights.map(Double::roundToInt).toIntArray()
    }
}
