package {{PACKAGE}}.about

import android.content.Context
import androidx.annotation.ColorInt
import io.noties.markwon.AbstractMarkwonPlugin
import io.noties.markwon.Markwon
import io.noties.markwon.core.MarkwonTheme
import io.noties.markwon.ext.strikethrough.StrikethroughPlugin
import io.noties.markwon.ext.tables.TablePlugin
import io.noties.markwon.ext.tables.TableTheme
import io.noties.markwon.linkify.LinkifyPlugin

/**
 * Markdown for the About documents with Markwon (CommonMark): headings, emphasis, lists, quotes,
 * code blocks, rules and links, plus tables (the permissions, services and licenses tables),
 * strikethrough and automatic links. Links open in the browser (Markwon sets LinkMovementMethod on
 * the TextView, so the TextView must NOT be selectable).
 *
 * Colors come from the app's theme: [accent] for links, quotes and bullets; [line] for the table
 * borders and rules. Gradle (one version for every module):
 *   io.noties.markwon:core, ext-strikethrough, ext-tables, linkify : 4.6.2
 */
object MarkdownRenderer {

    fun create(context: Context, @ColorInt accent: Int, @ColorInt line: Int): Markwon =
        Markwon.builder(context)
            .usePlugin(StrikethroughPlugin.create())
            .usePlugin(
                TablePlugin.create(
                    TableTheme.Builder()
                        .tableBorderColor(line)
                        .tableBorderWidth(dp(context, 1))
                        .tableCellPadding(dp(context, 8))
                        .tableHeaderRowBackgroundColor(withAlpha(accent, 0x1F))
                        .tableEvenRowBackgroundColor(withAlpha(line, 0x33))
                        .build()
                )
            )
            .usePlugin(LinkifyPlugin.create())
            .usePlugin(object : AbstractMarkwonPlugin() {
                override fun configureTheme(builder: MarkwonTheme.Builder) {
                    builder.linkColor(accent)
                        .blockQuoteColor(accent)
                        .listItemColor(accent)
                        .thematicBreakColor(line)
                        .thematicBreakHeight(dp(context, 1))
                        .headingBreakHeight(0)
                        .isLinkUnderlined(false)
                }
            })
            .build()

    private fun dp(context: Context, value: Int) = (value * context.resources.displayMetrics.density).toInt()

    private fun withAlpha(@ColorInt color: Int, alpha: Int) = (color and 0x00FFFFFF) or (alpha shl 24)
}
