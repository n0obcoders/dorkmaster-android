#!/bin/bash
set -e

mkdir -p app/src/main/java/org/dorkmaster
mkdir -p app/src/main/res/layout
mkdir -p app/src/main/res/values
mkdir -p app/src/main/res/drawable
mkdir -p app/src/main/res/mipmap-anydpi-v26
mkdir -p .github/workflows
mkdir -p gradle/wrapper

cat > settings.gradle << 'EOF'
rootProject.name = "DorkMaster"
include ':app'
EOF

cat > build.gradle << 'EOF'
buildscript {
    repositories { google(); mavenCentral() }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.2.2'
        classpath 'org.jetbrains.kotlin:kotlin-gradle-plugin:1.9.22'
    }
}
allprojects { repositories { google(); mavenCentral() } }
EOF

cat > gradle.properties << 'EOF'
android.useAndroidX=true
android.enableJetifier=true
org.gradle.jvmargs=-Xmx2048m
EOF

cat > gradle/wrapper/gradle-wrapper.properties << 'EOF'
distributionBase=GRADLE_USER_HOME
distributionPath=wrapper/dists
zipStoreBase=GRADLE_USER_HOME
zipStorePath=wrapper/dists
distributionUrl=https\://services.gradle.org/distributions/gradle-8.4-bin.zip
EOF

cat > app/build.gradle << 'EOF'
plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
}
android {
    namespace 'org.dorkmaster'
    compileSdk 34
    defaultConfig {
        applicationId "org.dorkmaster"
        minSdk 24
        targetSdk 34
        versionCode 2
        versionName "5.0"
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = '17' }
}
dependencies {
    implementation 'androidx.core:core-ktx:1.12.0'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.11.0'
    implementation 'androidx.recyclerview:recyclerview:1.3.2'
    implementation 'androidx.viewpager2:viewpager2:1.0.0'
    implementation 'androidx.webkit:webkit:1.10.0'
}
EOF

cat > app/src/main/AndroidManifest.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />
    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:label="@string/app_name"
        android:theme="@style/AppTheme"
        android:hardwareAccelerated="true"
        android:usesCleartextTraffic="true">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:windowSoftInputMode="adjustResize">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
        <activity
            android:name=".BrowserActivity"
            android:exported="false"
            android:configChanges="orientation|screenSize|keyboardHidden"
            android:windowSoftInputMode="adjustResize"/>
    </application>
</manifest>
EOF

cat > app/src/main/res/layout/activity_main.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:orientation="vertical"
    android:background="@color/bg">
    <com.google.android.material.tabs.TabLayout
        android:id="@+id/tabLayout"
        android:layout_width="match_parent"
        android:layout_height="48dp"
        android:background="@color/panel"
        app:tabTextColor="@color/dim"
        app:tabSelectedTextColor="@color/accent"
        app:tabIndicatorColor="@color/accent"
        app:tabMode="scrollable"/>
    <androidx.viewpager2.widget.ViewPager2
        android:id="@+id/viewPager"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:background="@color/bg"/>
</LinearLayout>
EOF

cat > app/src/main/res/values/colors.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="bg">#0F0F14</color>
    <color name="panel">#1A1A21</color>
    <color name="accent">#338FFF</color>
    <color name="dim">#606068</color>
    <color name="white">#EAEAEA</color>
    <color name="red">#FF4040</color>
    <color name="green">#33CC77</color>
    <color name="yellow">#FFCC1A</color>
    <color name="orange">#FF8C1A</color>
</resources>
EOF

cat > app/src/main/res/values/strings.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">DorkMaster</string>
</resources>
EOF

cat > app/src/main/res/values/styles.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="AppTheme" parent="Theme.MaterialComponents.DayNight.NoActionBar">
        <item name="colorPrimary">#338FFF</item>
        <item name="colorPrimaryDark">#0F0F14</item>
        <item name="colorAccent">#338FFF</item>
        <item name="android:windowBackground">#0F0F14</item>
        <item name="android:statusBarColor">#1A1A21</item>
        <item name="android:navigationBarColor">#0F0F14</item>
    </style>
