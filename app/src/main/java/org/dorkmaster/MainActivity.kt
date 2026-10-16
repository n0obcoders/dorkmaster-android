package org.dorkmaster

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.graphics.Color
import android.graphics.Typeface
import android.net.Uri
import android.os.Bundle
import android.text.Editable
import android.text.TextWatcher
import android.view.*
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.fragment.app.Fragment
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.viewpager2.adapter.FragmentStateAdapter
import androidx.viewpager2.widget.ViewPager2
import com.google.android.material.tabs.TabLayout
import com.google.android.material.tabs.TabLayoutMediator

data class DorkItem(val category: String, val query: String, val domain: String)

object Dorks {
    val categoryColors = mapOf(
        "credentials" to "#FF4040", "logs"      to "#FF8C1A",
        "databases"   to "#FFCC1A", "git"       to "#33CC77",
        "env"         to "#FF4040", "backups"   to "#FF8C1A",
        "admin"       to "#338FFF", "cloud"     to "#33CC77",
        "s3"          to "#FFCC1A", "apikeys"   to "#FF4040",
        "pastebin"    to "#FF8C1A", "github"    to "#808088",
        "jira"        to "#338FFF", "cms"       to "#FFCC1A",
        "network"     to "#FF8C1A", "stealer"   to "#FF4040",
        "emails"      to "#33CC77", "errors"    to "#FF8C1A",
        "xmlrpc"      to "#338FFF"
    )
    private fun s(d: String) = "site:$d"
    val categories: Map<String, (String) -> List<String>> = linkedMapOf(
        "credentials" to { d -> listOf(
            "${s(d)} filetype:txt intext:\"username\" intext:\"password\"",
            "${s(d)} filetype:cfg intext:\"password\"",
            "${s(d)} filetype:yml intext:\"password\"",
            "${s(d)} filetype:json intext:\"password\"",
            "${s(d)} filetype:ini intext:\"password=\"",
            "${s(d)} inurl:\"/.htpasswd\"",
            "${s(d)} intitle:\"index of\" \"shadow\"",
            "${s(d)} filetype:sh intext:\"password=\"",
            "${s(d)} filetype:ps1 intext:\"password\"",
            "intext:\"username\" intext:\"password\" intext:\"$d\" filetype:txt"
        )},
        "logs" to { d -> listOf(
            "${s(d)} intitle:\"index of\" \"access.log\"",
            "${s(d)} intitle:\"index of\" \"error.log\"",
            "${s(d)} filetype:log intext:\"password\"",
            "${s(d)} filetype:log intext:\"Authorization\"",
            "${s(d)} filetype:log intext:\"bearer\"",
            "${s(d)} filetype:log intext:\"api_key\"",
            "${s(d)} filetype:log intext:\"token\"",
            "${s(d)} intitle:\"index of\" \"debug.log\"",
            "${s(d)} intitle:\"index of\" \"laravel.log\"",
            "${s(d)} intitle:\"index of\" \"audit.log\""
        )},
        "databases" to { d -> listOf(
            "${s(d)} filetype:sql intext:\"INSERT INTO\" intext:\"password\"",
            "${s(d)} intitle:\"index of\" filetype:sql",
            "${s(d)} inurl:\"/phpmyadmin/\"",
            "${s(d)} inurl:adminer.php intitle:\"Login\"",
            "${s(d)} filetype:mdb inurl:\".mdb\"",
            "${s(d)} filetype:sqlite inurl:\".sqlite\"",
            "${s(d)} inurl:\":9200/_cat/indices\"",
            "${s(d)} inurl:\":27017\" intitle:\"mongo\"",
            "${s(d)} inurl:\":6379\" intitle:\"redis\"",
            "${s(d)} intitle:\"index of\" \"database.sql\""
        )},
        "git" to { d -> listOf(
            "${s(d)} intitle:\"index of\" \".git\"",
            "${s(d)} inurl:\"/.git/config\" intext:\"url =\"",
            "${s(d)} inurl:\"/.git/HEAD\" intext:\"ref:\"",
            "${s(d)} intitle:\"index of\" \".git/logs\"",
            "${s(d)} inurl:\"/.git/COMMIT_EDITMSG\"",
            "${s(d)} inurl:\"/.git/packed-refs\"",
            "${s(d)} intitle:\"index of\" \".svn\"",
            "${s(d)} intitle:\"index of\" \".hg\"",
            "intitle:\"index of\" \".git\" \"$d\""
        )},
        "env" to { d -> listOf(
            "${s(d)} filetype:env intext:\"DB_PASSWORD\"",
            "${s(d)} inurl:\".env\" intext:\"APP_KEY\"",
            "${s(d)} inurl:\".env.production\"",
            "${s(d)} filetype:env \"AWS_SECRET_ACCESS_KEY\"",
            "${s(d)} filetype:env \"AWS_ACCESS_KEY_ID\"",
            "${s(d)} filetype:env \"STRIPE_SECRET\"",
            "${s(d)} filetype:env \"OPENAI_API_KEY\"",
            "${s(d)} filetype:env \"ANTHROPIC_API_KEY\"",
            "${s(d)} filetype:env \"GITHUB_TOKEN\"",
            "${s(d)} filetype:env \"SECRET_KEY\"",
            "${s(d)} filetype:env \"DATABASE_URL\"",
            "${s(d)} filetype:env \"PRIVATE_KEY\"",
            "${s(d)} inurl:\"/.env\" -filetype:php"
        )},
        "backups" to { d -> listOf(
            "${s(d)} filetype:bak inurl:\"wp-config\"",
            "${s(d)} intitle:\"index of\" \"backup.zip\"",
            "${s(d)} intitle:\"index of\" \"backup.tar.gz\"",
            "${s(d)} filetype:zip inurl:\"backup\"",
            "${s(d)} inurl:\".bak\" filetype:bak",
            "${s(d)} inurl:\".swp\"",
            "${s(d)} intitle:\"index of\" \"database.bak\""
        )},
        "admin" to { d -> listOf(
            "${s(d)} inurl:admin intitle:\"login\"",
            "${s(d)} inurl:/wp-admin/ intitle:\"WordPress\"",
            "${s(d)} inurl:\"/jenkins\" intitle:\"Dashboard\"",
            "${s(d)} inurl:grafana intitle:\"Grafana\"",
            "${s(d)} inurl:kibana intitle:\"Kibana\"",
            "${s(d)} inurl:\":9090\" intitle:\"Prometheus\"",
            "${s(d)} inurl:\":3000\" intitle:\"Grafana\"",
            "${s(d)} inurl:\":15672\" intitle:\"RabbitMQ\"",
            "${s(d)} inurl:\":8888\" intitle:\"Jupyter\"",
            "${s(d)} intitle:\"RabbitMQ Management\""
        )},
        "cloud" to { d -> listOf(
            "site:s3.amazonaws.com inurl:$d",
            "site:blob.core.windows.net inurl:$d",
            "site:storage.googleapis.com inurl:$d",
            "filetype:json intext:\"aws_access_key_id\"",
            "${s(d)} intext:\"s3.amazonaws.com\" intext:\"bucket\"",
            "${s(d)} intext:\"blob.core.windows.net\"",
            "${s(d)} intext:\"digitaloceanspaces.com\""
        )},
        "s3" to { d -> listOf(
            "site:s3.amazonaws.com \"${d.replace(".", "-")}\"",
            "site:s3.amazonaws.com \"${d.replace(".", "-")}-backup\"",
            "site:s3.amazonaws.com \"${d.replace(".", "-")}-prod\"",
            "site:s3.amazonaws.com \"${d.replace(".", "-")}-dev\"",
            "site:s3.amazonaws.com \"${d.replace(".", "-")}-uploads\"",
            "site:storage.googleapis.com \"${d.replace(".", "-")}\"",
            "site:blob.core.windows.net \"${d.replace(".", "-")}\""
        )},
        "apikeys" to { d -> listOf(
            "${s(d)} filetype:js intext:\"api_key\"",
            "${s(d)} filetype:js intext:\"AIza\"",
            "${s(d)} filetype:js intext:\"AKIA\"",
            "${s(d)} filetype:js intext:\"pk_live_\"",
            "${s(d)} filetype:js intext:\"eyJ\"",
            "${s(d)} filetype:json intext:\"apiKey\"",
            "${s(d)} inurl:\"config.js\"",
            "${s(d)} inurl:\"service-account.json\"",
            "${s(d)} inurl:\"google-services.json\"",
            "${s(d)} inurl:\"secrets.yml\""
        )},
        "pastebin" to { d -> listOf(
            "site:pastebin.com \"$d\"",
            "site:pastebin.com \"$d\" password",
            "site:pastebin.com \"$d\" token",
            "site:pastebin.com \"$d\" DB_PASSWORD",
            "site:ghostbin.co \"$d\"",
            "site:rentry.co \"$d\"",
            "\"$d\" site:pastebin.com"
        )},
        "github" to { d -> listOf(
            "site:github.com \"$d\" password",
            "site:github.com \"$d\" api_key",
            "site:github.com \"$d\" .env",
            "site:github.com \"$d\" DB_PASSWORD",
            "site:github.com \"$d\" AWS_SECRET_ACCESS_KEY",
            "site:github.com \"$d\" private_key",
            "site:gitlab.com \"$d\" password",
            "site:gist.github.com \"$d\"",
            "site:bitbucket.org \"$d\" password"
        )},
        "jira" to { d -> listOf(
            "${s(d)} inurl:/jira/ intext:\"issue\"",
            "${s(d)} inurl:\"/confluence/\" intext:\"spaces\"",
            "${s(d)} inurl:\"/servicedesk/\"",
            "${s(d)} intitle:\"Dashboard - Jira\"",
            "site:*.atlassian.net \"$d\"",
            "site:*.atlassian.net \"$d\" password"
        )},
        "cms" to { d -> listOf(
            "${s(d)} inurl:wp-config.php.bak",
            "${s(d)} inurl:\"/wp-json/wp/v2/users\"",
            "${s(d)} inurl:xmlrpc.php",
            "${s(d)} inurl:wp-login.php",
            "${s(d)} inurl:\"/administrator/index.php\" intitle:\"Joomla\"",
            "${s(d)} inurl:\"/sites/default/settings.php\" intitle:\"Drupal\"",
            "${s(d)} inurl:\"/ghost/\" intitle:\"Ghost\""
        )},
        "network" to { d -> listOf(
            "${s(d)} intitle:\"webcamXP\" inurl:8080",
            "${s(d)} intitle:\"Live View / - AXIS\"",
            "${s(d)} intitle:\"Hikvision\" inurl:login",
            "${s(d)} inurl:\":10000\" intitle:\"Webmin\"",
            "${s(d)} intitle:\"TP-LINK\" inurl:admin",
            "${s(d)} intitle:\"pfSense\" inurl:index.php",
            "${s(d)} intitle:\"OpenWrt\" inurl:cgi-bin"
        )},
        "stealer" to { d -> listOf(
            "${s(d)} intitle:\"index of\" \"stealer\" filetype:txt",
            "${s(d)} intitle:\"index of\" \"combolist\"",
            "${s(d)} filetype:txt intext:\"URL:\" intext:\"USER:\" intext:\"PASS:\"",
            "${s(d)} filetype:txt intext:\"@gmail.com\" intext:\"password\"",
            "intext:\"$d\" intext:\"password\" filetype:txt -site:$d",
            "\"$d\" \"password\" filetype:txt"
        )},
        "emails" to { d -> listOf(
            "${s(d)} intext:\"@$d\" filetype:txt",
            "${s(d)} intext:\"@$d\" filetype:csv",
            "${s(d)} intitle:\"index of\" \"email\" filetype:txt",
            "${s(d)} intitle:\"index of\" \"contacts\" filetype:csv",
            "\"$d\" intext:\"@\" filetype:csv",
            "site:linkedin.com/in \"$d\""
        )},
        "errors" to { d -> listOf(
            "${s(d)} intext:\"Fatal error\"",
            "${s(d)} intext:\"Stack trace\"",
            "${s(d)} intext:\"Traceback (most recent call last)\"",
            "${s(d)} inurl:\"phpinfo.php\"",
            "${s(d)} inurl:\"/actuator/env\"",
            "${s(d)} inurl:\"/actuator/heapdump\"",
            "${s(d)} intitle:\"Whoops!\" intext:\"Laravel\"",
            "${s(d)} intitle:\"Werkzeug\" intext:\"Traceback\""
        )},
        "xmlrpc" to { d -> listOf(
            "${s(d)} inurl:\"xmlrpc.php\"",
            "${s(d)} inurl:\"/swagger-ui.html\"",
            "${s(d)} inurl:\"/api-docs\"",
            "${s(d)} intitle:\"Swagger UI\"",
            "${s(d)} inurl:\"?wsdl\"",
            "${s(d)} inurl:\"/rest/api/\"",
            "${s(d)} inurl:\"/wp-json/wp/v2/users\""
        )}
    )
    fun generate(domain: String, cats: Set<String>): List<DorkItem> {
        val result = mutableListOf<DorkItem>()
        for ((cat, fn) in categories) {
            if (cats.isEmpty() || cat in cats) fn(domain).forEach { result.add(DorkItem(cat, it, domain)) }
        }
        return result
    }
    fun googleUrl(query: String) = "https://www.google.com/search?q=${Uri.encode(query)}&num=10&safe=off"
    fun bingUrl  (query: String) = "https://www.bing.com/search?q=${Uri.encode(query)}&count=10"
    fun ddgUrl   (query: String) = "https://duckduckgo.com/?q=${Uri.encode(query)}&ia=web"
}

