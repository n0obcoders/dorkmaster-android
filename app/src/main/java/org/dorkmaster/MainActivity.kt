package org.dorkmaster

import android.annotation.SuppressLint
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.graphics.Color
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.*
import android.webkit.*
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.adapter.FragmentStateAdapter
import androidx.viewpager2.widget.ViewPager2
import com.google.android.material.tabs.TabLayout
import com.google.android.material.tabs.TabLayoutMediator
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Semaphore
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.net.URLDecoder
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.*
import java.util.concurrent.TimeUnit
import kotlin.random.Random

data class Finding(
    val severity: String, val category: String, val title: String,
    val url: String, val evidence: String = "", val secrets: List<String> = emptyList()
) {
    fun severityRank() = when (severity) { "critical"->4;"high"->3;"medium"->2;"low"->1;else->0 }
    fun severityColor() = when (severity) {
        "critical" -> Color.parseColor("#FF4040"); "high" -> Color.parseColor("#FF8C1A")
        "medium"   -> Color.parseColor("#FFCC1A"); "low"  -> Color.parseColor("#33CC77")
        else -> Color.parseColor("#808088")
    }
}

object Dorks {
    private fun s(d: String) = "site:$d"
    val categories: Map<String, (String) -> List<String>> = linkedMapOf(
        "credentials" to { d -> listOf("${s(d)} filetype:txt intext:\"username\" intext:\"password\"","${s(d)} filetype:cfg intext:\"password\"","${s(d)} filetype:yml intext:\"password\"","${s(d)} filetype:json intext:\"password\"","${s(d)} filetype:ini intext:\"password=\"","${s(d)} inurl:\"/.htpasswd\"","${s(d)} intitle:\"index of\" \"shadow\"","${s(d)} filetype:sh intext:\"password=\"","${s(d)} filetype:ps1 intext:\"password\"","intext:\"username\" intext:\"password\" intext:\"$d\" filetype:txt") },
        "logs"        to { d -> listOf("${s(d)} intitle:\"index of\" \"access.log\"","${s(d)} intitle:\"index of\" \"error.log\"","${s(d)} filetype:log intext:\"password\"","${s(d)} filetype:log intext:\"Authorization\"","${s(d)} filetype:log intext:\"bearer\"","${s(d)} filetype:log intext:\"api_key\"","${s(d)} filetype:log intext:\"token\"","${s(d)} intitle:\"index of\" \"debug.log\"","${s(d)} intitle:\"index of\" \"laravel.log\"","${s(d)} intitle:\"index of\" \"audit.log\"") },
        "databases"   to { d -> listOf("${s(d)} filetype:sql intext:\"INSERT INTO\" intext:\"password\"","${s(d)} intitle:\"index of\" filetype:sql","${s(d)} inurl:\"/phpmyadmin/\"","${s(d)} inurl:adminer.php intitle:\"Login\"","${s(d)} filetype:mdb inurl:\".mdb\"","${s(d)} filetype:sqlite inurl:\".sqlite\"","${s(d)} inurl:\":9200/_cat/indices\"","${s(d)} inurl:\":27017\" intitle:\"mongo\"","${s(d)} inurl:\":6379\" intitle:\"redis\"","${s(d)} intitle:\"index of\" \"database.sql\"") },
        "git"         to { d -> listOf("${s(d)} intitle:\"index of\" \".git\"","${s(d)} inurl:\"/.git/config\" intext:\"url =\"","${s(d)} inurl:\"/.git/HEAD\" intext:\"ref:\"","${s(d)} intitle:\"index of\" \".git/logs\"","${s(d)} inurl:\"/.git/COMMIT_EDITMSG\"","${s(d)} inurl:\"/.git/packed-refs\"","${s(d)} intitle:\"index of\" \".svn\"","${s(d)} intitle:\"index of\" \".hg\"","intitle:\"index of\" \".git\" \"$d\"") },
        "env"         to { d -> listOf("${s(d)} filetype:env intext:\"DB_PASSWORD\"","${s(d)} inurl:\".env\" intext:\"APP_KEY\"","${s(d)} inurl:\".env.production\"","${s(d)} filetype:env \"AWS_SECRET_ACCESS_KEY\"","${s(d)} filetype:env \"AWS_ACCESS_KEY_ID\"","${s(d)} filetype:env \"STRIPE_SECRET\"","${s(d)} filetype:env \"OPENAI_API_KEY\"","${s(d)} filetype:env \"ANTHROPIC_API_KEY\"","${s(d)} filetype:env \"GITHUB_TOKEN\"","${s(d)} filetype:env \"SECRET_KEY\"","${s(d)} filetype:env \"DATABASE_URL\"","${s(d)} filetype:env \"PRIVATE_KEY\"","${s(d)} inurl:\"/.env\" -filetype:php") },
        "backups"     to { d -> listOf("${s(d)} filetype:bak inurl:\"wp-config\"","${s(d)} intitle:\"index of\" \"backup.zip\"","${s(d)} intitle:\"index of\" \"backup.tar.gz\"","${s(d)} filetype:zip inurl:\"backup\"","${s(d)} inurl:\".bak\" filetype:bak","${s(d)} inurl:\".swp\"","${s(d)} intitle:\"index of\" \"database.bak\"") },
        "admin"       to { d -> listOf("${s(d)} inurl:admin intitle:\"login\"","${s(d)} inurl:/wp-admin/ intitle:\"WordPress\"","${s(d)} inurl:\"/jenkins\" intitle:\"Dashboard\"","${s(d)} inurl:grafana intitle:\"Grafana\"","${s(d)} inurl:kibana intitle:\"Kibana\"","${s(d)} inurl:\":9090\" intitle:\"Prometheus\"","${s(d)} inurl:\":3000\" intitle:\"Grafana\"","${s(d)} inurl:\":15672\" intitle:\"RabbitMQ\"","${s(d)} inurl:\":8888\" intitle:\"Jupyter\"","${s(d)} intitle:\"RabbitMQ Management\"") },
        "cloud"       to { d -> listOf("site:s3.amazonaws.com inurl:$d","site:blob.core.windows.net inurl:$d","site:storage.googleapis.com inurl:$d","filetype:json intext:\"aws_access_key_id\"","${s(d)} intext:\"s3.amazonaws.com\" intext:\"bucket\"","${s(d)} intext:\"blob.core.windows.net\"","${s(d)} intext:\"digitaloceanspaces.com\"") },
        "s3"          to { d -> listOf("site:s3.amazonaws.com \"${d.replace(".","-")}\"","site:s3.amazonaws.com \"${d.replace(".","-")}-backup\"","site:s3.amazonaws.com \"${d.replace(".","-")}-prod\"","site:s3.amazonaws.com \"${d.replace(".","-")}-dev\"","site:s3.amazonaws.com \"${d.replace(".","-")}-uploads\"","site:storage.googleapis.com \"${d.replace(".","-")}\"","site:blob.core.windows.net \"${d.replace(".","-")}\"") },
        "apikeys"     to { d -> listOf("${s(d)} filetype:js intext:\"api_key\"","${s(d)} filetype:js intext:\"AIza\"","${s(d)} filetype:js intext:\"AKIA\"","${s(d)} filetype:js intext:\"pk_live_\"","${s(d)} filetype:js intext:\"eyJ\"","${s(d)} filetype:json intext:\"apiKey\"","${s(d)} inurl:\"config.js\"","${s(d)} inurl:\"service-account.json\"","${s(d)} inurl:\"google-services.json\"","${s(d)} inurl:\"secrets.yml\"") },
        "pastebin"    to { d -> listOf("site:pastebin.com \"$d\"","site:pastebin.com \"$d\" password","site:pastebin.com \"$d\" token","site:pastebin.com \"$d\" DB_PASSWORD","site:ghostbin.co \"$d\"","site:rentry.co \"$d\"","\"$d\" site:pastebin.com") },
        "github"      to { d -> listOf("site:github.com \"$d\" password","site:github.com \"$d\" api_key","site:github.com \"$d\" .env","site:github.com \"$d\" DB_PASSWORD","site:github.com \"$d\" AWS_SECRET_ACCESS_KEY","site:github.com \"$d\" private_key","site:gitlab.com \"$d\" password","site:gist.github.com \"$d\"","site:bitbucket.org \"$d\" password") },
        "jira"        to { d -> listOf("${s(d)} inurl:/jira/ intext:\"issue\"","${s(d)} inurl:\"/confluence/\" intext:\"spaces\"","${s(d)} inurl:\"/servicedesk/\"","${s(d)} intitle:\"Dashboard - Jira\"","site:*.atlassian.net \"$d\"","site:*.atlassian.net \"$d\" password") },
        "cms"         to { d -> listOf("${s(d)} inurl:wp-config.php.bak","${s(d)} inurl:\"/wp-json/wp/v2/users\"","${s(d)} inurl:xmlrpc.php","${s(d)} inurl:wp-login.php","${s(d)} inurl:\"/administrator/index.php\" intitle:\"Joomla\"","${s(d)} inurl:\"/sites/default/settings.php\" intitle:\"Drupal\"","${s(d)} inurl:\"/ghost/\" intitle:\"Ghost\"") },
        "network"     to { d -> listOf("${s(d)} intitle:\"webcamXP\" inurl:8080","${s(d)} intitle:\"Live View / - AXIS\"","${s(d)} intitle:\"Hikvision\" inurl:login","${s(d)} inurl:\":10000\" intitle:\"Webmin\"","${s(d)} intitle:\"TP-LINK\" inurl:admin","${s(d)} intitle:\"pfSense\" inurl:index.php","${s(d)} intitle:\"OpenWrt\" inurl:cgi-bin") },
        "stealer"     to { d -> listOf("${s(d)} intitle:\"index of\" \"stealer\" filetype:txt","${s(d)} intitle:\"index of\" \"combolist\"","${s(d)} filetype:txt intext:\"URL:\" intext:\"USER:\" intext:\"PASS:\"","${s(d)} filetype:txt intext:\"@gmail.com\" intext:\"password\"","intext:\"$d\" intext:\"password\" filetype:txt -site:$d","\"$d\" \"password\" filetype:txt") },
        "emails"      to { d -> listOf("${s(d)} intext:\"@$d\" filetype:txt","${s(d)} intext:\"@$d\" filetype:csv","${s(d)} intitle:\"index of\" \"email\" filetype:txt","${s(d)} intitle:\"index of\" \"contacts\" filetype:csv","\"$d\" intext:\"@\" filetype:csv","site:linkedin.com/in \"$d\"") },
        "errors"      to { d -> listOf("${s(d)} intext:\"Fatal error\"","${s(d)} intext:\"Stack trace\"","${s(d)} intext:\"Traceback (most recent call last)\"","${s(d)} inurl:\"phpinfo.php\"","${s(d)} inurl:\"/actuator/env\"","${s(d)} inurl:\"/actuator/heapdump\"","${s(d)} intitle:\"Whoops!\" intext:\"Laravel\"","${s(d)} intitle:\"Werkzeug\" intext:\"Traceback\"") },
        "xmlrpc"      to { d -> listOf("${s(d)} inurl:\"xmlrpc.php\"","${s(d)} inurl:\"/swagger-ui.html\"","${s(d)} inurl:\"/api-docs\"","${s(d)} intitle:\"Swagger UI\"","${s(d)} inurl:\"?wsdl\"","${s(d)} inurl:\"/rest/api/\"","${s(d)} inurl:\"/wp-json/wp/v2/users\"") }
    )
    fun generate(domain: String, cats: Set<String>): List<String> {
        val all = mutableListOf<String>()
        for ((cat, fn) in categories) { if (cats.isEmpty() || cat in cats) all += fn(domain) }
        return all.distinct()
    }
}

