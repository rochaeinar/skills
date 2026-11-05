package {{PACKAGE}}.about

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.widget.TextView
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.toArgb
import androidx.core.graphics.drawable.toBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import {{PACKAGE}}.R

/*
 * About for Compose apps. Two ways to use it:
 *  - The app already has an About/Settings screen: add [WebsiteLink] under the version and
 *    [LegalDocumentsCard] as a section, and replace any in-app privacy/terms dialogs with
 *    [MarkdownDocumentScreen] (one source of truth: assets/legal).
 *  - It has none: use [AboutScreen] as a new destination reachable from Settings or the main menu.
 * Colors come from MaterialTheme: map them to the app's own design tokens if it has a custom
 * theme object (e.g. LocalAppColors) instead of Material's colorScheme.
 */

/** The full About screen: identity, website, documents, developer. */
@Composable
fun AboutScreen(
    onBack: () -> Unit,
    onOpenDocument: (title: String, assetPath: String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    Box(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).windowInsetsPadding(WindowInsets.safeDrawing)) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Column(Modifier.widthIn(max = 480.dp).fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
                Spacer(Modifier.size(56.dp))
                // The launcher icon is adaptive (painterResource only takes vectors and bitmaps):
                // render it to a bitmap. A brand logo VectorDrawable can use painterResource instead.
                val icon = remember {
                    context.packageManager.getApplicationIcon(context.packageName).toBitmap(256, 256).asImageBitmap()
                }
                Image(
                    icon,
                    contentDescription = stringResource(R.string.app_name),
                    modifier = Modifier.size(84.dp).clip(RoundedCornerShape(20.dp)),
                )
                Text(
                    stringResource(R.string.app_name),
                    style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onBackground, modifier = Modifier.padding(top = 16.dp),
                )
                Text(
                    remember { AboutVersion.text(context) },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 6.dp),
                )
                WebsiteLink(Modifier.padding(top = 20.dp))
                LegalDocumentsCard(onOpenDocument, Modifier.padding(top = 28.dp))
                Spacer(Modifier.size(28.dp))
                Text(
                    stringResource(R.string.about_developed_by),
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    stringResource(R.string.about_copyright),
                    style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 4.dp, bottom = 24.dp),
                )
            }
        }
        IconButton(onClick = onBack, modifier = Modifier.padding(4.dp)) {
            Icon(painterResource(R.drawable.ic_about_back), contentDescription = stringResource(R.string.about_back))
        }
    }
}

