package mozc_runtime.converter

// Ported from mozc/src/converter/candidate.h
// Ported from mozc/src/converter/candidate.cc
class Candidate {
    enum class Command {
        DEFAULT_COMMAND,
        ENABLE_INCOGNITO_MODE,
        DISABLE_INCOGNITO_MODE,
        ENABLE_PRESENTATION_MODE,
        DISABLE_PRESENTATION_MODE,
    }

    enum class Category {
        DEFAULT_CATEGORY,
        SYMBOL,
        OTHER,
    }

    var key: String = ""
    var value: String = ""
    var contentKey: String = ""
    var contentValue: String = ""
    var consumedKeySize: Int = 0
    var prefix: String = ""
    var suffix: String = ""
    var description: String = ""
    var a11yDescription: String = ""
    var displayValue: String = ""
    var usageId: Int = 0
    var usageTitle: String = ""
    var usageDescription: String = ""
    var cost: Int = 0
    var wcost: Int = 0
    var structureCost: Int = 0
    var lid: Int = 0
    var rid: Int = 0
    var attributes: Int = Attribute.DEFAULT_ATTRIBUTE
    var category: Category = Category.DEFAULT_CATEGORY
    var command: Command = Command.DEFAULT_COMMAND
    val innerSegments: MutableList<InnerSegment> = ArrayList()
    var costBeforeRescoring: Int = 0

    fun clear() {
        key = ""
        value = ""
        contentKey = ""
        contentValue = ""
        consumedKeySize = 0
        prefix = ""
        suffix = ""
        description = ""
        a11yDescription = ""
        displayValue = ""
        usageId = 0
        usageTitle = ""
        usageDescription = ""
        cost = 0
        wcost = 0
        structureCost = 0
        lid = 0
        rid = 0
        attributes = Attribute.DEFAULT_ATTRIBUTE
        category = Category.DEFAULT_CATEGORY
        command = Command.DEFAULT_COMMAND
        innerSegments.clear()
        costBeforeRescoring = 0
    }

    fun functionalKey(): String =
        key.utf8Substring(minOf(key.utf8Size(), contentKey.utf8Size()))

    fun functionalValue(): String =
        value.utf8Substring(minOf(value.utf8Size(), contentValue.utf8Size()))

    fun copyFrom(other: Candidate) {
        key = other.key
        value = other.value
        contentKey = other.contentKey
        contentValue = other.contentValue
        consumedKeySize = other.consumedKeySize
        prefix = other.prefix
        suffix = other.suffix
        description = other.description
        a11yDescription = other.a11yDescription
        displayValue = other.displayValue
        usageId = other.usageId
        usageTitle = other.usageTitle
        usageDescription = other.usageDescription
        cost = other.cost
        wcost = other.wcost
        structureCost = other.structureCost
        lid = other.lid
        rid = other.rid
        attributes = other.attributes
        category = other.category
        command = other.command
        innerSegments.clear()
        innerSegments += other.innerSegments
        costBeforeRescoring = other.costBeforeRescoring
    }
}