object SecretScanner {
    private val patterns = listOf(
        "AWS_KEY"         to Regex("AKIA[0-9A-Z]{16}"),
        "GCP_KEY"         to Regex("AIza[0-9A-Za-z\\-_]{35}"),
        "GITHUB_TOKEN"    to Regex("ghp_[a-zA-Z0-9]{36}"),
        "GITLAB_TOKEN"    to Regex("glpat-[a-zA-Z0-9_\\-]{20,}"),
        "STRIPE_SECRET"   to Regex("sk_live_[a-zA-Z0-9]{24,}"),
        "OPENAI_KEY"      to Regex("sk-proj-[a-zA-Z0-9_\\-]{40,}"),
        "ANTHROPIC_KEY"   to Regex("sk-ant-[a-zA-Z0-9_\\-]{40,}"),
        "SLACK_TOKEN"     to Regex("xox[baprs]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]+"),
        "DISCORD_WEBHOOK" to Regex("https://discord\\.com/api/webhooks/\\d+/[a-zA-Z0-9_\\-]+"),
        "SENDGRID_KEY"    to Regex("SG\\.[a-zA-Z0-9\\-_]{22}\\.[a-zA-Z0-9\\-_]{43}"),
        "PRIVATE_KEY"     to Regex("-----BEGIN RSA PRIVATE KEY-----"),
        "DB_PASSWORD"     to Regex("DB_PASS(?:WORD)?\\s*[=:]\\s*\\S+"),
        "DATABASE_URL"    to Regex("(?:mysql|postgres|mongodb|redis)://[^\\s\"']+"),
        "JWT"             to Regex("eyJ[a-zA-Z0-9\\-_]+\\.[a-zA-Z0-9\\-_]+\\.[a-zA-Z0-9\\-_]+"),
        "BEARER"          to Regex("Bearer\\s+[a-zA-Z0-9\\-_.]{20,}"),
        "SECRET_GENERIC"  to Regex("(?i)(?:secret[_\\-]?key|api[_\\-]?key)\\s*[=:]\\s*[\"']?([a-zA-Z0-9\\-_]{16,})")
    )
    fun scan(text: String): List<String> {
        val hits = mutableListOf<String>(); val seen = mutableSetOf<String>()
        for ((name, pat) in patterns) for (m in pat.findAll(text)) { val v = "$name: ${m.value.take(80)}"; if (seen.add(v)) hits.add(v) }
        return hits
    }
}

