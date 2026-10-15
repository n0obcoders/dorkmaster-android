package org.dorkmaster

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.EditorInfo
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.viewpager2.adapter.FragmentStateAdapter
import androidx.viewpager2.widget.ViewPager2
import com.google.android.material.tabs.TabLayout
import com.google.android.material.tabs.TabLayoutMediator
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private const val BG = 0xFF0F0F14.toInt()
private const val PANEL = 0xFF1A1A21.toInt()
private const val ACCENT = 0xFF338FFF.toInt()
private const val FG = 0xFFEAEAEA.toInt()
private const val DIM = 0xFF808088.toInt()

data class SearchItem(val category: String, val query: String, val url: String)

object AppState {
    val items = mutableListOf<SearchItem>()
    val logs = mutableListOf<String>()
    var browserUrl: String? = null

    fun log(message: String) {
        val stamp = SimpleDateFormat("HH:mm:ss", Locale.US).format(Date())
        logs.add("[$stamp] $message")
    }
}

object DorkCatalog {
    // Queries are search links for manual review; the app does not crawl targets,
    // retrieve exposed files, or extract credentials/secrets.
    val templates: LinkedHashMap<String, List<String>> = linkedMapOf(
        "public_files" to listOf("site:%s filetype:pdf", "site:%s filetype:doc OR filetype:docx"),
        "documents" to listOf("site:%s (filetype:xls OR filetype:xlsx OR filetype:csv)"),
        "directories" to listOf("site:%s intitle:\"index of\""),
        "configuration_pages" to listOf("site:%s (inurl:config OR inurl:configuration)"),
        "development_docs" to listOf("site:%s (inurl:swagger OR inurl:api-docs OR intitle:\"API documentation\")"),
        "status_pages" to listOf("site:%s (inurl:status OR intitle:\"system status\")"),
        "error_pages" to listOf("site:%s (\"stack trace\" OR \"internal server error\")"),
        "technology" to listOf("site:%s (inurl:phpinfo OR intitle:\"Welcome to nginx\")"),
        "login_pages" to listOf("site:%s (inurl:login OR inurl:signin OR intitle:\"sign in\")"),
        "admin_portals" to listOf("site:%s (inurl:admin OR inurl:dashboard)"),
        "cms" to listOf("site:%s (inurl:wp-content OR inurl:wp-includes OR inurl:administrator)"),
        "sitemaps" to listOf("site:%s (inurl:sitemap.xml OR inurl:robots.txt)"),
        "subdomains" to listOf("site:*.%s"),
        "archives" to listOf("site:%s (filetype:zip OR filetype:tar OR filetype:gz)"),
        "backups" to listOf("site:%s (inurl:backup OR inurl:archive)"),
        "public_repositories" to listOf("site:github.com \"%s\"", "site:gitlab.com \"%s\""),
        "issue_trackers" to listOf("site:%s (inurl:issues OR inurl:ticket OR inurl: Jira)"),
        "cloud_references" to listOf("site:%s (amazonaws.com OR blob.core.windows.net OR storage.googleapis.com)"),
        "contact_pages" to listOf("site:%s (inurl:contact OR inurl:about OR inurl:team)"),
        "security_policy" to listOf("site:%s (inurl:security.txt OR \"responsible disclosure\" OR \"bug bounty\")")
    )

    fun generate(domain: String, selected: Set<String>): List<SearchItem> {
        val engineBase = "https://www.google.com/search?q="
        return templates.filterKeys { selected.isEmpty() || it in selected }
            .flatMap { (category, templates) ->
                templates.map { template ->
                    val query = template.replace("%s", domain)
                    SearchItem(category, query, engineBase + enc(query))
                }
            }
    }

    private fun enc(value: String) = URLEncoder.encode(value, "UTF-8")
}

class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        val pager = findViewById<ViewPager2>(R.id.viewPager)
        val tabs = findViewById<TabLayout>(R.id.tabLayout)
        pager.adapter = object : FragmentStateAdapter(this) {
            override fun getItemCount() = 4
            override fun createFragment(position: Int): Fragment = when (position) {
                0 -> ScanFragment()
                1 -> ResultsFragment()
                2 -> BrowserFragment()
                else -> LogFragment()
            }
        }
        TabLayoutMediator(tabs, pager) { tab, position ->
            tab.text = listOf("Scan", "Results", "Browser", "Log")[position]
        }.attach()
    }
}

