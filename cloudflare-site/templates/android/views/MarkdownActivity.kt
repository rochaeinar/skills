package {{PACKAGE}}.about

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import {{PACKAGE}}.R

/**
 * Shows one About document (Markdown in assets) with its title. The file is read and parsed off the
 * main thread (the licenses can be long); links open in the browser.
 */
class MarkdownActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_markdown)
        val root = findViewById<android.view.View>(R.id.markdownRoot)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.updatePadding(left = bars.left, top = bars.top, right = bars.right, bottom = bars.bottom)
            insets
        }

        findViewById<ImageView>(R.id.markdownBack).setOnClickListener { finish() }
        findViewById<TextView>(R.id.markdownTitle).text = intent.getStringExtra(EXTRA_TITLE)

        val body = findViewById<TextView>(R.id.markdownBody)
        val markwon = MarkdownRenderer.create(
            this,
            accent = ContextCompat.getColor(this, R.color.about_accent),
            line = ContextCompat.getColor(this, R.color.about_divider),
        )
        val path = intent.getStringExtra(EXTRA_PATH).orEmpty()
        lifecycleScope.launch {
            val rendered = withContext(Dispatchers.Default) {
                markwon.toMarkdown(LegalDocs.read(this@MarkdownActivity, path))
            }
            markwon.setParsedMarkdown(body, rendered)
        }
    }

    companion object {
        private const val EXTRA_TITLE = "title"
        private const val EXTRA_PATH = "assetPath"

        fun intent(context: Context, title: String, assetPath: String) =
            Intent(context, MarkdownActivity::class.java)
                .putExtra(EXTRA_TITLE, title)
                .putExtra(EXTRA_PATH, assetPath)
    }
}