object ScanState {
    val findings = mutableListOf<Finding>()
    val urls     = mutableListOf<String>()
    val logs     = mutableListOf<String>()
    var running  = false
    var job: Job? = null

    private val findingListeners = mutableMapOf<String, (Finding) -> Unit>()
    private val urlListeners     = mutableMapOf<String, (String)  -> Unit>()
    private val logListeners     = mutableMapOf<String, (String)  -> Unit>()
    private val doneListeners    = mutableMapOf<String, ()        -> Unit>()

    fun addFindingListener(key: String, l: (Finding) -> Unit) { findingListeners[key] = l }
    fun addUrlListener    (key: String, l: (String)  -> Unit) { urlListeners[key]     = l }
    fun addLogListener    (key: String, l: (String)  -> Unit) { logListeners[key]     = l }
    fun addDoneListener   (key: String, l: ()        -> Unit) { doneListeners[key]    = l }
    fun removeListeners   (key: String) { findingListeners.remove(key); urlListeners.remove(key); logListeners.remove(key); doneListeners.remove(key) }

    fun reset() { findings.clear(); urls.clear(); logs.clear() }
    fun emitFinding(f: Finding) { findings.add(f);    findingListeners.values.forEach { it(f) } }
    fun emitUrl    (u: String)  { if (u !in urls) { urls.add(u); urlListeners.values.forEach { it(u) } } }
    fun emitLog    (m: String)  { logs.add(m);        logListeners.values.forEach    { it(m) } }
    fun emitDone   ()           { running = false;    doneListeners.values.forEach   { it()  } }
}

object HttpEngine {
    private val UAS = listOf(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36"
    )
    fun client(proxyUrl: String? = null): OkHttpClient {
        val b = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .followRedirects(true)
        if (!proxyUrl.isNullOrBlank()) {
            try {
                val uri  = java.net.URI(proxyUrl.trim())
                val type = if (uri.scheme.startsWith("socks")) java.net.Proxy.Type.SOCKS else java.net.Proxy.Type.HTTP
                val addr = java.net.InetSocketAddress(uri.host, uri.port)
                b.proxy(java.net.Proxy(type, addr))
            } catch (_: Exception) {}
        }
        return b.build()
    }
    fun get(client: OkHttpClient, url: String): String? = try {
        val req = Request.Builder().url(url)
            .header("User-Agent", UAS.random())
            .header("Accept", "text/html,*/*;q=0.8")
            .header("DNT", "1").build()
        client.newCall(req).execute().use { if (it.isSuccessful) it.body?.string() else null }
    } catch (_: Exception) { null }
}