/** Outlined pill with the website's domain; opens it in the browser. */
@Composable
fun WebsiteLink(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val url = stringResource(R.string.about_web_url)
    val accent = MaterialTheme.colorScheme.primary
    Surface(
        onClick = {
            try {
                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
            } catch (e: ActivityNotFoundException) {
                // No browser: nothing to open (log it with the app's logger).
            }
        },
        shape = RoundedCornerShape(22.dp),
        color = MaterialTheme.colorScheme.surface,
        border = BorderStroke(1.dp, accent.copy(alpha = 0.45f)),
        modifier = modifier.heightIn(min = 44.dp),
    ) {
        Row(Modifier.padding(horizontal = 16.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(painterResource(R.drawable.ic_about_web), contentDescription = null, tint = accent, modifier = Modifier.size(17.dp))
            Text(
                stringResource(R.string.about_web_label), color = accent, fontWeight = FontWeight.Bold,
                style = MaterialTheme.typography.labelLarge, maxLines = 1, modifier = Modifier.padding(horizontal = 8.dp),
            )
            Icon(painterResource(R.drawable.ic_about_external), contentDescription = null, tint = accent, modifier = Modifier.size(14.dp))
        }
    }
}

/** "Legal & information": privacy policy, terms, third-party licenses (+ app-specific documents). */
@Composable
fun LegalDocumentsCard(onOpenDocument: (title: String, assetPath: String) -> Unit, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val rows = listOf(
        Triple(R.drawable.ic_about_privacy, R.string.about_privacy, LegalDocs.Doc.PRIVACY),
        Triple(R.drawable.ic_about_terms, R.string.about_terms, LegalDocs.Doc.TERMS),
        Triple(R.drawable.ic_about_licenses, R.string.about_licenses, LegalDocs.Doc.LICENSES),
    )
    Column(modifier.fillMaxWidth()) {
        Text(
            stringResource(R.string.about_section_documents).uppercase(),
            style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(start = 8.dp, bottom = 8.dp).semantics { heading() },
        )
        Surface(
            shape = RoundedCornerShape(18.dp), color = MaterialTheme.colorScheme.surface,
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        ) {
            Column {
                rows.forEachIndexed { index, (icon, title, doc) ->
                    if (index > 0) HorizontalDivider(Modifier.padding(start = 66.dp), color = MaterialTheme.colorScheme.outlineVariant)
                    val label = stringResource(title)
                    DocumentRow(icon, label) { onOpenDocument(label, LegalDocs.assetPath(context, doc)) }
                }
            }
        }
    }
}

@Composable
private fun DocumentRow(icon: Int, title: String, onClick: () -> Unit) {
    val accent = MaterialTheme.colorScheme.primary
    Row(
        Modifier.fillMaxWidth().heightIn(min = 56.dp).clickable(role = Role.Button, onClick = onClick).padding(horizontal = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Box(
            Modifier.size(36.dp).clip(RoundedCornerShape(10.dp)).background(accent.copy(alpha = 0.12f)),
            contentAlignment = Alignment.Center,
        ) { Icon(painterResource(icon), contentDescription = null, tint = accent, modifier = Modifier.size(20.dp)) }
        Text(title, style = MaterialTheme.typography.bodyLarge, color = MaterialTheme.colorScheme.onSurface, modifier = Modifier.weight(1f))
        Icon(painterResource(R.drawable.ic_about_chevron), contentDescription = null, tint = MaterialTheme.colorScheme.outline, modifier = Modifier.size(18.dp))
    }
}

/** One About document: title bar with back, then the Markdown (Markwon in a TextView). */
@Composable
fun MarkdownDocumentScreen(title: String, assetPath: String, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val accent = MaterialTheme.colorScheme.primary.toArgb()
    val line = MaterialTheme.colorScheme.outlineVariant.toArgb()
    val textColor = MaterialTheme.colorScheme.onSurface.toArgb()
    val markwon = remember(accent, line) { MarkdownRenderer.create(context, accent, line) }
    var rendered by remember(assetPath) { mutableStateOf<android.text.Spanned?>(null) }
    LaunchedEffect(assetPath, markwon) {
        rendered = withContext(Dispatchers.Default) { markwon.toMarkdown(LegalDocs.read(context, assetPath)) }
    }
    Column(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).windowInsetsPadding(WindowInsets.safeDrawing)) {
        Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).padding(horizontal = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) {
                Icon(painterResource(R.drawable.ic_about_back), contentDescription = stringResource(R.string.about_back))
            }
            Text(
                title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, maxLines = 2,
                color = MaterialTheme.colorScheme.onBackground, modifier = Modifier.padding(start = 4.dp, end = 16.dp).semantics { heading() },
            )
        }
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            AndroidView(
                factory = { ctx -> TextView(ctx).apply { textSize = 15f; setLineSpacing(4f * ctx.resources.displayMetrics.density, 1f) } },
                update = { view ->
                    view.setTextColor(textColor)
                    rendered?.let { markwon.setParsedMarkdown(view, it) }
                },
                modifier = Modifier.widthIn(max = 680.dp).fillMaxWidth().padding(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 32.dp),
            )
        }
    }
}

object AboutVersion {
    fun text(context: android.content.Context): String {
        val info = context.packageManager.getPackageInfo(context.packageName, 0)
        return context.getString(R.string.about_version, info.versionName ?: "", androidx.core.content.pm.PackageInfoCompat.getLongVersionCode(info))
    }
}