class ScanFragment : Fragment() {
    override fun onCreateView(inflater: android.view.LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        val ctx = requireContext()
        val scroll = ScrollView(ctx).apply { setBackgroundColor(BG) }
        val root = column(ctx).apply { setPadding(dp(ctx, 14), dp(ctx, 14), dp(ctx, 14), dp(ctx, 24)) }
        scroll.addView(root)

        root.addView(TextView(ctx).apply {
            text = "DorkMaster v4.3"
            textSize = 23f
            setTextColor(ACCENT)
            setTypeface(null, android.graphics.Typeface.BOLD)
        })
        root.addView(label(ctx, "Domain to review"))
        val domain = edit(ctx, "example.com").apply {
            inputType = android.text.InputType.TYPE_CLASS_TEXT or android.text.InputType.TYPE_TEXT_VARIATION_URI
        }
        root.addView(domain)
        root.addView(label(ctx, "Search engine"))
        val engine = Spinner(ctx)
        val engines = listOf("Google", "Bing", "DuckDuckGo")
        engine.adapter = ArrayAdapter(ctx, android.R.layout.simple_spinner_dropdown_item, engines)
        root.addView(engine)

        root.addView(label(ctx, "Search categories (20)"))
        val actions = row(ctx)
        val boxes = linkedMapOf<String, CheckBox>()
        val selectAll = button(ctx, "All") { boxes.values.forEach { it.isChecked = true } }
        val clearAll = button(ctx, "None") { boxes.values.forEach { it.isChecked = false } }
        actions.addView(selectAll)
        actions.addView(clearAll)
        root.addView(actions)

        val grid = GridLayout(ctx).apply { columnCount = 2 }
        DorkCatalog.templates.keys.forEach { key ->
            val cb = CheckBox(ctx).apply {
                text = key.replace('_', ' ')
                isChecked = true
                textSize = 12f
                setTextColor(FG)
                buttonTintList = android.content.res.ColorStateList.valueOf(ACCENT)
            }
            boxes[key] = cb
            grid.addView(cb, GridLayout.LayoutParams().apply {
                width = 0
                columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f)
                setMargins(0, 0, dp(ctx, 4), 0)
            })
        }
        root.addView(grid)

        root.addView(label(ctx, "Actions"))
        val generate = Button(ctx).apply {
            text = "GENERATE SEARCH LINKS"
            setTextColor(Color.WHITE)
            setBackgroundColor(ACCENT)
        }
        root.addView(generate, LinearLayout.LayoutParams(-1, dp(ctx, 48)).apply {
            topMargin = dp(ctx, 10)
        })
        val status = label(ctx, "Ready. Choose categories and generate links.")
        root.addView(status)

        generate.setOnClickListener {
            val target = domain.text.toString().trim()
                .removePrefix("https://").removePrefix("http://").trimEnd('/')
                .substringBefore('/')
            if (target.isBlank() || !target.contains('.')) {
                status.text = "Enter a valid domain, such as example.com."
                return@setOnClickListener
            }
            val selected = boxes.filterValues { it.isChecked }.keys
            if (selected.isEmpty()) {
                status.text = "Select at least one category."
                return@setOnClickListener
            }
            AppState.items.clear()
            val generated = DorkCatalog.generate(target, selected)
            val base = when (engine.selectedItemPosition) {
                1 -> "https://www.bing.com/search?q="
                2 -> "https://html.duckduckgo.com/html/?q="
                else -> "https://www.google.com/search?q="
            }
            AppState.items.addAll(generated.map {
                it.copy(url = base + URLEncoder.encode(it.query, "UTF-8"))
            })
            AppState.log("Generated ${AppState.items.size} search links for $target")
            status.text = "Generated ${AppState.items.size} links. Open Results to review them."
            Toast.makeText(ctx, "Search links generated", Toast.LENGTH_SHORT).show()
        }
        return scroll
    }
}