object Scrapers {
    private val CAPTCHA = listOf("detected unusual traffic", "recaptcha", "captcha", "/sorry/")
    private fun isCaptcha(b: String) = CAPTCHA.any { it in b.lowercase() }

    fun google(client: OkHttpClient, query: String, pages: Int = 2): List<String> {
        val urls = mutableListOf<String>()
        for (page in 0 until pages) {
            val p = "q=${URLEncoder.encode(query, "UTF-8")}&start=${page * 10}&num=10&hl=en&safe=off"
            val body = HttpEngine.get(client, "https://www.google.com/search?$p") ?: break
            if (isCaptcha(body)) { Thread.sleep(3000); continue }
            Regex("/url\\?q=(https?://[^&\"'<> ]+)").findAll(body).forEach {
                val u = URLDecoder.decode(it.groupValues[1], "UTF-8")
                if (!listOf("google.com", "googleadservices", "webcache").any { s -> s in u }) urls.add(u)
            }
            if ("did not match" in body.lowercase()) break
        }
        return urls.distinct()
    }

    fun bing(client: OkHttpClient, query: String, pages: Int = 2): List<String> {
        val urls = mutableListOf<String>()
        for (page in 0 until pages) {
            val p = "q=${URLEncoder.encode(query, "UTF-8")}&first=${page * 10 + 1}&count=10"
            val body = HttpEngine.get(client, "https://www.bing.com/search?$p") ?: break
            val found = Regex("<h2[^>]*>\\s*<a[^>]+href=[\"']?(https?://[^\"'<> ]+)[\"']?", RegexOption.IGNORE_CASE)
                .findAll(body).map { it.groupValues[1] }
                .filter { !listOf("bing.com", "microsoft.com").any { s -> s in it } }.toList()
            urls += found; if (found.isEmpty()) break
        }
        return urls.distinct()
    }

    fun ddg(client: OkHttpClient, query: String): List<String> {
        val body = try {
            val form = "q=${URLEncoder.encode(query, "UTF-8")}&b=&kl=us-en"
            val rb   = form.toRequestBody("application/x-www-form-urlencoded".toMediaType())
            val req  = Request.Builder().url("https://html.duckduckgo.com/html/")
                .header("User-Agent", "Mozilla/5.0").post(rb).build()
            client.newCall(req).execute().use { it.body?.string() }
        } catch (_: Exception) { null } ?: return emptyList()
        return Regex("uddg=([^&\"'<> ]+)").findAll(body)
            .map { URLDecoder.decode(it.groupValues[1], "UTF-8") }.toList().distinct()
    }
}

object Engine {
    fun start(domain: String, engines: Set<String>, categories: Set<String>, proxy: String?, delay: Long, pages: Int, scope: CoroutineScope) {
        ScanState.running = true
        ScanState.job = scope.launch(Dispatchers.IO) {
            val client  = HttpEngine.client(proxy)
            val queries = Dorks.generate(domain, categories)
            ScanState.emitLog("Generated ${queries.size} queries across ${categories.size.takeIf { it > 0 } ?: Dorks.categories.size} categories")
            val sem  = Semaphore(6)
            val jobs = queries.map { query ->
                launch {
                    sem.acquire()
                    try {
                        if (!isActive) return@launch
                        delay(delay + Random.nextLong(-500, 500))
                        val found = mutableListOf<String>()
                        if ("google" in engines) found += Scrapers.google(client, query, pages)
                        if ("bing"   in engines) found += Scrapers.bing  (client, query, pages)
                        if ("ddg"    in engines) found += Scrapers.ddg   (client, query)
                        found.distinct().forEach { ScanState.emitUrl(it) }
                    } finally { sem.release() }
                }
            }
            jobs.forEach { it.join() }
            ScanState.emitLog("Dork phase done — ${ScanState.urls.size} URLs")

            // .env probing
            ScanState.urls.filter { ".env" in it.lowercase() }.take(10).forEach { url ->
                if (!isActive) return@forEach
                val content = try {
                    val req = Request.Builder().url(url).header("User-Agent","Mozilla/5.0").build()
                    client.newCall(req).execute().use { it.body?.string() ?: "" }
                } catch (_: Exception) { "" }
                if (content.isNotEmpty()) {
                    val hits = SecretScanner.scan(content)
                    ScanState.emitFinding(Finding(
                        severity = if (hits.isNotEmpty()) "critical" else "medium",
                        category = "env_exposure",
                        title    = ".env exposed" + if (hits.isNotEmpty()) " — ${hits.size} secrets" else "",
                        url = url, evidence = content.take(500), secrets = hits
                    ))
                }
            }

            // .git probing
            ScanState.urls.filter { ".git" in it }.take(5).forEach { url ->
                if (!isActive) return@forEach
                val base = if ("/.git/" in url) url.substringBefore("/.git/") + "/.git" else url.trimEnd('/') + "/.git"
                for (gf in listOf("HEAD", "config", "COMMIT_EDITMSG")) {
                    val text = try {
                        val req = Request.Builder().url("$base/$gf").header("User-Agent","Mozilla/5.0").build()
                        client.newCall(req).execute().use { if (it.isSuccessful) it.body?.string() else null }
                    } catch (_: Exception) { null }
                    if (!text.isNullOrBlank() && text.length > 10) {
                        val hits = SecretScanner.scan(text)
                        ScanState.emitFinding(Finding(
                            severity = if (hits.isNotEmpty()) "critical" else "high",
                            category = "git_exposure",
                            title    = "Exposed .git/$gf" + if (hits.isNotEmpty()) " — ${hits.size} secrets" else "",
                            url = url, evidence = text.take(500), secrets = hits
                        ))
                        break
                    }
                }
            }

            ScanState.emitLog("Probe done — ${ScanState.findings.size} findings total")
            ScanState.emitDone()
        }
    }
    fun stop() { ScanState.job?.cancel(); ScanState.running = false }
}

