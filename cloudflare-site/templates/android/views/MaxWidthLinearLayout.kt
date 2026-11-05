package {{PACKAGE}}.about

import android.content.Context
import android.util.AttributeSet
import android.widget.LinearLayout

/**
 * A vertical LinearLayout no wider than android:maxWidth: on tablets and in landscape the About
 * content keeps the proportions of a phone, centred (layout_gravity="center_horizontal").
 */
class MaxWidthLinearLayout @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
) : LinearLayout(context, attrs) {

    private val maxWidth: Int = context.obtainStyledAttributes(attrs, intArrayOf(android.R.attr.maxWidth)).run {
        try { getDimensionPixelSize(0, Int.MAX_VALUE) } finally { recycle() }
    }

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        val width = MeasureSpec.getSize(widthMeasureSpec)
        val spec = if (width > maxWidth) MeasureSpec.makeMeasureSpec(maxWidth, MeasureSpec.EXACTLY) else widthMeasureSpec
        super.onMeasure(spec, heightMeasureSpec)
    }
}