</resources>
EOF

cat > app/src/main/res/drawable/ic_logo.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="108dp" android:height="108dp"
    android:viewportWidth="108" android:viewportHeight="108">
    <path android:fillColor="#0F0F14"
        android:pathData="M0,0 L108,0 L108,108 L0,108 Z"/>
    <path android:strokeColor="#338FFF" android:strokeWidth="0.7" android:strokeAlpha="0.25"
        android:pathData="M14,27 L94,27 M14,40 L94,40 M14,53 L94,53 M14,66 L94,66 M14,79 L94,79"/>
    <path android:strokeColor="#338FFF" android:strokeWidth="0.7" android:strokeAlpha="0.25"
        android:pathData="M27,14 L27,94 M40,14 L40,94 M53,14 L53,94 M66,14 L66,94 M79,14 L79,94"/>
    <path android:strokeColor="#338FFF" android:strokeWidth="4.5" android:fillColor="#00000000"
        android:pathData="M45,45m-17,0a17,17 0,1 1,34 0a17,17 0,1 1,-34 0"/>
    <path android:strokeColor="#338FFF" android:strokeWidth="4.5" android:strokeLineCap="round"
        android:pathData="M57,57 L72,72"/>
    <path android:fillColor="#FF4040"
        android:pathData="M45,45m-4,0a4,4 0,1 1,8 0a4,4 0,1 1,-8 0"/>
    <path android:strokeColor="#FF4040" android:strokeWidth="2"
        android:pathData="M28,45 L38,45 M52,45 L62,45 M45,28 L45,38 M45,52 L45,62"/>
</vector>
EOF

cat > app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/bg"/>
    <foreground android:drawable="@drawable/ic_logo"/>
</adaptive-icon>
EOF

cat > app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml << 'EOF'
<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/bg"/>
    <foreground android:drawable="@drawable/ic_logo"/>
</adaptive-icon>
EOF