// ─── Activity ────────────────────────────────────────────────────────────────

class MainActivity : AppCompatActivity() {
    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        setContentView(R.layout.activity_main)
        val pager = findViewById<ViewPager2>(R.id.viewPager)
        val tabs  = findViewById<TabLayout>(R.id.tabLayout)
        val titles = listOf("Scan", "Findings", "Browser", "URLs", "Log")
        pager.adapter = object : FragmentStateAdapter(this) {
            override fun getItemCount() = 5
            override fun createFragment(pos: Int): Fragment = when (pos) {
                0 -> ScanFragment(); 1 -> FindingsFragment(); 2 -> BrowserFragment()
                3 -> UrlsFragment(); else -> LogFragment()
            }
        }
        pager.isUserInputEnabled = true
        TabLayoutMediator(tabs, pager) { tab, pos -> tab.text = titles[pos] }.attach()
    }
}

// ─── Scan fragment ────────────────────────────────────────────────────────────

class ScanFragment : Fragment() {
    private val scope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, b: Bundle?): View {
        val ctx = requireContext()
        val scroll = ScrollView(ctx).apply { setBackgroundColor(Color.parseColor("#0F0F14")) }
        val root   = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(14), dp(14), dp(14), dp(14)) }
        scroll.addView(root)

        root.addView(TextView(ctx).apply { text = "DorkMaster v4.3"; setTextColor(Color.parseColor("#338FFF")); textSize = 22f; setTypeface(null, android.graphics.Typeface.BOLD); setPadding(0, 0, 0, dp(8)) })
        root.addView(TextView(ctx).apply { text = "Target Domain"; setTextColor(Color.parseColor("#808088")); textSize = 12f })

        val domainEt = EditText(ctx).apply { hint = "example.com"; setTextColor(Color.parseColor("#EAEAEA")); setHintTextColor(Color.parseColor("#808088")); setBackgroundColor(Color.parseColor("#1A1A21")); setPadding(dp(10), dp(10), dp(10), dp(10)); textSize = 14f; setSingleLine() }
        root.addView(domainEt)

        root.addView(TextView(ctx).apply { text = "Engines"; setTextColor(Color.parseColor("#808088")); textSize = 12f; setPadding(0, dp(8), 0, dp(4)) })
        val engRow = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
        val cbG = CheckBox(ctx).apply { text = "Google"; isChecked = true; setTextColor(Color.WHITE) }
        val cbB = CheckBox(ctx).apply { text = "Bing";   setTextColor(Color.WHITE) }
        val cbD = CheckBox(ctx).apply { text = "DDG";    setTextColor(Color.WHITE) }
        listOf(cbG, cbB, cbD).forEach { engRow.addView(it) }
        root.addView(engRow)

        root.addView(TextView(ctx).apply { text = "Categories"; setTextColor(Color.parseColor("#808088")); textSize = 12f; setPadding(0, dp(8), 0, dp(4)) })
        val catBoxes = mutableListOf<CheckBox>()
        val grid = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL }
        val catList = Dorks.categories.keys.toList()
        for (row in catList.chunked(3)) {
            val rowLayout = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 3f }
            for (cat in row) {
                val cb = CheckBox(ctx).apply { text = cat; isChecked = true; setTextColor(Color.WHITE); textSize = 11f; layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f) }
                catBoxes.add(cb); rowLayout.addView(cb)
            }
            grid.addView(rowLayout)
        }
        root.addView(grid)

        val selRow = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL }
        selRow.addView(Button(ctx).apply { text = "All";  setBackgroundColor(Color.parseColor("#1A1A21")); setTextColor(Color.parseColor("#338FFF")); textSize = 12f; setOnClickListener { catBoxes.forEach { it.isChecked = true  } } })
        selRow.addView(Button(ctx).apply { text = "None"; setBackgroundColor(Color.parseColor("#1A1A21")); setTextColor(Color.parseColor("#338FFF")); textSize = 12f; setOnClickListener { catBoxes.forEach { it.isChecked = false } } })
        root.addView(selRow)

        root.addView(TextView(ctx).apply { text = "Proxy (optional)"; setTextColor(Color.parseColor("#808088")); textSize = 12f; setPadding(0, dp(8), 0, dp(4)) })
        val proxyEt = EditText(ctx).apply { hint = "socks5h://127.0.0.1:9050"; setTextColor(Color.parseColor("#EAEAEA")); setHintTextColor(Color.parseColor("#808088")); setBackgroundColor(Color.parseColor("#1A1A21")); setPadding(dp(10), dp(8), dp(10), dp(8)); textSize = 13f; setSingleLine() }
        root.addView(proxyEt)

        val btnRow  = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 2f; setPadding(0, dp(10), 0, 0) }
        val scanBtn = Button(ctx).apply { text = "SCAN"; setBackgroundColor(Color.parseColor("#338FFF")); setTextColor(Color.WHITE); textSize = 14f; layoutParams = LinearLayout.LayoutParams(0, dp(48), 1f).apply { rightMargin = dp(6) } }
        val stopBtn = Button(ctx).apply { text = "STOP"; setBackgroundColor(Color.parseColor("#FF3333")); setTextColor(Color.WHITE); textSize = 14f; isEnabled = false; layoutParams = LinearLayout.LayoutParams(0, dp(48), 1f) }
        btnRow.addView(scanBtn); btnRow.addView(stopBtn); root.addView(btnRow)

        val statusTv = TextView(ctx).apply { text = "idle"; setTextColor(Color.parseColor("#808088")); textSize = 12f; setPadding(0, dp(6), 0, 0) }
        root.addView(statusTv)

        scanBtn.setOnClickListener {
            val domain = domainEt.text.toString().trim().removePrefix("https://").removePrefix("http://").trimEnd('/')
            if (domain.isEmpty()) { statusTv.text = "enter a domain first"; return@setOnClickListener }
            val engs = buildSet<String> { if (cbG.isChecked) add("google"); if (cbB.isChecked) add("bing"); if (cbD.isChecked) add("ddg") }.ifEmpty { setOf("google") }
            val cats = catBoxes.filter { it.isChecked }.map { it.text.toString() }.toSet()
            val proxy = proxyEt.text.toString().trim().ifEmpty { null }
            ScanState.reset()
            statusTv.text = "scanning..."
            scanBtn.isEnabled = false; stopBtn.isEnabled = true
            ScanState.addDoneListener("scan_frag") {
                requireActivity().runOnUiThread {
                    statusTv.text = "done — ${ScanState.urls.size} URLs  ${ScanState.findings.size} findings"
                    scanBtn.isEnabled = true; stopBtn.isEnabled = false
                }
            }
            Engine.start(domain, engs, cats, proxy, 3000L, 2, scope)
        }
        stopBtn.setOnClickListener { Engine.stop(); statusTv.text = "stopped"; scanBtn.isEnabled = true; stopBtn.isEnabled = false }
        return scroll
    }

    override fun onDestroyView() { super.onDestroyView(); ScanState.removeListeners("scan_frag"); scope.cancel() }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}