class MainActivity : AppCompatActivity() {
    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        setContentView(R.layout.activity_main)
        val pager = findViewById<ViewPager2>(R.id.viewPager)
        val tabs  = findViewById<TabLayout>(R.id.tabLayout)
        pager.offscreenPageLimit = 1
        pager.adapter = object : FragmentStateAdapter(this) {
            override fun getItemCount() = 1
            override fun createFragment(pos: Int) = DorkFragment()
        }
        pager.isUserInputEnabled = false
        TabLayoutMediator(tabs, pager) { tab, _ -> tab.text = "Dork" }.attach()
    }
}

class DorkFragment : Fragment() {
    private lateinit var rv: RecyclerView
    private lateinit var adapter: DorkAdapter
    private lateinit var countTv: TextView
    private var allItems   = listOf<DorkItem>()
    private var filterText = ""
    private var filterCat  = "all"

    override fun onCreateView(inf: LayoutInflater, c: ViewGroup?, b: Bundle?): View {
        val ctx  = requireContext()
        val root = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0F0F14"))
        }
        root.addView(LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(12), dp(10), dp(12), dp(6))
            setBackgroundColor(Color.parseColor("#1A1A21"))
            addView(TextView(ctx).apply {
                text = "⚡ DorkMaster"
                setTextColor(Color.parseColor("#338FFF"))
                textSize = 18f
                setTypeface(null, Typeface.BOLD)
                layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
            })
        })
        val domainEt = EditText(ctx).apply {
            hint = "target domain — example.com"
            setTextColor(Color.parseColor("#EAEAEA"))
            setHintTextColor(Color.parseColor("#606068"))
            setBackgroundColor(Color.parseColor("#1A1A21"))
            setPadding(dp(12), dp(10), dp(12), dp(10))
            textSize = 14f
            setSingleLine()
        }
        root.addView(domainEt, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
        ).apply { setMargins(dp(10), dp(6), dp(10), 0) })
        root.addView(TextView(ctx).apply {
            text = "Search engine"
            setTextColor(Color.parseColor("#606068"))
            textSize = 11f
            setPadding(dp(12), dp(8), dp(12), dp(2))
        })
        val engGroup = RadioGroup(ctx).apply {
            orientation = RadioGroup.HORIZONTAL
            setPadding(dp(8), 0, dp(8), 0)
        }
        val engines = listOf("Google" to "google", "Bing" to "bing", "DuckDuckGo" to "ddg")
        engines.forEachIndexed { idx, (label, _) ->
            engGroup.addView(RadioButton(ctx).apply {
                text = label; id = idx
                setTextColor(Color.WHITE); textSize = 12f
                isChecked = idx == 0
                setPadding(dp(4), 0, dp(16), 0)
            })
        }
        root.addView(engGroup)
        root.addView(TextView(ctx).apply {
            text = "Category"
            setTextColor(Color.parseColor("#606068"))
            textSize = 11f
            setPadding(dp(12), dp(8), dp(12), dp(2))
        })
        val chipScroll = HorizontalScrollView(ctx).apply { isHorizontalScrollBarEnabled = false }
        val chipRow    = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(8), dp(2), dp(8), dp(6))
        }
        val catList   = listOf("all") + Dorks.categories.keys.toList()
        val chipViews = mutableListOf<TextView>()
        catList.forEach { cat ->
            val chip = TextView(ctx).apply {
                text = cat; textSize = 11f
                setPadding(dp(10), dp(5), dp(10), dp(5))
                setTypeface(null, Typeface.BOLD)
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT, LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { rightMargin = dp(6) }
            }
            chipViews.add(chip); chipRow.addView(chip)
        }
        fun updateChips(selected: String) {
            chipViews.forEachIndexed { idx, chip ->
                if (catList[idx] == selected) {
                    chip.setBackgroundColor(Color.parseColor("#338FFF"))
                    chip.setTextColor(Color.WHITE)
                } else {
                    chip.setBackgroundColor(Color.parseColor("#1A1A21"))
                    chip.setTextColor(Color.parseColor("#808088"))
                }
            }
        }
        updateChips("all")
        chipViews.forEachIndexed { idx, chip ->
            chip.setOnClickListener { filterCat = catList[idx]; updateChips(filterCat); applyFilter() }
        }
        chipScroll.addView(chipRow); root.addView(chipScroll)
        val searchRow = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(10), dp(4), dp(10), dp(4))
        }
        val searchEt = EditText(ctx).apply {
            hint = "filter dorks..."
            setTextColor(Color.parseColor("#EAEAEA"))
            setHintTextColor(Color.parseColor("#606068"))
            setBackgroundColor(Color.parseColor("#1A1A21"))
            setPadding(dp(10), dp(8), dp(10), dp(8))
            textSize = 12f; setSingleLine()
            layoutParams = LinearLayout.LayoutParams(0, dp(40), 1f).apply { rightMargin = dp(6) }
        }
        val genBtn = Button(ctx).apply {
            text = "GENERATE"
            setBackgroundColor(Color.parseColor("#338FFF"))
            setTextColor(Color.WHITE); textSize = 12f
            setTypeface(null, Typeface.BOLD)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, dp(40))
        }
        searchRow.addView(searchEt); searchRow.addView(genBtn); root.addView(searchRow)
        countTv = TextView(ctx).apply {
            text = "enter domain and tap GENERATE"
            setTextColor(Color.parseColor("#606068"))
            textSize = 11f; setPadding(dp(12), dp(2), dp(12), dp(4))
        }
        root.addView(countTv)
        rv = RecyclerView(ctx).apply {
            layoutManager = LinearLayoutManager(ctx)
            setHasFixedSize(false)
            setItemViewCacheSize(40)
            recycledViewPool.setMaxRecycledViews(0, 80)
        }
        adapter = DorkAdapter(
            onOpenEngine = { item, eng ->
                val url = when (eng) {
                    "bing" -> Dorks.bingUrl(item.query)
                    "ddg"  -> Dorks.ddgUrl(item.query)
                    else   -> Dorks.googleUrl(item.query)
                }
                openUrl(url)
            },
            onCopy = { item ->
                val cm = requireContext().getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cm.setPrimaryClip(ClipData.newPlainText("dork", item.query))
                Toast.makeText(requireContext(), "Copied", Toast.LENGTH_SHORT).show()
            }
        )
        rv.adapter = adapter
        root.addView(rv, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
        genBtn.setOnClickListener {
            val domain = domainEt.text.toString().trim()
                .removePrefix("https://").removePrefix("http://").trimEnd('/')
            if (domain.isEmpty()) { Toast.makeText(ctx, "Enter a domain first", Toast.LENGTH_SHORT).show(); return@setOnClickListener }
            val cats = if (filterCat == "all") emptySet() else setOf(filterCat)
            allItems = Dorks.generate(domain, cats)
            applyFilter()
        }
        searchEt.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) { filterText = s.toString().lowercase().trim(); applyFilter() }
            override fun beforeTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
            override fun onTextChanged(s: CharSequence?, a: Int, b: Int, c: Int) {}
        })
        return root
    }

    private fun applyFilter() {
        val filtered = allItems.filter {
            (filterCat == "all" || it.category == filterCat) &&
            (filterText.isEmpty() || filterText in it.query.lowercase() || filterText in it.category)
        }
        adapter.setData(filtered)
        countTv.text = "${filtered.size} dorks" + if (allItems.size != filtered.size) " (${allItems.size} total)" else ""
    }

    private fun openUrl(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            })
        } catch (e: Exception) {
            Toast.makeText(requireContext(), "No browser found — install Brave or Firefox", Toast.LENGTH_LONG).show()
        }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}