class ResultsFragment : Fragment() {
    private lateinit var adapter: SearchAdapter
    private lateinit var count: TextView
    private var filter = ""

    override fun onCreateView(inflater: android.view.LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        val ctx = requireContext()
        val root = column(ctx).apply {
            setPadding(dp(ctx, 10), dp(ctx, 10), dp(ctx, 10), dp(ctx, 10))
            setBackgroundColor(BG)
        }
        val header = row(ctx)
        header.addView(TextView(ctx).apply {
            text = "Generated search links"
            textSize = 17f
            setTextColor(FG)
            layoutParams = LinearLayout.LayoutParams(0, -2, 1f)
        })
        count = label(ctx, "0 links")
        header.addView(count)
        root.addView(header)
        val search = edit(ctx, "Filter category or query").apply {
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) {
                    filter = s?.toString().orEmpty()
                    refresh()
                }
                override fun afterTextChanged(s: Editable?) {}
            })
        }
        root.addView(search)
        val list = android.widget.ListView(ctx)
        adapter = SearchAdapter(ctx) { item ->
            AppState.browserUrl = item.url
            AppState.log("Opened search link: ${item.category}")
            (activity?.findViewById<ViewPager2>(R.id.viewPager))?.currentItem = 2
        }
        list.adapter = adapter
        root.addView(list, LinearLayout.LayoutParams(-1, 0, 1f))
        refresh()
        return root
    }

    private fun refresh() {
        if (!::adapter.isInitialized) return
        val items = AppState.items.filter {
            filter.isBlank() || it.category.contains(filter, true) || it.query.contains(filter, true)
        }
        adapter.setItems(items)
        count.text = "${items.size} links"
    }
}

class SearchAdapter(
    private val context: Context,
    private val onOpen: (SearchItem) -> Unit
) : android.widget.BaseAdapter() {
    private var items: List<SearchItem> = emptyList()
    fun setItems(value: List<SearchItem>) { items = value; notifyDataSetChanged() }
    override fun getCount() = items.size
    override fun getItem(position: Int) = items[position]
    override fun getItemId(position: Int) = position.toLong()
    override fun getView(position: Int, convertView: View?, parent: ViewGroup): View {
        val item = getItem(position)
        val card = column(context).apply {
            setPadding(dp(context, 10), dp(context, 8), dp(context, 10), dp(context, 8))
            setBackgroundColor(PANEL)
        }
        card.addView(TextView(context).apply {
            text = item.category.replace('_', ' ').uppercase(Locale.US)
            textSize = 11f
            setTextColor(ACCENT)
        })
        card.addView(TextView(context).apply {
            text = item.query
            textSize = 13f
            setTextColor(FG)
            setPadding(0, dp(context, 4), 0, dp(context, 4))
        })
        val buttons = row(context)
        buttons.addView(button(context, "Open") { onOpen(item) })
        buttons.addView(button(context, "Copy query") {
            val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            clipboard.setPrimaryClip(ClipData.newPlainText("Search query", item.query))
            Toast.makeText(context, "Query copied", Toast.LENGTH_SHORT).show()
        })
        card.addView(buttons)
        return card
    }
}

class BrowserFragment : Fragment() {
    private var webView: WebView? = null
    private var address: EditText? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreateView(inflater: android.view.LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        val ctx = requireContext()
        val root = column(ctx).apply { setBackgroundColor(BG) }
        val bar = row(ctx).apply { setPadding(dp(ctx, 6), dp(ctx, 6), dp(ctx, 6), dp(ctx, 6)); setBackgroundColor(PANEL) }
        address = edit(ctx, "https://www.google.com").apply {
            layoutParams = LinearLayout.LayoutParams(0, dp(ctx, 44), 1f)
            imeOptions = EditorInfo.IME_ACTION_GO
            setSingleLine()
        }
        val go = button(ctx, "Go") { loadAddress() }
        bar.addView(address)
        bar.addView(go)
        root.addView(bar)
        val nav = row(ctx)
        nav.addView(button(ctx, "Back") { webView?.takeIf { it.canGoBack() }?.goBack() })
        nav.addView(button(ctx, "Forward") { webView?.takeIf { it.canGoForward() }?.goForward() })
        nav.addView(button(ctx, "Reload") { webView?.reload() })
        root.addView(nav)
        webView = WebView(ctx).apply {
            settings.javaScriptEnabled = false
            settings.domStorageEnabled = true
            settings.loadWithOverviewMode = true
            settings.useWideViewPort = true
            webViewClient = object : WebViewClient() {
                override fun onPageStarted(view: WebView?, url: String?, favicon: android.graphics.Bitmap?) {
                    address?.setText(url.orEmpty())
                }
            }
            webChromeClient = WebChromeClient()
        }
        root.addView(webView, LinearLayout.LayoutParams(-1, 0, 1f))
        address?.setOnEditorActionListener { _, actionId, _ ->
            if (actionId == EditorInfo.IME_ACTION_GO) { loadAddress(); true } else false
        }
        AppState.browserUrl?.let { url ->
            webView?.loadUrl(url)
            address?.setText(url)
            AppState.browserUrl = null
        }
        return root
    }