// ─── Findings fragment ────────────────────────────────────────────────────────

class FindingsFragment : Fragment() {
    private lateinit var adapter: FindingsAdapter
    private var allFindings = listOf<Finding>()

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, b: Bundle?): View {
        val ctx  = requireContext()
        val root = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor("#0F0F14")); setPadding(dp(10), dp(10), dp(10), dp(10)) }

        val statsTv = TextView(ctx).apply { text = "Findings"; setTextColor(Color.parseColor("#EAEAEA")); textSize = 16f; setTypeface(null, android.graphics.Typeface.BOLD) }
        root.addView(statsTv)
        val countTv = TextView(ctx).apply { text = ""; setTextColor(Color.parseColor("#808088")); textSize = 12f }
        root.addView(countTv)

        val filterEt = EditText(ctx).apply { hint = "filter..."; textSize = 12f; setTextColor(Color.parseColor("#EAEAEA")); setHintTextColor(Color.parseColor("#808088")); setBackgroundColor(Color.parseColor("#1A1A21")); setPadding(dp(10), dp(6), dp(10), dp(6)); setSingleLine() }
        root.addView(filterEt, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(38)).apply { bottomMargin = dp(6) })

        val rv = RecyclerView(ctx).apply { layoutManager = LinearLayoutManager(ctx) }
        adapter = FindingsAdapter { url ->
            activity?.let { act ->
                BrowserFragment.pendingUrl = url
                act.findViewById<ViewPager2>(R.id.viewPager).currentItem = 2
            }
        }
        rv.adapter = adapter
        root.addView(rv, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        // load existing
        allFindings = ScanState.findings.toList()
        adapter.setData(allFindings)
        countTv.text = "${allFindings.size} findings"

        ScanState.addFindingListener("findings_frag") { _ ->
            activity?.runOnUiThread {
                allFindings = ScanState.findings.toList()
                adapter.setData(allFindings)
                countTv.text = "${allFindings.size} findings"
            }
        }

        filterEt.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                val kw = s.toString().lowercase()
                adapter.setData(if (kw.isEmpty()) allFindings else allFindings.filter { kw in it.title.lowercase() || kw in it.url.lowercase() || kw in it.severity || kw in it.category })
            }
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
        })
        return root
    }

    override fun onDestroyView() { super.onDestroyView(); ScanState.removeListeners("findings_frag") }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}

class FindingsAdapter(private val onOpen: (String) -> Unit) : RecyclerView.Adapter<FindingsAdapter.VH>() {
    private var data = listOf<Finding>()
    fun setData(d: List<Finding>) { data = d.sortedByDescending { it.severityRank() }; notifyDataSetChanged() }

    inner class VH(val root: LinearLayout) : RecyclerView.ViewHolder(root) {
        val sevTv   = TextView(root.context)
        val titleTv = TextView(root.context)
        val urlTv   = TextView(root.context)
        val openBtn = Button(root.context)
        val copyBtn = Button(root.context)
        init {
            root.orientation = LinearLayout.VERTICAL; root.setPadding(dp(12), dp(8), dp(12), dp(8))
            root.setBackgroundColor(Color.parseColor("#1A1A21"))
            root.layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { bottomMargin = dp(6) }
            sevTv.textSize = 11f; sevTv.setTypeface(null, android.graphics.Typeface.BOLD)
            titleTv.textSize = 13f; titleTv.setTextColor(Color.parseColor("#EAEAEA"))
            urlTv.textSize = 10f; urlTv.setTextColor(Color.parseColor("#808088")); urlTv.maxLines = 1
            val btnRow = LinearLayout(root.context).apply { orientation = LinearLayout.HORIZONTAL; weightSum = 2f }
            openBtn.text = "Open"; openBtn.setBackgroundColor(Color.parseColor("#338FFF")); openBtn.setTextColor(Color.WHITE); openBtn.textSize = 10f; openBtn.layoutParams = LinearLayout.LayoutParams(0, dp(28), 1f).apply { rightMargin = dp(4) }
            copyBtn.text = "Copy"; copyBtn.setBackgroundColor(Color.parseColor("#1A1A21")); copyBtn.setTextColor(Color.parseColor("#338FFF")); copyBtn.textSize = 10f; copyBtn.layoutParams = LinearLayout.LayoutParams(0, dp(28), 1f)
            btnRow.addView(openBtn); btnRow.addView(copyBtn)
            root.addView(sevTv); root.addView(titleTv); root.addView(urlTv); root.addView(btnRow)
        }
        fun dp(v: Int) = (v * root.context.resources.displayMetrics.density).toInt()
    }

