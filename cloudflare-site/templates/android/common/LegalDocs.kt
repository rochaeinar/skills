package {{PACKAGE}}.about

import android.content.Context

/**
 * The About documents: Markdown files in assets/legal/, one per language
 * (privacy_en.md, privacy_es.md, terms_pt-BR.md…). The same files are published on the website
 * (cloudflare-site: `web.py legal`), so the app, the website and Google Play say the same thing.
 *
 * The file follows the language the app is SHOWN in (the activity's configuration, which also
 * follows a per-app language), not Locale.getDefault(), which on Android 12 and lower does not
 * change with the per-app language. Fallback: full tag (pt-BR) → language (pt) → English.
 */
object LegalDocs {

    enum class Doc(val fileBase: String) { PRIVACY("privacy"), TERMS("terms"), LICENSES("licenses") }

    private const val FOLDER = "legal"
    private const val FALLBACK = "en"

    /** Path inside assets of [doc] for the language [context] is shown in. */
    fun assetPath(context: Context, doc: Doc): String {
        val locale = context.resources.configuration.locales[0]
        val available = context.assets.list(FOLDER)?.toSet().orEmpty()
        val candidates = listOf(locale.toLanguageTag(), locale.language, FALLBACK)
            .distinct()
            .map { "${doc.fileBase}_$it.md" }
        return "$FOLDER/" + (candidates.firstOrNull { it in available } ?: candidates.last())
    }

    /** The Markdown text, or an empty string if the file is missing (never crashes the screen). */
    fun read(context: Context, assetPath: String): String =
        runCatching { context.assets.open(assetPath).bufferedReader(Charsets.UTF_8).use { it.readText() } }
            .getOrDefault("")
}
