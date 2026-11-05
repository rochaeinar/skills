package {{PACKAGE}}.about

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.ImageView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.pm.PackageInfoCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import {{PACKAGE}}.R

/**
 * About: identity (icon, name, version), the official website (opens the browser) and the
 * documents (privacy policy, terms, third-party licenses) shown in-app as Markdown by
 * [MarkdownActivity]. The developer sits at the bottom.
 *
 * If the app navigates with fragments or Navigation, turn this into a Fragment/destination with the
 * same layout and logic; keep one way of navigating per app.
 */
class AboutActivity : AppCompatActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_about)
        applySystemBarInsets()

        findViewById<ImageView>(R.id.aboutBack).setOnClickListener { finish() }
        findViewById<TextView>(R.id.aboutVersion).text = versionText(this)
        findViewById<android.view.View>(R.id.aboutWeb).setOnClickListener { openWebsite() }

        documentRow(R.id.aboutPrivacy, R.drawable.ic_about_privacy, R.string.about_privacy, LegalDocs.Doc.PRIVACY)
        documentRow(R.id.aboutTerms, R.drawable.ic_about_terms, R.string.about_terms, LegalDocs.Doc.TERMS)
        documentRow(R.id.aboutLicenses, R.drawable.ic_about_licenses, R.string.about_licenses, LegalDocs.Doc.LICENSES)
    }

    /** One row of the documents card: icon tile, title, chevron; opens the Markdown document. */
    private fun documentRow(rowId: Int, icon: Int, title: Int, doc: LegalDocs.Doc) {
        val row = findViewById<android.view.View>(rowId)
        row.findViewById<ImageView>(R.id.rowIcon).setImageResource(icon)
        row.findViewById<TextView>(R.id.rowTitle).setText(title)
        row.setOnClickListener {
            startActivity(MarkdownActivity.intent(this, getString(title), LegalDocs.assetPath(this, doc)))
        }
    }

    private fun openWebsite() {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(getString(R.string.about_web_url))))
        } catch (e: ActivityNotFoundException) {
            // No browser on the device: nothing to open. Log it with the app's logger if it has one.
        }
    }

    /** Edge-to-edge (enforced from targetSdk 35): keep the content clear of the system bars. */
    private fun applySystemBarInsets() {
        val root = findViewById<android.view.View>(R.id.aboutRoot)
        ViewCompat.setOnApplyWindowInsetsListener(root) { view, insets ->
            val bars = insets.getInsets(WindowInsetsCompat.Type.systemBars() or WindowInsetsCompat.Type.displayCutout())
            view.updatePadding(left = bars.left, top = bars.top, right = bars.right, bottom = bars.bottom)
            insets
        }
    }

    companion object {
        fun versionText(context: Context): String {
            val info = context.packageManager.getPackageInfo(context.packageName, 0)
            return context.getString(R.string.about_version, info.versionName ?: "", PackageInfoCompat.getLongVersionCode(info))
        }
    }
}