    override fun onCreateViewHolder(p: ViewGroup, t: Int) = VH(LinearLayout(p.context))
    override fun getItemCount() = data.size
    override fun onBindViewHolder(h: VH, pos: Int) {
        val f = data[pos]
        h.sevTv.text  = "${f.severity.uppercase()} | ${f.category}"; h.sevTv.setTextColor(f.severityColor())
        h.titleTv.text = f.title.take(65); h.urlTv.text = f.url.take(80)
        h.openBtn.setOnClickListener { onOpen(f.url) }
        h.copyBtn.setOnClickListener {
            val cm = h.root.context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
            cm.setPrimaryClip(ClipData.newPlainText("url", f.url))
            Toast.makeText(h.root.context, "Copied", Toast.LENGTH_SHORT).show()
        }
    }
}

// ─── Browser fragment ─────────────────────────────────────────────────────────

class BrowserFragment : Fragment() {
    private var webView: WebView? = null
    companion object { var pendingUrl: String? = null }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, b: Bundle?): View {
        val ctx  = requireContext()
        val root = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor("#0F0F14")) }

        val barRow = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL; setPadding(dp(8), dp(6), dp(8), dp(6)); setBackgroundColor(Color.parseColor("#1A1A21")) }
        val urlBar = EditText(ctx).apply { hint = "https://..."; textSize = 13f; setTextColor(Color.parseColor("#EAEAEA")); setHintTextColor(Color.parseColor("#808088")); setBackgroundColor(Color.TRANSPARENT); setSingleLine(); layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f) }
        val goBtn  = Button(ctx).apply { text = "Go"; setBackgroundColor(Color.parseColor("#338FFF")); setTextColor(Color.WHITE); textSize = 12f; layoutParams = LinearLayout.LayoutParams(dp(50), dp(36)) }
        barRow.addView(urlBar); barRow.addView(goBtn); root.addView(barRow)

        val navRow   = LinearLayout(ctx).apply { orientation = LinearLayout.HORIZONTAL; setPadding(dp(8), dp(2), dp(8), dp(2)); setBackgroundColor(Color.parseColor("#1A1A21")) }
        fun navBtn(l: String) = Button(ctx).apply { text = l; textSize = 11f; setBackgroundColor(Color.parseColor("#0F0F14")); setTextColor(Color.parseColor("#338FFF")); layoutParams = LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, dp(32)).apply { rightMargin = dp(4) } }
        val backBtn   = navBtn("< Back")
        val fwdBtn    = navBtn("Fwd >")
        val reloadBtn = navBtn("Reload")
        val titleTv   = TextView(ctx).apply { text = "Browser"; setTextColor(Color.parseColor("#808088")); textSize = 11f; maxLines = 1; layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f) }
        listOf(backBtn, fwdBtn, reloadBtn, titleTv).forEach { navRow.addView(it) }
        root.addView(navRow)

        val progress = ProgressBar(ctx, null, android.R.attr.progressBarStyleHorizontal).apply { max = 100; isIndeterminate = false }
        root.addView(progress, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, dp(3)))

        val wv = WebView(ctx).apply {
            settings.apply {
                javaScriptEnabled   = true; domStorageEnabled  = true
                loadWithOverviewMode = true; useWideViewPort   = true
                setSupportZoom(true); builtInZoomControls = true; displayZoomControls = false
                mixedContentMode    = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
                userAgentString     = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
            }
            webViewClient = object : WebViewClient() {
                override fun onPageStarted(v: WebView?, u: String?, f: android.graphics.Bitmap?) { urlBar.setText(u); titleTv.text = "Loading..." }
                override fun onPageFinished(v: WebView?, u: String?) { titleTv.text = v?.title ?: u ?: ""; progress.progress = 0 }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onProgressChanged(v: WebView?, p: Int) { progress.progress = p }
            }
        }
        webView = wv
        root.addView(wv, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))

        goBtn.setOnClickListener {
            var url = urlBar.text.toString().trim()
            if (!url.startsWith("http")) url = "https://$url"
            wv.loadUrl(url)
        }
        urlBar.setOnEditorActionListener { _, _, _ -> goBtn.performClick(); true }
        backBtn.setOnClickListener   { if (wv.canGoBack())    wv.goBack()    }
        fwdBtn.setOnClickListener    { if (wv.canGoForward()) wv.goForward() }
        reloadBtn.setOnClickListener { wv.reload() }

        pendingUrl?.let { wv.loadUrl(it); pendingUrl = null }
        return root
    }

    override fun onDestroyView() {
        super.onDestroyView()
        webView?.stopLoading(); webView?.destroy(); webView = null
        pendingUrl = null
    }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}

// ─── URLs fragment ────────────────────────────────────────────────────────────