    private fun loadAddress() {
        var url = address?.text?.toString()?.trim().orEmpty()
        if (url.isBlank()) return
        if (!url.startsWith("https://") && !url.startsWith("http://")) url = "https://$url"
        if (!url.startsWith("https://") && !url.startsWith("http://")) return
        webView?.loadUrl(url)
        AppState.log("Browser opened $url")
    }

    override fun onDestroyView() {
        webView?.stopLoading()
        webView?.destroy()
        webView = null
        address = null
        super.onDestroyView()
    }
}

class LogFragment : Fragment() {
    override fun onCreateView(inflater: android.view.LayoutInflater, container: ViewGroup?, state: Bundle?): View {
        val ctx = requireContext()
        val root = column(ctx).apply {
            setPadding(dp(ctx, 10), dp(ctx, 10), dp(ctx, 10), dp(ctx, 10))
            setBackgroundColor(BG)
        }
        val header = row(ctx)
        header.addView(TextView(ctx).apply {
            text = "Activity log"
            textSize = 17f
            setTextColor(FG)
            layoutParams = LinearLayout.LayoutParams(0, -2, 1f)
        })
        header.addView(button(ctx, "Refresh") { logText.text = AppState.logs.joinToString("\\n") })
        root.addView(header)
        logText = TextView(ctx).apply {
            text = AppState.logs.joinToString("\\n")
            textSize = 12f
            setTextColor(FG)
            typeface = android.graphics.Typeface.MONOSPACE
            setPadding(dp(ctx, 4), dp(ctx, 8), dp(ctx, 4), dp(ctx, 8))
        }
        val scroll = ScrollView(ctx)
        scroll.addView(logText)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(button(ctx, "Clear log") {
            AppState.logs.clear()
            logText.text = ""
        })
        return root
    }

    private lateinit var logText: TextView
}

private fun column(ctx: Context) = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL }
private fun row(ctx: Context) = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
private fun dp(ctx: Context, value: Int) = (value * ctx.resources.displayMetrics.density).toInt()

private fun label(ctx: Context, value: String) = TextView(ctx).apply {
    text = value
    textSize = 12f
    setTextColor(DIM)
    setPadding(0, dp(ctx, 8), 0, dp(ctx, 4))
}

private fun edit(ctx: Context, hintText: String) = EditText(ctx).apply {
    hint = hintText
    textSize = 14f
    setTextColor(FG)
    setHintTextColor(DIM)
    setPadding(dp(ctx, 10), dp(ctx, 8), dp(ctx, 10), dp(ctx, 8))
    setBackgroundColor(PANEL)
    layoutParams = LinearLayout.LayoutParams(-1, dp(ctx, 44)).apply {
        bottomMargin = dp(ctx, 4)
    }
}

private fun button(ctx: Context, title: String, action: () -> Unit) = Button(ctx).apply {
    text = title
    textSize = 12f
    setTextColor(Color.WHITE)
    setBackgroundColor(ACCENT)
    setOnClickListener { action() }
    layoutParams = LinearLayout.LayoutParams(
        ViewGroup.LayoutParams.WRAP_CONTENT, dp(ctx, 40)
    ).apply { rightMargin = dp(ctx, 5); bottomMargin = dp(ctx, 4) }
}