cat > .github/workflows/build.yml << 'EOF'
name: Build APK
on:
  push:
    branches: [main, master]
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-22.04
    steps:
      - uses: actions/checkout@v4
      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          java-version: '17'
          distribution: 'temurin'
      - name: Make gradlew executable
        run: chmod +x ./gradlew
      - name: Build debug APK
        run: ./gradlew assembleDebug --stacktrace --no-daemon
      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: DorkMaster-APK
          path: app/build/outputs/apk/debug/*.apk
          if-no-files-found: error
EOF

cat > app/src/main/java/org/dorkmaster/MainActivity.kt << 'EOF'
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

// ── Dork library ─────────────────────────────────────────────────────────────

data class DorkItem(val category: String, val query: String, val domain: String)

object Dorks {
    val categoryColors = mapOf(
        "credentials" to "#FF4040",
        "logs"        to "#FF8C1A",
        "databases"   to "#FFCC1A",
        "git"         to "#33CC77",
        "env"         to "#FF4040",
        "backups"     to "#FF8C1A",
        "admin"       to "#338FFF",
        "cloud"       to "#33CC77",
        "s3"          to "#FFCC1A",
        "apikeys"     to "#FF4040",
        "pastebin"    to "#FF8C1A",
        "github"      to "#808088",
        "jira"        to "#338FFF",
        "cms"         to "#FFCC1A",
        "network"     to "#FF8C1A",
        "stealer"     to "#FF4040",
        "emails"      to "#33CC77",
        "errors"      to "#FF8C1A",
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
            if (cats.isEmpty() || cat in cats) {
                fn(domain).forEach { result.add(DorkItem(cat, it, domain)) }
            }
        }
        return result
    }

    fun googleUrl(query: String): String =
        "https://www.google.com/search?q=${Uri.encode(query)}&num=10&safe=off"

    fun bingUrl(query: String): String =
        "https://www.bing.com/search?q=${Uri.encode(query)}&count=10"

    fun ddgUrl(query: String): String =
        "https://duckduckgo.com/?q=${Uri.encode(query)}&ia=web"
}

// ── Main activity ─────────────────────────────────────────────────────────────

class MainActivity : AppCompatActivity() {
    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        setContentView(R.layout.activity_main)
        val pager  = findViewById<ViewPager2>(R.id.viewPager)
        val tabs   = findViewById<TabLayout>(R.id.tabLayout)
        val titles = listOf("Dork", "Browse")
        pager.offscreenPageLimit = 2
        pager.adapter = object : FragmentStateAdapter(this) {
            override fun getItemCount() = 2
            override fun createFragment(pos: Int): Fragment = when (pos) {
                0    -> DorkFragment()
                else -> BrowserTabFragment()
            }
        }
        pager.isUserInputEnabled = true
        TabLayoutMediator(tabs, pager) { tab, pos -> tab.text = titles[pos] }.attach()
    }
}

// ── Dork fragment ─────────────────────────────────────────────────────────────

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

        // ── header
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

        // ── domain input row
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

        // ── engine selector
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

        // ── category chips scroll
        root.addView(TextView(ctx).apply {
            text = "Category"
            setTextColor(Color.parseColor("#606068"))
            textSize = 11f
            setPadding(dp(12), dp(8), dp(12), dp(2))
        })
        val chipScroll = HorizontalScrollView(ctx).apply {
            isHorizontalScrollBarEnabled = false
        }
        val chipRow = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(8), dp(2), dp(8), dp(6))
        }
        val catList  = listOf("all") + Dorks.categories.keys.toList()
        val chipViews = mutableListOf<TextView>()
        catList.forEach { cat ->
            val chip = TextView(ctx).apply {
                text = cat
                textSize = 11f
                setPadding(dp(10), dp(5), dp(10), dp(5))
                setTypeface(null, Typeface.BOLD)
                layoutParams = LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.WRAP_CONTENT,
                    LinearLayout.LayoutParams.WRAP_CONTENT
                ).apply { rightMargin = dp(6) }
            }
            chipViews.add(chip)
            chipRow.addView(chip)
        }

        fun updateChips(selected: String) {
            chipViews.forEachIndexed { idx, chip ->
                val cat = catList[idx]
                if (cat == selected) {
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
            chip.setOnClickListener {
                filterCat = catList[idx]
                updateChips(filterCat)
                applyFilter()
            }
        }

        chipScroll.addView(chipRow)
        root.addView(chipScroll)

        // ── search bar + generate button
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
            textSize = 12f
            setSingleLine()
            layoutParams = LinearLayout.LayoutParams(0, dp(40), 1f).apply { rightMargin = dp(6) }
        }
        val genBtn = Button(ctx).apply {
            text = "GENERATE"
            setBackgroundColor(Color.parseColor("#338FFF"))
            setTextColor(Color.WHITE)
            textSize = 12f
            setTypeface(null, Typeface.BOLD)
            layoutParams = LinearLayout.LayoutParams(LinearLayout.LayoutParams.WRAP_CONTENT, dp(40))
        }
        searchRow.addView(searchEt); searchRow.addView(genBtn)
        root.addView(searchRow)

        // ── count bar
        countTv = TextView(ctx).apply {
            text = "enter domain and tap GENERATE"
            setTextColor(Color.parseColor("#606068"))
            textSize = 11f
            setPadding(dp(12), dp(2), dp(12), dp(4))
        }
        root.addView(countTv)

        // ── recycler
        rv = RecyclerView(ctx).apply {
            layoutManager = LinearLayoutManager(ctx)
            setHasFixedSize(false)
            setItemViewCacheSize(30)
        }
        adapter = DorkAdapter(
            onOpen = { item ->
                val eng = engines[engGroup.checkedRadioButtonId].second
                val url = when (eng) {
                    "bing" -> Dorks.bingUrl(item.query)
                    "ddg"  -> Dorks.ddgUrl(item.query)
                    else   -> Dorks.googleUrl(item.query)
                }
                openInBrowser(url)
            },
            onCopy = { item ->
                val cm = requireContext().getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cm.setPrimaryClip(ClipData.newPlainText("dork", item.query))
                Toast.makeText(requireContext(), "Copied", Toast.LENGTH_SHORT).show()
            },
            onOpenAllEngine = { item, eng ->
                val url = when (eng) {
                    "bing" -> Dorks.bingUrl(item.query)
                    "ddg"  -> Dorks.ddgUrl(item.query)
                    else   -> Dorks.googleUrl(item.query)
                }
                openInBrowser(url)
            }
        )
        rv.adapter = adapter
        rv.recycledViewPool.setMaxRecycledViews(0, 60)
        root.addView(rv, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
        ))

        // ── generate action
        genBtn.setOnClickListener {
            val raw    = domainEt.text.toString().trim()
            val domain = raw.removePrefix("https://").removePrefix("http://").trimEnd('/')
            if (domain.isEmpty()) {
                Toast.makeText(ctx, "Enter a domain first", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            val cats = if (filterCat == "all") emptySet() else setOf(filterCat)
            allItems = Dorks.generate(domain, cats)
            applyFilter()
        }

        // ── filter watcher
        searchEt.addTextChangedListener(object : TextWatcher {
            override fun afterTextChanged(s: Editable?) {
                filterText = s.toString().lowercase().trim()
                applyFilter()
            }
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

    private fun openInBrowser(url: String) {
        // switch to browser tab and load
        val act = requireActivity() as? MainActivity
        act?.findViewById<ViewPager2>(R.id.viewPager)?.let { pager ->
            BrowserTabFragment.pendingUrl = url
            pager.currentItem = 1
        }
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}

// ── Dork adapter ──────────────────────────────────────────────────────────────

class DorkAdapter(
    private val onOpen: (DorkItem) -> Unit,
    private val onCopy: (DorkItem) -> Unit,
    private val onOpenAllEngine: (DorkItem, String) -> Unit
) : RecyclerView.Adapter<DorkAdapter.VH>() {

    private var data = listOf<DorkItem>()

    fun setData(d: List<DorkItem>) {
        data = d
        notifyDataSetChanged()
    }

    inner class VH(val root: LinearLayout) : RecyclerView.ViewHolder(root) {
        val catTv    = TextView(root.context)
        val queryTv  = TextView(root.context)
        val btnRow   = LinearLayout(root.context)
        val openBtn  = Button(root.context)
        val bingBtn  = Button(root.context)
        val ddgBtn   = Button(root.context)
        val copyBtn  = Button(root.context)

        init {
            root.orientation = LinearLayout.VERTICAL
            root.setPadding(dp(10), dp(8), dp(10), dp(8))
            root.setBackgroundColor(Color.parseColor("#1A1A21"))
            root.layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT,
                LinearLayout.LayoutParams.WRAP_CONTENT
            ).apply { bottomMargin = dp(5); setMargins(dp(8), dp(3), dp(8), dp(3)) }

            catTv.textSize   = 10f
            catTv.setTypeface(null, Typeface.BOLD)

            queryTv.textSize = 12f
            queryTv.setTextColor(Color.parseColor("#EAEAEA"))
            queryTv.setPadding(0, dp(3), 0, dp(4))
            queryTv.setLineSpacing(dp(2).toFloat(), 1f)

            btnRow.orientation = LinearLayout.HORIZONTAL
            btnRow.weightSum   = 4f

            fun mkBtn(label: String, bg: String, fg: String) = Button(root.context).apply {
                text = label
                setBackgroundColor(Color.parseColor(bg))
                setTextColor(Color.parseColor(fg))
                textSize = 10f
                setPadding(dp(2), 0, dp(2), 0)
                setTypeface(null, Typeface.BOLD)
                layoutParams = LinearLayout.LayoutParams(0, dp(30), 1f).apply { rightMargin = dp(3) }
            }

            openBtn.apply { text = "Google"; setBackgroundColor(Color.parseColor("#338FFF")); setTextColor(Color.WHITE); textSize = 10f; setTypeface(null, Typeface.BOLD); setPadding(dp(2),0,dp(2),0); layoutParams = LinearLayout.LayoutParams(0, dp(30), 1f).apply { rightMargin = dp(3) } }
            bingBtn.apply { text = "Bing";   setBackgroundColor(Color.parseColor("#008080")); setTextColor(Color.WHITE); textSize = 10f; setTypeface(null, Typeface.BOLD); setPadding(dp(2),0,dp(2),0); layoutParams = LinearLayout.LayoutParams(0, dp(30), 1f).apply { rightMargin = dp(3) } }
            ddgBtn.apply  { text = "DDG";    setBackgroundColor(Color.parseColor("#DE5833")); setTextColor(Color.WHITE); textSize = 10f; setTypeface(null, Typeface.BOLD); setPadding(dp(2),0,dp(2),0); layoutParams = LinearLayout.LayoutParams(0, dp(30), 1f).apply { rightMargin = dp(3) } }
            copyBtn.apply { text = "Copy";   setBackgroundColor(Color.parseColor("#2A2A33")); setTextColor(Color.parseColor("#338FFF")); textSize = 10f; setTypeface(null, Typeface.BOLD); setPadding(dp(2),0,dp(2),0); layoutParams = LinearLayout.LayoutParams(0, dp(30), 1f) }

            btnRow.addView(openBtn); btnRow.addView(bingBtn); btnRow.addView(ddgBtn); btnRow.addView(copyBtn)
            root.addView(catTv); root.addView(queryTv); root.addView(btnRow)
        }

        fun dp(v: Int) = (v * root.context.resources.displayMetrics.density).toInt()
    }

    override fun onCreateViewHolder(p: ViewGroup, t: Int) = VH(LinearLayout(p.context))
    override fun getItemCount() = data.size

    override fun onBindViewHolder(h: VH, pos: Int) {
        val item = data[pos]
        val color = Dorks.categoryColors[item.category] ?: "#808088"
        h.catTv.text = "▸ ${item.category.uppercase()}"
        h.catTv.setTextColor(Color.parseColor(color))
        h.queryTv.text = item.query
        h.openBtn.setOnClickListener { onOpen(item) }
        h.bingBtn.setOnClickListener { onOpenAllEngine(item, "bing") }
        h.ddgBtn.setOnClickListener  { onOpenAllEngine(item, "ddg")  }
        h.copyBtn.setOnClickListener { onCopy(item) }
    }
}

// ── Browser tab fragment (in-app) ─────────────────────────────────────────────

class BrowserTabFragment : Fragment() {

    companion object {
        var pendingUrl: String? = null
    }

    private var webView: WebView? = null

    @android.annotation.SuppressLint("SetJavaScriptEnabled")
    override fun onCreateView(inf: LayoutInflater, c: ViewGroup?, b: Bundle?): View {
        val ctx  = requireContext()
        val root = LinearLayout(ctx).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(Color.parseColor("#0F0F14"))
        }

        // url bar
        val barRow = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(6), dp(6), dp(6), dp(6))
            setBackgroundColor(Color.parseColor("#1A1A21"))
        }
        val urlBar = EditText(ctx).apply {
            hint = "https://..."
            textSize = 12f
            setTextColor(Color.parseColor("#EAEAEA"))
            setHintTextColor(Color.parseColor("#606068"))
            setBackgroundColor(Color.TRANSPARENT)
            setSingleLine()
            layoutParams = LinearLayout.LayoutParams(0, dp(38), 1f)
        }
        val goBtn = Button(ctx).apply {
            text = "Go"
            setBackgroundColor(Color.parseColor("#338FFF"))
            setTextColor(Color.WHITE)
            textSize = 12f
            layoutParams = LinearLayout.LayoutParams(dp(52), dp(38))
        }
        barRow.addView(urlBar); barRow.addView(goBtn)
        root.addView(barRow)

        // nav row
        val navRow = LinearLayout(ctx).apply {
            orientation = LinearLayout.HORIZONTAL
            setPadding(dp(4), dp(2), dp(4), dp(2))
            setBackgroundColor(Color.parseColor("#1A1A21"))
        }
        fun navBtn(t: String) = Button(ctx).apply {
            text = t; textSize = 11f
            setBackgroundColor(Color.parseColor("#0F0F14"))
            setTextColor(Color.parseColor("#338FFF"))
            layoutParams = LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, dp(32)
            ).apply { rightMargin = dp(4) }
        }
        val backBtn   = navBtn("◀")
        val fwdBtn    = navBtn("▶")
        val reloadBtn = navBtn("↻")
        val extBtn    = navBtn("⬡ ext")
        val titleTv   = TextView(ctx).apply {
            text = "Browser"
            setTextColor(Color.parseColor("#606068"))
            textSize = 10f
            maxLines = 1
            ellipsize = android.text.TextUtils.TruncateAt.END
            layoutParams = LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f)
        }
        listOf(backBtn, fwdBtn, reloadBtn, titleTv, extBtn).forEach { navRow.addView(it) }
        root.addView(navRow)

        // progress
        val progress = ProgressBar(ctx, null, android.R.attr.progressBarStyleHorizontal).apply {
            max = 100; isIndeterminate = false
        }
        root.addView(progress, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, dp(3)
        ))

        // webview
        val wv = WebView(ctx)
        wv.settings.apply {
            javaScriptEnabled    = true
            domStorageEnabled    = true
            loadWithOverviewMode = true
            useWideViewPort      = true
            setSupportZoom(true)
            builtInZoomControls  = true
            displayZoomControls  = false
            mixedContentMode     = android.webkit.WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            cacheMode            = android.webkit.WebSettings.LOAD_DEFAULT
            userAgentString      = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36"
        }
        wv.webViewClient = object : android.webkit.WebViewClient() {
            override fun onPageStarted(v: WebView?, u: String?, f: android.graphics.Bitmap?) {
                urlBar.setText(u); titleTv.text = "Loading..."
            }
            override fun onPageFinished(v: WebView?, u: String?) {
                titleTv.text = v?.title ?: u ?: ""
                progress.progress = 0
            }
            override fun onReceivedError(v: WebView?, req: android.webkit.WebResourceRequest?, err: android.webkit.WebResourceError?) {
                // swallow — page still loads partially, don't crash
            }
        }
        wv.webChromeClient = object : android.webkit.WebChromeClient() {
            override fun onProgressChanged(v: WebView?, p: Int) { progress.progress = p }
        }
        webView = wv
        root.addView(wv, LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f
        ))

        // actions
        goBtn.setOnClickListener {
            var url = urlBar.text.toString().trim()
            if (!url.startsWith("http")) url = "https://$url"
            wv.loadUrl(url)
        }
        urlBar.setOnEditorActionListener { _, _, _ -> goBtn.performClick(); true }
        backBtn.setOnClickListener   { if (wv.canGoBack())    wv.goBack()    }
        fwdBtn.setOnClickListener    { if (wv.canGoForward()) wv.goForward() }
        reloadBtn.setOnClickListener { wv.reload() }
        extBtn.setOnClickListener {
            val url = wv.url ?: urlBar.text.toString().trim()
            if (url.isNotEmpty()) {
                try { startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
                catch (_: Exception) { Toast.makeText(ctx, "No browser found", Toast.LENGTH_SHORT).show() }
            }
        }

        // load pending url from dork tab
        pendingUrl?.let { wv.loadUrl(it); pendingUrl = null }

        return root
    }

    override fun onResume() {
        super.onResume()
        pendingUrl?.let { webView?.loadUrl(it); pendingUrl = null }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        webView?.stopLoading()
        webView?.destroy()
        webView = null
    }

    private fun dp(v: Int) = (v * resources.displayMetrics.density).toInt()
}
EOF

# ── download gradle wrapper binaries ──────────────────────────────────────────
curl -L "https://raw.githubusercontent.com/gradle/gradle/v8.4.0/gradlew"     -o gradlew
curl -L "https://raw.githubusercontent.com/gradle/gradle/v8.4.0/gradlew.bat" -o gradlew.bat
curl -L "https://github.com/gradle/gradle/raw/v8.4.0/gradle/wrapper/gradle-wrapper.jar" \
     -o gradle/wrapper/gradle-wrapper.jar
chmod +x gradlew

git add -A
git commit -m "v5.0 - dork launcher, browser tab, all engines, zero scraping, stable"
git push --force