class UrlsFragment : Fragment() {
    private lateinit var adapter: UrlsAdapter
    private var allUrls = listOf<String>()

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, b: Bundle?): View {
        val ctx  = requireContext()
        val root = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor("#0F0F14")); setPadding(dp(10), dp(10), dp(10), dp(10)) }

        root.addView(TextView(ctx).apply { text = "All URLs"; setTextColor(Color.parseColor("#EAEAEA")); textSize = 15f; setTypeface(null, android.graphics.Typeface.BOLD) })
        val countTv = TextView(ctx).apply { text = "0 URLs"; setTextColor(Color.parseColor("#808088")); textSize = 12f }
        root.addView(countTv)

        val filterEt = EditText(ctx).apply { hint = "filter URLs..."; textSize = 12f; setTextColor(Color.parseColor("#EAEAEA")); setHintTextColor(Color.parseColor("#808088")); setBackgroundColor(Color.parseColor("#1A1A21")); setPadding(dp(10), dp(6), dp(10), dp(6)); setSingleLine() }
        root.addView(filterEt, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, dp(38)).apply { bottomMargin = dp(6) })

        val rv = RecyclerView(ctx).apply { layoutManager = LinearLayoutManager(ctx) }
        adapter = UrlsAdapter { url ->
            activity?.let { act ->
                BrowserFragment.pendingUrl = url
                act.findViewById<ViewPager2>(R.id.viewPager).currentItem = 2
            }
        }
        rv.adapter = adapter
        root.addView(rv, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f))

        allUrls = ScanState.urls.toList(); adapter.setData(allUrls); countTv.text = "${allUrls.size} URLs"

        ScanState.addUrlListener("urls_frag") { _ ->
            activity?.runOnUiThread {
                allUrls = ScanState.urls.toList(); adapter.setData(allUrls); countTv.text = "${allUrls.size} URLs"
            }
        }

        filterEt.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                val kw = s.toString().lowercase()
                adapter.setData(if (kw.isEmpty()) allUrls else allUrls.filter { kw in it.lowercase() })
            }
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
        })
        return root
    }

    override fun onDestroyView() { super.onDestroyView(); ScanState.removeListeners("urls_frag") }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}

class UrlsAdapter(private val onOpen: (String) -> Unit) : RecyclerView.Adapter<UrlsAdapter.VH>() {
    private var data = listOf<String>()
    fun setData(d: List<String>) { data = d; notifyDataSetChanged() }

    inner class VH(val root: LinearLayout) : RecyclerView.ViewHolder(root) {
        val urlTv = TextView(root.context); val goBtn = Button(root.context)
        init {
            root.orientation = LinearLayout.HORIZONTAL; root.setPadding(dp(8), dp(4), dp(8), dp(4))
            root.setBackgroundColor(Color.parseColor("#1A1A21"))
            root.layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT).apply { bottomMargin = dp(4) }
            urlTv.setTextColor(Color.parseColor("#EAEAEA")); urlTv.textSize = 11f; urlTv.maxLines = 2
            urlTv.layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
            goBtn.text = "Go"; goBtn.setBackgroundColor(Color.parseColor("#338FFF")); goBtn.setTextColor(Color.WHITE); goBtn.textSize = 11f; goBtn.layoutParams = LinearLayout.LayoutParams(dp(44), dp(36))
            root.addView(urlTv); root.addView(goBtn)
        }
        fun dp(v: Int) = (v * root.context.resources.displayMetrics.density).toInt()
    }

    override fun onCreateViewHolder(p: ViewGroup, t: Int) = VH(LinearLayout(p.context))
    override fun getItemCount() = data.size
    override fun onBindViewHolder(h: VH, pos: Int) { h.urlTv.text = data[pos]; h.goBtn.setOnClickListener { onOpen(data[pos]) } }
}

// ─── Log fragment ─────────────────────────────────────────────────────────────

class LogFragment : Fragment() {
    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, b: Bundle?): View {
        val ctx  = requireContext()
        val root = LinearLayout(ctx).apply { orientation = LinearLayout.VERTICAL; setBackgroundColor(Color.parseColor("#0F0F14")); setPadding(dp(10), dp(10), dp(10), dp(10)) }

        root.addView(TextView(ctx).apply { text = "Live Log"; setTextColor(Color.parseColor("#EAEAEA")); textSize = 15f; setTypeface(null, android.graphics.Typeface.BOLD) })
        val clearBtn = Button(ctx).apply { text = "Clear"; textSize = 11f; setBackgroundColor(Color.parseColor("#1A1A21")); setTextColor(Color.parseColor("#338FFF")) }
        root.addView(clearBtn)

        val scroll = ScrollView(ctx)
        val logTv  = TextView(ctx).apply {
            text = ScanState.logs.joinToString("\n")
            setTextColor(Color.parseColor("#EAEAEA")); textSize = 11f
            setPadding(dp(4), dp(4), dp(4), dp(4))
            setTypeface(android.graphics.Typeface.MONOSPACE)
        }
        scroll.addView(logTv)
        root.addView(scroll, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))

        val ts = SimpleDateFormat("HH:mm:ss", Locale.US)
        ScanState.addLogListener("log_frag") { msg ->
            activity?.runOnUiThread {
                logTv.append("\n[${ts.format(Date())}] $msg")
                scroll.post { scroll.fullScroll(View.FOCUS_DOWN) }
            }
        }
        clearBtn.setOnClickListener { ScanState.logs.clear(); logTv.text = "" }
        return root
    }

    override fun onDestroyView() { super.onDestroyView(); ScanState.removeListeners("log_frag") }
    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
