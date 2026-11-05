package {{PACKAGE}}.about

import android.content.Context

/**
 * The About documents: Markdown files in assets/legal/ (privacy.md, terms.md, licenses.md).
 * Legal documents are in ENGLISH ONLY, in the app and on the website: they are never translated
 * (one authoritative text). The same files are published on the website (cloudflare-site:
 * `web.py legal`), so the app, the website and Google Play say exactly the same thing.
 * The labels that open them ("Privacy policy"…) are translated like any other string.
 */
object LegalDocs {

    enum class Doc(val fileBase: String) { PRIVACY("privacy"), TERMS("terms"), LICENSES("licenses") }

    /** Path inside assets of [doc]. */
    fun assetPath(doc: Doc): String = "legal/${doc.fileBase}.md"

    /** The Markdown text, or an empty string if the file is missing (never crashes the screen). */
    fun read(context: Context, assetPath: String): String =
        runCatching { context.assets.open(assetPath).bufferedReader(Charsets.UTF_8).use { it.readText() } }
            .getOrDefault("")
}