class DorkAdapter(
    private val onOpenEngine: (DorkItem, String) -> Unit,
    private val onCopy      : (DorkItem)         -> Unit
) : RecyclerView.Adapter<DorkAdapter.VH>() {

    private var data = listOf<DorkItem>()
    fun setData(d: List<DorkItem>) { data = d; notifyDataSetChanged() }

    inner class VH(val root: LinearLayout) : RecyclerView.ViewHolder(root) {
        val catTv   = TextView(root.context)
        val queryTv = TextView(root.context)
        val btnRow  = LinearLayout(root.context)
        val gBtn    = Button(root.context)
        val bBtn    = Button(root.context)
        val dBtn    = Button(root.context)
        val cBtn    = Button(root.context)
        init {
            root.orientation = LinearLayout.VERTICAL
            root.setPadding(dp(10), dp(8), dp(10), dp(8))
            root.setBackgroundColor(Color.parseColor("#1A1A21"))
            root.layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { setMargins(dp(8), dp(3), dp(8), dp(3)) }
            catTv.textSize = 10f; catTv.setTypeface(null, Typeface.BOLD)
            queryTv.textSize = 12f
            queryTv.setTextColor(Color.parseColor("#EAEAEA"))
            queryTv.setPadding(0, dp(3), 0, dp(5))
            queryTv.setLineSpacing(dp(2).toFloat(), 1f)
            btnRow.orientation = LinearLayout.HORIZONTAL; btnRow.weightSum = 4f
            gBtn.apply { text="Google"; setBackgroundColor(Color.parseColor("#1A6FD4")); setTextColor(Color.WHITE); textSize=10f; setTypeface(null,Typeface.BOLD); layoutParams=LinearLayout.LayoutParams(0,dp(32),1f).apply{rightMargin=dp(3)} }
            bBtn.apply { text="Bing";   setBackgroundColor(Color.parseColor("#008080")); setTextColor(Color.WHITE); textSize=10f; setTypeface(null,Typeface.BOLD); layoutParams=LinearLayout.LayoutParams(0,dp(32),1f).apply{rightMargin=dp(3)} }
            dBtn.apply { text="DDG";    setBackgroundColor(Color.parseColor("#DE5833")); setTextColor(Color.WHITE); textSize=10f; setTypeface(null,Typeface.BOLD); layoutParams=LinearLayout.LayoutParams(0,dp(32),1f).apply{rightMargin=dp(3)} }
            cBtn.apply { text="Copy";   setBackgroundColor(Color.parseColor("#2A2A33")); setTextColor(Color.parseColor("#338FFF")); textSize=10f; setTypeface(null,Typeface.BOLD); layoutParams=LinearLayout.LayoutParams(0,dp(32),1f) }
            btnRow.addView(gBtn); btnRow.addView(bBtn); btnRow.addView(dBtn); btnRow.addView(cBtn)
            root.addView(catTv); root.addView(queryTv); root.addView(btnRow)
        }
        fun dp(v: Int) = (v * root.context.resources.displayMetrics.density).toInt()
    }

    override fun onCreateViewHolder(p: ViewGroup, t: Int) = VH(LinearLayout(p.context))
    override fun getItemCount() = data.size
    override fun onBindViewHolder(h: VH, pos: Int) {
        val item  = data[pos]
        val color = Dorks.categoryColors[item.category] ?: "#808088"
        h.catTv.text = "▸ ${item.category.uppercase()}"
        h.catTv.setTextColor(Color.parseColor(color))
        h.queryTv.text = item.query
        h.gBtn.setOnClickListener { onOpenEngine(item, "google") }
        h.bBtn.setOnClickListener { onOpenEngine(item, "bing")   }
        h.dBtn.setOnClickListener { onOpenEngine(item, "ddg")    }
        h.cBtn.setOnClickListener { onCopy(item) }
    }
}