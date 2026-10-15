#!/usr/bin/env python3
"""
DorkMaster Mobile v4.3
- Pure Python HTTP (requests) — zero C extensions, builds clean on Android
- 20 dork categories, full query lists
- Browser tab: tap any result URL to open it in an embedded WebView
- Scan / Results / Browser / Log tabs
"""
from __future__ import annotations

import os, sys, pathlib

def _write_if_missing(path: str, content: str) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(content, encoding="utf-8")

_BUILDOZER_SPEC = """
[app]
title = DorkMaster
package.name = dorkmaster
package.domain = org.dorkmaster
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 4.3.0
requirements = python3==3.11.6,kivy==2.3.0,pyjnius,requests,urllib3,certifi,charset-normalizer,idna,attrs
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True
android.logcat_filters = *:S python:D
android.sdk_path = /usr/local/lib/android/sdk
android.ndk_path = /home/runner/.buildozer/android/platform/android-ndk-r25b

[buildozer]
log_level = 2
warn_on_root = 1
""".strip()

_GH_WORKFLOW = """
name: Build APK
on:
  push:
    branches: [main, master]
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-22.04
    env:
      ANDROID_HOME: /usr/local/lib/android/sdk
      ANDROID_SDK_ROOT: /usr/local/lib/android/sdk
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install system deps
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y \\
            git zip unzip openjdk-17-jdk autoconf libtool \\
            pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \\
            libtinfo5 cmake libffi-dev libssl-dev \\
            python3-pip build-essential ccache
      - name: Accept Android SDK licenses
        run: |
          yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses 2>/dev/null || true
          $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "build-tools;34.0.0" "platforms;android-33" "platform-tools" 2>/dev/null || true
      - name: Patch buildozer SDK path
        run: |
          mkdir -p ~/.buildozer/android/platform/
          ln -sfn $ANDROID_HOME ~/.buildozer/android/platform/android-sdk
          mkdir -p $ANDROID_HOME/tools/bin
          ln -sfn $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager \\
                  $ANDROID_HOME/tools/bin/sdkmanager
      - name: Cache Buildozer
        uses: actions/cache@v4
        with:
          path: ~/.buildozer
          key: buildozer-${{ runner.os }}-${{ hashFiles('buildozer.spec') }}
      - name: Install Buildozer
        run: pip install buildozer cython==0.29.36
      - name: Build APK
        run: |
          buildozer -v android debug 2>&1 | tee build.log
          exit ${PIPESTATUS[0]}
      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: DorkMaster-APK
          path: bin/*.apk
          if-no-files-found: error
      - name: Upload build log on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: build-log
          path: build.log
""".strip()

_write_if_missing("buildozer.spec", _BUILDOZER_SPEC)
_write_if_missing(".github/workflows/build.yml", _GH_WORKFLOW)

os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("PYTHONUTF8", "1")

import concurrent.futures
import json
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import random

try:
    import requests as _req
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    _req.packages.urllib3.disable_warnings(InsecureRequestWarning)
    _REQUESTS = True
except ImportError:
    _REQUESTS = False

try:
    import kivy
    kivy.require("2.0.0")
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.lang import Builder
    from kivy.metrics import dp
    from kivy.properties import BooleanProperty, ListProperty, StringProperty
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.recycleview import RecycleView
    from kivy.uix.recycleview.views import RecycleDataViewBehavior
    from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.textinput import TextInput
    from kivy.uix.widget import Widget
    from kivy.graphics import Color, RoundedRectangle
    _KIVY = True
except ImportError as _ke:
    _KIVY = False
    print(f"[WARN] Kivy not available: {_ke}")

# ═══════════════════════════════════════════════════════════════
#  MODELS
# ═══════════════════════════════════════════════════════════════

def _utcnow(): return datetime.now(timezone.utc)

def _write_text_safe(path, data):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", errors="replace", newline="\n") as f:
        f.write(data)

@dataclass
class DorkResult:
    query: str; url: str; snippet: str = ""
    source_engine: str = "google"; domain: str = ""
    def __hash__(self): return hash(self.url)
    def __eq__(self, o): return isinstance(o, DorkResult) and self.url == o.url

@dataclass
class SecretHit:
    pattern_name: str; matched_value: str
    context_line: str; source_url: str = ""

@dataclass
class Finding:
    severity: str; category: str; title: str; url: str
    description: str = ""; evidence: str = ""
    secrets: list = field(default_factory=list)
    timestamp: datetime = field(default_factory=_utcnow)
    def severity_rank(self):
        return {"critical":4,"high":3,"medium":2,"low":1,"info":0}.get(self.severity,0)

@dataclass
class Target:
    domain: str
    urls: list = field(default_factory=list)
    dork_results: list = field(default_factory=list)
    findings: list = field(default_factory=list)
    pulled_files: list = field(default_factory=list)
    rule_summary: list = field(default_factory=list)
    def add_finding(self, f): self.findings.append(f)
    def add_result(self, r):
        if r not in self.dork_results:
            self.dork_results.append(r); self.urls.append(r.url)
    def add_pulled(self, e): self.pulled_files.append(e)
    def note_rule(self, l): self.rule_summary.append(l)

# ═══════════════════════════════════════════════════════════════
#  DORK CATEGORIES  (full lists)
# ═══════════════════════════════════════════════════════════════

def _s(d): return f"site:{d}"

DORK_CATS = {
"credentials": lambda d: [
    f'{_s(d)} intitle:"index of" "leak" filetype:txt',
    f'{_s(d)} intitle:"index of" "passwords" filetype:txt',
    f'{_s(d)} intitle:"index of" "credentials"',
    f'{_s(d)} filetype:txt intext:"username" intext:"password"',
    f'{_s(d)} filetype:cfg intext:"password"',
    f'{_s(d)} filetype:ini intext:"password="',
    f'{_s(d)} filetype:xml intext:"password"',
    f'{_s(d)} filetype:yml intext:"password"',
    f'{_s(d)} filetype:yaml intext:"password"',
    f'{_s(d)} filetype:json intext:"password"',
    f'{_s(d)} filetype:conf intext:"password"',
    f'{_s(d)} filetype:properties intext:"password"',
    f'{_s(d)} intext:"db_password" filetype:php',
    f'{_s(d)} filetype:txt intext:"passwd"',
    f'{_s(d)} filetype:txt intext:"login:" intext:"password:"',
    f'{_s(d)} inurl:"/.htpasswd"',
    f'{_s(d)} intitle:"index of" ".htpasswd"',
    f'{_s(d)} intitle:"index of" "shadow"',
    f'{_s(d)} filetype:reg intext:"password"',
    f'{_s(d)} filetype:ps1 intext:"password"',
    f'{_s(d)} filetype:sh intext:"password="',
    f'{_s(d)} filetype:bat intext:"password="',
    f'intext:"username" intext:"password" intext:"{d}" filetype:txt',
],
"logs": lambda d: [
    f'{_s(d)} intitle:"index of" "access.log"',
    f'{_s(d)} intitle:"index of" "error.log"',
    f'{_s(d)} filetype:log intext:"password"',
    f'{_s(d)} filetype:log intext:"Authorization"',
    f'{_s(d)} filetype:log intext:"bearer"',
    f'{_s(d)} filetype:log intext:"api_key"',
    f'{_s(d)} filetype:log intext:"secret"',
    f'{_s(d)} filetype:log intext:"token"',
    f'{_s(d)} inurl:/logs/ intitle:"index of"',
    f'{_s(d)} filetype:log intext:"Basic "',
    f'{_s(d)} intitle:"index of" "debug.log"',
    f'{_s(d)} intitle:"index of" "laravel.log"',
    f'{_s(d)} intitle:"index of" "application.log"',
    f'{_s(d)} intitle:"index of" "server.log"',
    f'{_s(d)} intitle:"index of" "audit.log"',
    f'{_s(d)} intitle:"index of" "trace.log"',
],
"databases": lambda d: [
    f'{_s(d)} filetype:sql intext:"INSERT INTO" intext:"password"',
    f'{_s(d)} intitle:"index of" filetype:sql',
    f'{_s(d)} inurl:"/phpmyadmin/" intext:"Welcome to phpMyAdmin"',
    f'{_s(d)} inurl:phpmyadmin intitle:"phpMyAdmin" intext:"root"',
    f'{_s(d)} inurl:adminer.php intitle:"Login"',
    f'{_s(d)} inurl:adminer intitle:"adminer"',
    f'{_s(d)} filetype:mdb inurl:".mdb"',
    f'{_s(d)} filetype:db inurl:".db"',
    f'{_s(d)} filetype:sqlite inurl:".sqlite"',
    f'{_s(d)} intitle:"index of" "database.sql"',
    f'{_s(d)} intitle:"index of" "dump.sql"',
    f'{_s(d)} filetype:sql "CREATE TABLE" "password"',
    f'{_s(d)} filetype:sql "users" "email" "password"',
    f'{_s(d)} inurl:":9200/_cat/indices"',
    f'{_s(d)} inurl:":27017" intitle:"mongo"',
    f'{_s(d)} inurl:":6379" intitle:"redis"',
    f'{_s(d)} inurl:":5984/_all_dbs"',
    f'{_s(d)} inurl:":8086/query"',
],
"git": lambda d: [
    f'{_s(d)} intitle:"index of" ".git"',
    f'{_s(d)} inurl:"/.git/config" intext:"url ="',
    f'{_s(d)} inurl:"/.git/HEAD" intext:"ref:"',
    f'{_s(d)} intitle:"index of" ".git/logs"',
    f'{_s(d)} inurl:"/.git/COMMIT_EDITMSG"',
    f'{_s(d)} inurl:"/.git/packed-refs"',
    f'{_s(d)} inurl:"/.git/description"',
    f'{_s(d)} intitle:"index of" ".svn"',
    f'{_s(d)} intitle:"index of" ".hg"',
    f'{_s(d)} inurl:"/.hg/store"',
    f'{_s(d)} intitle:"index of" ".bzr"',
    f'intitle:"index of" ".git" "{d}"',
],
"env": lambda d: [
    f'{_s(d)} filetype:env intext:"DB_PASSWORD"',
    f'{_s(d)} filetype:env intext:"DB_USER" intext:"DB_PASS"',
    f'{_s(d)} inurl:".env" intext:"APP_KEY"',
    f'{_s(d)} inurl:".env.local"',
    f'{_s(d)} inurl:".env.production"',
    f'{_s(d)} inurl:".env.development"',
    f'{_s(d)} inurl:".env.backup"',
    f'{_s(d)} inurl:".env.bak"',
    f'{_s(d)} filetype:env "AWS_SECRET_ACCESS_KEY"',
    f'{_s(d)} filetype:env "AWS_ACCESS_KEY_ID"',
    f'{_s(d)} filetype:env "STRIPE_SECRET"',
    f'{_s(d)} filetype:env "TWILIO_AUTH_TOKEN"',
    f'{_s(d)} filetype:env "SENDGRID_API_KEY"',
    f'{_s(d)} filetype:env "MAILGUN_API_KEY"',
    f'{_s(d)} filetype:env "GITHUB_TOKEN"',
    f'{_s(d)} filetype:env "SLACK_BOT_TOKEN"',
    f'{_s(d)} filetype:env "DISCORD_TOKEN"',
    f'{_s(d)} filetype:env "TELEGRAM_BOT_TOKEN"',
    f'{_s(d)} filetype:env "SECRET_KEY"',
    f'{_s(d)} filetype:env "JWT_SECRET"',
    f'{_s(d)} filetype:env "DATABASE_URL"',
    f'{_s(d)} filetype:env "REDIS_URL"',
    f'{_s(d)} filetype:env "GOOGLE_API_KEY"',
    f'{_s(d)} filetype:env "OPENAI_API_KEY"',
    f'{_s(d)} filetype:env "ANTHROPIC_API_KEY"',
    f'{_s(d)} inurl:"/.env" -filetype:php',
    f'{_s(d)} filetype:env "PRIVATE_KEY"',
],
"backups": lambda d: [
    f'{_s(d)} filetype:bak inurl:"wp-config"',
    f'{_s(d)} filetype:txt intext:"wp-config" intext:"DB_PASSWORD"',
    f'{_s(d)} intitle:"index of" "wp-config.php.bak"',
    f'{_s(d)} intitle:"index of" filetype:bak',
    f'{_s(d)} intitle:"index of" "backup"',
    f'{_s(d)} intitle:"index of" "backup.zip"',
    f'{_s(d)} intitle:"index of" "backup.tar.gz"',
    f'{_s(d)} intitle:"index of" "backup.rar"',
    f'{_s(d)} intitle:"index of" ".sql.gz"',
    f'{_s(d)} filetype:zip inurl:"backup"',
    f'{_s(d)} filetype:tar.gz inurl:"backup"',
    f'{_s(d)} filetype:7z inurl:"backup"',
    f'{_s(d)} intitle:"index of" "config.php.bak"',
    f'{_s(d)} inurl:".bak" filetype:bak',
    f'{_s(d)} inurl:".old" filetype:php',
    f'{_s(d)} inurl:".swp"',
    f'{_s(d)} intitle:"index of" "database.bak"',
],
"stealer": lambda d: [
    f'{_s(d)} intitle:"index of" "stealer" filetype:txt',
    f'{_s(d)} intitle:"index of" "logs" intext:"@gmail.com" filetype:txt',
    f'{_s(d)} intitle:"index of" "passwords.txt"',
    f'{_s(d)} intitle:"index of" "combolist"',
    f'{_s(d)} intitle:"index of" "combo.txt"',
    f'{_s(d)} filetype:txt intext:"@gmail.com" intext:"password"',
    f'{_s(d)} filetype:txt intext:"@yahoo.com" intext:"password"',
    f'{_s(d)} intitle:"index of" "leaked"',
    f'{_s(d)} intitle:"index of" "dumps"',
    f'{_s(d)} filetype:txt intext:"URL:" intext:"USER:" intext:"PASS:"',
    f'intext:"{d}" intext:"password" filetype:txt -site:{d}',
    f'"{d}" "password" filetype:txt',
],
"admin": lambda d: [
    f'{_s(d)} inurl:admin intitle:"login"',
    f'{_s(d)} inurl:administrator intitle:"login"',
    f'{_s(d)} inurl:/wp-admin/ intitle:"WordPress"',
    f'{_s(d)} inurl:"/manager/html" intitle:"Tomcat"',
    f'{_s(d)} inurl:"/jenkins" intitle:"Dashboard"',
    f'{_s(d)} inurl:8080 intitle:"Jenkins"',
    f'{_s(d)} inurl:grafana intitle:"Grafana"',
    f'{_s(d)} inurl:kibana intitle:"Kibana"',
    f'{_s(d)} inurl:":5601" intitle:"Kibana"',
    f'{_s(d)} inurl:":9090" intitle:"Prometheus"',
    f'{_s(d)} inurl:"/admin/login"',
    f'{_s(d)} inurl:"/panel" intitle:"login"',
    f'{_s(d)} inurl:"/cpanel"',
    f'{_s(d)} inurl:":8888" intitle:"Jupyter"',
    f'{_s(d)} inurl:"/flower" intitle:"Celery"',
    f'{_s(d)} inurl:":15672" intitle:"RabbitMQ"',
    f'{_s(d)} inurl:":8443" intitle:"Portainer"',
    f'{_s(d)} inurl:":3000" intitle:"Grafana"',
    f'{_s(d)} inurl:":8500" intitle:"Consul"',
    f'{_s(d)} intitle:"RabbitMQ Management"',
],
"cloud": lambda d: [
    f'site:s3.amazonaws.com inurl:{d}',
    f'site:blob.core.windows.net inurl:{d}',
    f'site:storage.googleapis.com inurl:{d}',
    f'site:s3.amazonaws.com inurl:{d.replace(".","")}'
    f'inurl:".s3.amazonaws.com"',
    f'filetype:json intext:"aws_access_key_id"',
    f'filetype:json intext:"client_secret"',
    f'{_s(d)} filetype:json intext:"aws_access_key_id"',
    f'{_s(d)} intext:"s3.amazonaws.com" intext:"bucket"',
    f'"{d}" site:s3.amazonaws.com',
    f'{_s(d)} intext:"blob.core.windows.net"',
    f'{_s(d)} intext:"digitaloceanspaces.com"',
    f'{_s(d)} intext:"cloudfront.net"',
],
"cms": lambda d: [
    f'{_s(d)} inurl:wp-content/uploads filetype:php',
    f'{_s(d)} inurl:wp-config.php.txt',
    f'{_s(d)} inurl:wp-config.php.bak',
    f'{_s(d)} inurl:"/wp-json/wp/v2/users"',
    f'{_s(d)} inurl:xmlrpc.php',
    f'{_s(d)} inurl:wp-login.php',
    f'{_s(d)} filetype:php inurl:"wp-config.php"',
    f'{_s(d)} inurl:"/administrator/index.php" intitle:"Joomla"',
    f'{_s(d)} inurl:"/sites/default/settings.php" intitle:"Drupal"',
    f'{_s(d)} inurl:"/app/etc/local.xml" intext:"crypt_key"',
    f'{_s(d)} inurl:"/typo3/" intitle:"TYPO3"',
    f'{_s(d)} inurl:"/ghost/" intitle:"Ghost"',
],
"network": lambda d: [
    f'{_s(d)} intitle:"router" inurl:admin intext:"password"',
    f'{_s(d)} intitle:"webcamXP" inurl:8080',
    f'{_s(d)} intitle:"Live View / - AXIS"',
    f'{_s(d)} inurl:ViewerFrame?Mode=',
    f'{_s(d)} intitle:"index of" "DCIM"',
    f'{_s(d)} intitle:"DVR Login" intext:"password"',
    f'{_s(d)} intitle:"Hikvision" inurl:login',
    f'{_s(d)} intitle:"Network Camera" inurl:axis-cgi',
    f'{_s(d)} inurl:":10000" intitle:"Webmin"',
    f'{_s(d)} inurl:":2082" intitle:"cPanel"',
    f'{_s(d)} intitle:"TP-LINK" inurl:admin',
    f'{_s(d)} intitle:"D-Link" inurl:admin',
    f'{_s(d)} intitle:"pfSense" inurl:index.php',
    f'{_s(d)} intitle:"OpenWrt" inurl:cgi-bin',
    f'{_s(d)} intitle:"SonicWall" inurl:auth',
],
"apikeys": lambda d: [
    f'{_s(d)} filetype:js intext:"api_key"',
    f'{_s(d)} filetype:js intext:"apiKey"',
    f'{_s(d)} filetype:js intext:"AIza"',
    f'{_s(d)} filetype:js intext:"AKIA"',
    f'{_s(d)} filetype:js intext:"pk_live_"',
    f'{_s(d)} filetype:js intext:"sk_live_"',
    f'{_s(d)} filetype:js intext:"eyJ"',
    f'{_s(d)} filetype:js intext:"firebase"',
    f'{_s(d)} filetype:json intext:"apiKey"',
    f'{_s(d)} filetype:json intext:"api_key"',
    f'{_s(d)} filetype:json intext:"client_id"',
    f'{_s(d)} filetype:xml intext:"apikey"',
    f'{_s(d)} filetype:php intext:"api_key"',
    f'{_s(d)} inurl:"config.js"',
    f'{_s(d)} inurl:"config.json"',
    f'{_s(d)} inurl:"credentials.json"',
    f'{_s(d)} inurl:"service-account.json"',
    f'{_s(d)} inurl:"google-services.json"',
    f'{_s(d)} inurl:"firebase.json"',
    f'{_s(d)} inurl:"secrets.yml"',
    f'{_s(d)} inurl:"secret.json"',
    f'{_s(d)} inurl:"apikeys.js"',
],
"pastebin": lambda d: [
    f'site:pastebin.com "{d}"',
    f'site:pastebin.com "{d}" password',
    f'site:ghostbin.co "{d}"',
    f'site:rentry.co "{d}"',
    f'site:hastebin.com "{d}"',
    f'site:paste.ee "{d}"',
    f'site:controlc.com "{d}"',
    f'site:dpaste.org "{d}"',
    f'site:ideone.com "{d}"',
    f'site:pastebin.com "{d}" mysql',
    f'site:pastebin.com "{d}" token',
    f'site:pastebin.com "{d}" api',
    f'site:pastebin.com "{d}" DB_PASSWORD',
    f'site:pastebin.com "{d}" .env',
    f'"{d}" site:pastebin.com',
    f'"{d}" filetype:txt intext:"password"',
],
"github": lambda d: [
    f'site:github.com "{d}" password',
    f'site:github.com "{d}" api_key',
    f'site:github.com "{d}" secret',
    f'site:github.com "{d}" .env',
    f'site:github.com "{d}" DB_PASSWORD',
    f'site:github.com "{d}" AWS_SECRET_ACCESS_KEY',
    f'site:github.com "{d}" private_key',
    f'site:gitlab.com "{d}" password',
    f'site:gitlab.com "{d}" api_key',
    f'site:bitbucket.org "{d}" password',
    f'site:gist.github.com "{d}"',
    f'site:raw.githubusercontent.com "{d}"',
    f'site:github.com "{d}" filetype:env',
    f'site:github.com "{d}" filetype:json "private_key"',
],
"jira": lambda d: [
    f'{_s(d)} inurl:/jira/ intext:"issue"',
    f'{_s(d)} inurl:"/confluence/" intext:"spaces"',
    f'{_s(d)} inurl:"/wiki/" intext:"confluence"',
    f'{_s(d)} inurl:"/servicedesk/"',
    f'{_s(d)} inurl:"/secure/Dashboard.jspa"',
    f'{_s(d)} inurl:"/rest/api/2/"',
    f'{_s(d)} intitle:"Dashboard - Jira"',
    f'{_s(d)} intitle:"Log in - Confluence"',
    f'site:*.atlassian.net "{d}"',
    f'site:*.atlassian.net "{d}" password',
    f'site:*.atlassian.net "{d}" token',
],
"s3": lambda d: [
    f'site:s3.amazonaws.com "{d.replace(".","-")}"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-backup"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-dev"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-prod"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-assets"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-media"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-uploads"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-logs"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-static"',
    f'site:storage.googleapis.com "{d.replace(".","-")}"',
    f'site:blob.core.windows.net "{d.replace(".","-")}"',
    f'site:digitaloceanspaces.com "{d.replace(".","-")}"',
    f'site:*.r2.cloudflarestorage.com "{d.replace(".","-")}"',
],
"emails": lambda d: [
    f'{_s(d)} intext:"@{d}" filetype:txt',
    f'{_s(d)} intext:"@{d}" filetype:csv',
    f'{_s(d)} intext:"@{d}" filetype:xls',
    f'{_s(d)} intitle:"index of" "email" filetype:txt',
    f'{_s(d)} intitle:"index of" "contacts" filetype:csv',
    f'{_s(d)} intitle:"index of" "users" filetype:csv',
    f'{_s(d)} intitle:"index of" "subscribers" filetype:csv',
    f'"{d}" intext:"@" filetype:csv',
    f'site:linkedin.com/in "{d}"',
    f'site:github.com "{d}" intext:"@"',
    f'"{d}" filetype:vcf',
],
"errors": lambda d: [
    f'{_s(d)} intext:"Fatal error"',
    f'{_s(d)} intext:"Warning: mysqli"',
    f'{_s(d)} intext:"Warning: mysql_"',
    f'{_s(d)} intext:"Stack trace"',
    f'{_s(d)} intext:"Traceback (most recent call last)"',
    f'{_s(d)} intext:"at org.springframework"',
    f'{_s(d)} intext:"java.lang.NullPointerException"',
    f'{_s(d)} inurl:"phpinfo.php"',
    f'{_s(d)} inurl:"/server-status"',
    f'{_s(d)} inurl:"/debug"',
    f'{_s(d)} inurl:"/actuator"',
    f'{_s(d)} inurl:"/actuator/env"',
    f'{_s(d)} inurl:"/actuator/heapdump"',
    f'{_s(d)} intitle:"Whoops!" intext:"Laravel"',
    f'{_s(d)} intitle:"Werkzeug" intext:"Traceback"',
    f'{_s(d)} inurl:"/telescope"',
    f'{_s(d)} inurl:"/horizon"',
],
"xmlrpc": lambda d: [
    f'{_s(d)} inurl:"xmlrpc.php"',
    f'{_s(d)} inurl:"/wp-json/"',
    f'{_s(d)} inurl:"/wp-json/wp/v2/users"',
    f'{_s(d)} inurl:"?wsdl"',
    f'{_s(d)} inurl:"/services/" intitle:"SOAP"',
    f'{_s(d)} inurl:":8080/jmx-console"',
    f'{_s(d)} inurl:"/rest/api/"',
    f'{_s(d)} inurl:"/api/v1/" intitle:"swagger"',
    f'{_s(d)} inurl:"/swagger-ui.html"',
    f'{_s(d)} inurl:"/api-docs"',
    f'{_s(d)} inurl:"/v2/api-docs"',
    f'{_s(d)} intitle:"Swagger UI"',
],
}

ALL_CATS = list(DORK_CATS.keys())

# ═══════════════════════════════════════════════════════════════
#  SECRET SCANNER
# ═══════════════════════════════════════════════════════════════

_SECRET_PATTERNS = [
    ("AWS_ACCESS_KEY",      re.compile(r'AKIA[0-9A-Z]{16}')),
    ("AWS_ACCESS_KEY_V2",   re.compile(r'ASIA[0-9A-Z]{16}')),
    ("GCP_API_KEY",         re.compile(r'AIza[0-9A-Za-z\-_]{35}')),
    ("GITHUB_TOKEN",        re.compile(r'ghp_[a-zA-Z0-9]{36}')),
    ("GITHUB_TOKEN_V2",     re.compile(r'github_pat_[a-zA-Z0-9_]{82}')),
    ("GITHUB_OAUTH",        re.compile(r'gho_[a-zA-Z0-9]{36}')),
    ("GITLAB_TOKEN",        re.compile(r'glpat-[a-zA-Z0-9_\-]{20,}')),
    ("STRIPE_SECRET",       re.compile(r'sk_live_[a-zA-Z0-9]{24,}')),
    ("STRIPE_PK",           re.compile(r'pk_live_[a-zA-Z0-9]{24,}')),
    ("OPENAI_KEY",          re.compile(r'sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}')),
    ("OPENAI_KEY_V2",       re.compile(r'sk-proj-[a-zA-Z0-9_\-]{40,}')),
    ("ANTHROPIC_KEY",       re.compile(r'sk-ant-[a-zA-Z0-9_\-]{40,}')),
    ("HUGGINGFACE_TOKEN",   re.compile(r'hf_[a-zA-Z0-9]{34,}')),
    ("SLACK_TOKEN",         re.compile(r'xox[baprs]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]+')),
    ("SLACK_WEBHOOK",       re.compile(r'https://hooks\.slack\.com/services/T[a-zA-Z0-9]+/B[a-zA-Z0-9]+/[a-zA-Z0-9]+')),
    ("DISCORD_WEBHOOK",     re.compile(r'https://discord\.com/api/webhooks/\d+/[a-zA-Z0-9_\-]+')),
    ("DISCORD_TOKEN",       re.compile(r'[MN][a-zA-Z0-9]{23}\.[a-zA-Z0-9\-_]{6}\.[a-zA-Z0-9\-_]{27}')),
    ("TELEGRAM_BOT",        re.compile(r'\d{9,10}:[a-zA-Z0-9_\-]{35}')),
    ("SENDGRID_KEY",        re.compile(r'SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43}')),
    ("TWILIO_SID",          re.compile(r'AC[a-zA-Z0-9]{32}')),
    ("FIREBASE_KEY",        re.compile(r'AAAA[A-Za-z0-9_\-]{7}:[A-Za-z0-9_\-]{140}')),
    ("PRIVATE_KEY_RSA",     re.compile(r'-----BEGIN RSA PRIVATE KEY-----')),
    ("PRIVATE_KEY_OPENSSH", re.compile(r'-----BEGIN OPENSSH PRIVATE KEY-----')),
    ("PRIVATE_KEY_EC",      re.compile(r'-----BEGIN EC PRIVATE KEY-----')),
    ("PRIVATE_KEY_PGP",     re.compile(r'-----BEGIN PGP PRIVATE KEY BLOCK-----')),
    ("DB_PASSWORD",         re.compile(r'DB_PASS(?:WORD)?\s*[=:]\s*\S+')),
    ("DATABASE_URL",        re.compile(r'(?:mysql|postgres|postgresql|mongodb|redis|amqp)://[^\s"\']+')),
    ("BEARER_TOKEN",        re.compile(r'Bearer\s+[a-zA-Z0-9\-_\.]{20,}')),
    ("BASIC_AUTH",          re.compile(r'Authorization:\s*Basic\s+[a-zA-Z0-9+/=]{20,}')),
    ("JWT",                 re.compile(r'eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+')),
    ("SHOPIFY_TOKEN",       re.compile(r'shpat_[a-fA-F0-9]{32}')),
    ("DIGITALOCEAN_TOKEN",  re.compile(r'dop_v1_[a-f0-9]{64}')),
    ("HEROKU_API_KEY",      re.compile(r'heroku[a-zA-Z0-9]{32}')),
    ("SECRET_KEY_GENERIC",  re.compile(r'(?i)(?:secret[_\-]?key|api[_\-]?key)\s*[=:]\s*["\']?([a-zA-Z0-9\-_]{16,})')),
    ("EMAIL_PASSWORD",      re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}:\S{4,}')),
]

def scan_text(text: str, source_url: str = "") -> list:
    hits = []; lines = text.splitlines(); seen = set()
    for name, pat in _SECRET_PATTERNS:
        for line in lines:
            for m in pat.finditer(line):
                val = m.group(0)[:120]; key = (name, val)
                if key in seen: continue
                seen.add(key)
                hits.append(SecretHit(name, val, line.strip()[:200], source_url))
    return hits

# ═══════════════════════════════════════════════════════════════
#  HTTP SESSION  (pure requests, no C extensions)
# ═══════════════════════════════════════════════════════════════

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
]

def _make_session(proxy=None):
    s = _req.Session()
    s.headers.update({
        "User-Agent":      random.choice(_UA_POOL),
        "Accept":          "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "DNT":             "1",
    })
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    s.verify = False
    return s

_CAPTCHA_SIGS = ["detected unusual traffic","recaptcha","captcha","/sorry/"]
def _is_captcha(b): return any(s in b.lower() for s in _CAPTCHA_SIGS)

def _extract_google_urls(html):
    urls = []
    for m in re.finditer(r'/url\?q=(https?://[^&"\'<> ]+)', html):
        url = urllib.parse.unquote(m.group(1))
        if not any(s in url for s in ("google.com","googleadservices","webcache")):
            urls.append(url)
    return list(dict.fromkeys(urls))

def _extract_bing_urls(html):
    urls = []
    for m in re.finditer(
        r'<h2[^>]*>\s*<a[^>]+href=["\']?(https?://[^"\'<> ]+)["\']?',
        html, re.IGNORECASE):
        url = m.group(1)
        if not any(s in url for s in ("bing.com","microsoft.com")):
            urls.append(url)
    return list(dict.fromkeys(urls))

def _google_search(query, session, pages=2):
    results = []
    for page in range(pages):
        params = urllib.parse.urlencode({
            "q": query, "start": page*10, "num": 10,
            "hl": "en", "safe": "off"})
        try:
            r = session.get(f"https://www.google.com/search?{params}", timeout=15)
            body = r.text
            if not body or _is_captcha(body): time.sleep(3); continue
            for u in _extract_google_urls(body):
                results.append(DorkResult(query=query, url=u, source_engine="google"))
            if "did not match" in body.lower(): break
        except Exception: break
    return results

def _bing_search(query, session, pages=2):
    results = []
    for page in range(pages):
        params = urllib.parse.urlencode({"q": query, "first": page*10+1, "count": 10})
        try:
            r = session.get(f"https://www.bing.com/search?{params}", timeout=15)
            urls = _extract_bing_urls(r.text)
            for u in urls:
                results.append(DorkResult(query=query, url=u, source_engine="bing"))
            if not urls: break
        except Exception: break
    return results

def _ddg_search(query, session):
    try:
        data = urllib.parse.urlencode({"q": query, "b": "", "kl": "us-en"})
        r = session.post("https://html.duckduckgo.com/html/", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://html.duckduckgo.com/"}, timeout=15)
        body = r.text
        if not body: return []
        urls = [urllib.parse.unquote(m) for m in re.findall(r'uddg=([^&"\'<> ]+)', body)]
        return [DorkResult(query=query, url=u, source_engine="ddg") for u in urls]
    except Exception: return []

def _pull_url(url, session, size_limit_mb=5.0):
    size_limit = int(size_limit_mb * 1024 * 1024)
    try:
        r = session.get(url, timeout=15, stream=True)
        data = b""
        for chunk in r.iter_content(8192):
            data += chunk
            if len(data) > size_limit:
                return {"url": url, "error": "too large", "content": ""}
        return {"url": url, "content": data.decode("utf-8", errors="replace"), "type": "text"}
    except Exception as e:
        return {"url": url, "error": str(e), "content": ""}

# ═══════════════════════════════════════════════════════════════
#  SCAN ENGINE
# ═══════════════════════════════════════════════════════════════

@dataclass
class ScanConfig:
    domain: str
    engines: list = field(default_factory=lambda: ["google"])
    categories: list = field(default_factory=lambda: ["all"])
    proxy: Optional[str] = None
    delay: float = 3.0
    pages: int = 2
    threads: int = 6
    no_probe: bool = False
    size_limit_mb: float = 5.0
    output_dir: str = "./results"

class ScanEngine:
    def __init__(self, config: ScanConfig,
                 on_log=None, on_url=None, on_finding=None):
        self.config = config
        self.on_log = on_log or (lambda m, lv="info": None)
        self.on_url = on_url or (lambda u: None)
        self.on_finding = on_finding or (lambda f: None)
        self._stop = False

    def stop(self): self._stop = True

    def run(self) -> Target:
        session = _make_session(self.config.proxy)
        target = Target(domain=self.config.domain)
        try:
            self._phase_dorks(target, session)
            if not self.config.no_probe and not self._stop:
                self._phase_probe(target, session)
        finally:
            session.close()
            self._write_report(target)
        return target

    def _phase_dorks(self, target, session):
        cats = self.config.categories
        queries = []
        for cat, fn in DORK_CATS.items():
            if cats == ["all"] or cat in cats:
                queries.extend(fn(self.config.domain))
        queries = list(dict.fromkeys(queries))
        self.on_log(f"Generated {len(queries)} queries", "info")

        def fire(q):
            if self._stop: return []
            time.sleep(max(0.5, self.config.delay + random.uniform(-0.5, 0.5)))
            results = []
            for eng in self.config.engines:
                try:
                    if eng == "google":
                        results.extend(_google_search(q, session, self.config.pages))
                    elif eng == "bing":
                        results.extend(_bing_search(q, session, self.config.pages))
                    elif eng == "ddg":
                        results.extend(_ddg_search(q, session))
                except Exception as e:
                    self.on_log(f"[{eng}] {e}", "warn")
            return results

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=self.config.threads) as ex:
            futs = {ex.submit(fire, q): q for q in queries}
            for fut in concurrent.futures.as_completed(futs):
                if self._stop: break
                try:
                    for r in (fut.result() or []):
                        r.domain = target.domain
                        target.add_result(r)
                        self.on_url(r.url)
                except Exception: pass

        self.on_log(f"Dork phase: {len(target.dork_results)} unique URLs", "ok")

    def _phase_probe(self, target, session):
        for url in [r.url for r in target.dork_results
                    if ".env" in r.url.lower()][:10]:
            if self._stop: break
            pf = _pull_url(url, session, self.config.size_limit_mb)
            if pf and pf.get("content"):
                target.add_pulled(pf)
                hits = scan_text(pf["content"], url)
                f = Finding(
                    severity="critical" if hits else "medium",
                    category="env_exposure",
                    title=f".env exposed" + (f" — {len(hits)} secrets" if hits else ""),
                    url=url,
                    evidence="\n".join(
                        f"{h.pattern_name}: {h.matched_value[:80]}"
                        for h in hits[:20]),
                    secrets=hits)
                target.add_finding(f); self.on_finding(f)

        for url in [r.url for r in target.dork_results
                    if ".git" in r.url][:5]:
            if self._stop: break
            base = (url.split("/.git/")[0] + "/.git" if "/.git/" in url
                    else url.rstrip("/") + "/.git")
            for gf in ["HEAD", "config", "COMMIT_EDITMSG"]:
                try:
                    r = session.get(base + "/" + gf, timeout=10)
                    if r.status_code == 200 and len(r.text) > 10:
                        hits = scan_text(r.text, url)
                        f = Finding(
                            severity="critical" if hits else "high",
                            category="git_exposure",
                            title=f"Exposed .git/{gf}"
                                  + (f" — {len(hits)} secrets" if hits else ""),
                            url=url, evidence=r.text[:1000], secrets=hits)
                        target.add_finding(f); self.on_finding(f); break
                except Exception: pass

        for url in [r.url for r in target.dork_results
                    if r.url.lower().endswith((".sql", ".sql.gz"))][:5]:
            if self._stop: break
            pf = _pull_url(url, session, self.config.size_limit_mb)
            if pf and pf.get("content"):
                target.add_pulled(pf)
                hits = scan_text(pf["content"], url)
                f = Finding(
                    severity="critical" if hits else "high",
                    category="sql_exposure",
                    title=f"Exposed SQL dump"
                          + (f" — {len(hits)} secrets" if hits else ""),
                    url=url, evidence=pf["content"][:500], secrets=hits)
                target.add_finding(f); self.on_finding(f)

        for pf in target.pulled_files:
            if not pf.get("content"): continue
            hits = scan_text(pf["content"], pf.get("url", ""))
            if hits:
                f = Finding(
                    severity="critical", category="secrets",
                    title=f"Secrets in pulled file — {len(hits)} hits",
                    url=pf.get("url", ""),
                    evidence="\n".join(
                        f"{h.pattern_name}: {h.matched_value[:80]}"
                        for h in hits[:20]),
                    secrets=hits)
                target.add_finding(f); self.on_finding(f)

        self.on_log(f"Probe phase: {len(target.findings)} findings", "ok")

    def _write_report(self, target):
        out = Path(self.config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        lines = [
            "=" * 60,
            f"DorkMaster Report — {target.domain}",
            f"Generated: {_utcnow().isoformat()}",
            "=" * 60,
            f"URLs: {len(target.urls)}  Findings: {len(target.findings)}", "",
        ]
        for i, f in enumerate(sorted(target.findings,
                key=lambda x: x.severity_rank(), reverse=True), 1):
            lines += [f"[{i}] {f.severity.upper()} | {f.category}",
                      f"    {f.title}", f"    {f.url}", ""]
        lines.append("ALL URLS:")
        lines.extend(f"  {u}" for u in target.urls)
        _write_text_safe(out / "report.txt", "\n".join(lines) + "\n")
        data = {
            "domain": target.domain, "urls": target.urls,
            "findings": [
                {"severity": f.severity, "category": f.category,
                 "title": f.title, "url": f.url,
                 "evidence": f.evidence[:500]}
                for f in sorted(target.findings,
                    key=lambda x: x.severity_rank(), reverse=True)
            ]
        }
        _write_text_safe(out / "report.json",
                         json.dumps(data, indent=2, ensure_ascii=False))
        self.on_log(f"Report saved → {out}", "ok")


# ═══════════════════════════════════════════════════════════════
#  KIVY UI
# ═══════════════════════════════════════════════════════════════

if _KIVY:

    BG    = (0.06, 0.06, 0.08, 1)
    PANEL = (0.10, 0.10, 0.13, 1)
    PANEL2= (0.14, 0.14, 0.18, 1)
    ACCENT= (0.20, 0.60, 1.00, 1)
    ACCENT2=(0.10, 0.80, 0.50, 1)
    DANGER= (1.00, 0.25, 0.25, 1)
    WARN  = (1.00, 0.75, 0.10, 1)
    TEXT  = (0.92, 0.92, 0.92, 1)
    DIM   = (0.50, 0.50, 0.55, 1)

    SEV_COL = {
        "critical": [1.0, 0.25, 0.25, 1],
        "high":     [1.0, 0.55, 0.10, 1],
        "medium":   [1.0, 0.80, 0.10, 1],
        "low":      [0.2, 0.80, 0.50, 1],
        "info":     [0.5, 0.50, 0.55, 1],
    }

    KV = """
#:import dp kivy.metrics.dp

<DarkInput@TextInput>:
    background_color: app.PANEL
    foreground_color: app.TEXT
    cursor_color: app.ACCENT
    hint_text_color: app.DIM
    padding: dp(10), dp(10)
    multiline: False
    font_size: dp(14)

<AccentBtn@Button>:
    background_normal: ''
    background_down: ''
    background_color: app.ACCENT
    color: 1,1,1,1
    font_size: dp(13)
    bold: True

<DangerBtn@Button>:
    background_normal: ''
    background_down: ''
    background_color: app.DANGER
    color: 1,1,1,1
    font_size: dp(13)

<PanelBtn@Button>:
    background_normal: ''
    background_down: ''
    background_color: app.PANEL
    color: app.ACCENT
    font_size: dp(13)

<TabBar>:
    size_hint_y: None
    height: dp(42)
    spacing: dp(4)
    padding: [dp(6), dp(4)]
    canvas.before:
        Color:
            rgba: app.PANEL
        Rectangle:
            pos: self.pos
            size: self.size

<FindingRow>:
    orientation: 'vertical'
    padding: dp(10), dp(6)
    spacing: dp(3)
    size_hint_y: None
    height: dp(82)
    canvas.before:
        Color:
            rgba: 0.12, 0.12, 0.16, 1
        RoundedRectangle:
            pos: self.x + dp(4), self.y + dp(2)
            size: self.width - dp(8), self.height - dp(4)
            radius: [dp(8)]
    Label:
        text: root.sev_text
        font_size: dp(11)
        bold: True
        color: root.sev_color
        size_hint_y: None
        height: dp(18)
        halign: 'left'
        text_size: self.size
    Label:
        text: root.title_text
        font_size: dp(13)
        color: app.TEXT
        size_hint_y: None
        height: dp(22)
        halign: 'left'
        text_size: self.size
    Label:
        text: root.url_text
        font_size: dp(10)
        color: app.DIM
        size_hint_y: None
        height: dp(16)
        halign: 'left'
        text_size: self.size
    BoxLayout:
        size_hint_y: None
        height: dp(22)
        spacing: dp(6)
        Button:
            text: 'Open in browser'
            font_size: dp(10)
            size_hint_x: 0.5
            background_normal: ''
            background_color: app.ACCENT
            color: 1,1,1,1
            on_release: app.open_in_browser(root.url_text)
        Button:
            text: 'Copy URL'
            font_size: dp(10)
            size_hint_x: 0.5
            background_normal: ''
            background_color: app.PANEL
            color: app.ACCENT
            on_release: app.copy_url(root.url_text)

<UrlRow>:
    orientation: 'horizontal'
    size_hint_y: None
    height: dp(44)
    padding: dp(6), dp(4)
    spacing: dp(6)
    canvas.before:
        Color:
            rgba: 0.10, 0.10, 0.13, 1
        RoundedRectangle:
            pos: self.x + dp(2), self.y + dp(1)
            size: self.width - dp(4), self.height - dp(2)
            radius: [dp(6)]
    Label:
        text: root.url_text
        font_size: dp(11)
        color: app.TEXT
        halign: 'left'
        text_size: self.width, None
        shorten: True
        shorten_from: 'right'
    Button:
        text: 'Go'
        size_hint_x: None
        width: dp(40)
        font_size: dp(12)
        background_normal: ''
        background_color: app.ACCENT
        color: 1,1,1,1
        on_release: app.open_in_browser(root.url_text)

<ScanScreen>:
    name: 'scan'
    canvas.before:
        Color:
            rgba: app.BG
        Rectangle:
            pos: self.pos
            size: self.size
    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(14), dp(14)
            spacing: dp(10)

            Label:
                text: '[b][color=33aaff]DorkMaster[/color] v4.3[/b]'
                markup: True
                font_size: dp(22)
                size_hint_y: None
                height: dp(38)
                halign: 'left'
                text_size: self.size

            Label:
                text: 'Target Domain'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            DarkInput:
                id: domain_input
                hint_text: 'example.com'
                size_hint_y: None
                height: dp(44)

            Label:
                text: 'Search Engines'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            BoxLayout:
                size_hint_y: None
                height: dp(38)
                spacing: dp(6)
                CatToggle:
                    id: tb_google
                    text: 'Google'
                    active: True
                CatToggle:
                    id: tb_bing
                    text: 'Bing'
                    active: False
                CatToggle:
                    id: tb_ddg
                    text: 'DDG'
                    active: False

            Label:
                text: 'Dork Categories'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            BoxLayout:
                size_hint_y: None
                height: dp(32)
                spacing: dp(6)
                PanelBtn:
                    text: 'All'
                    on_release: root.ids.cat_grid.select_all()
                PanelBtn:
                    text: 'None'
                    on_release: root.ids.cat_grid.deselect_all()

            CatGrid:
                id: cat_grid

            Label:
                text: 'Proxy  (optional)'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            DarkInput:
                id: proxy_input
                hint_text: 'socks5h://127.0.0.1:9050'
                size_hint_y: None
                height: dp(40)

            Label:
                text: 'Delay (sec)  /  Pages per query'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            BoxLayout:
                size_hint_y: None
                height: dp(40)
                spacing: dp(8)
                DarkInput:
                    id: delay_input
                    hint_text: '3.0'
                DarkInput:
                    id: pages_input
                    hint_text: '2'

            BoxLayout:
                size_hint_y: None
                height: dp(44)
                spacing: dp(10)
                AccentBtn:
                    id: scan_btn
                    text: 'SCAN'
                    on_release: app.start_scan()
                DangerBtn:
                    id: stop_btn
                    text: 'STOP'
                    disabled: True
                    on_release: app.stop_scan()

            Label:
                id: status_lbl
                text: 'idle'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(24)
                halign: 'left'
                text_size: self.size

<ResultsScreen>:
    name: 'results'
    canvas.before:
        Color:
            rgba: app.BG
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10), dp(10)
        spacing: dp(6)

        Label:
            id: results_title
            text: 'Results'
            font_size: dp(16)
            bold: True
            color: app.TEXT
            size_hint_y: None
            height: dp(30)
            halign: 'left'
            text_size: self.size

        Label:
            id: results_stats
            text: ''
            font_size: dp(12)
            color: app.DIM
            size_hint_y: None
            height: dp(20)
            halign: 'left'
            text_size: self.size

        BoxLayout:
            size_hint_y: None
            height: dp(32)
            spacing: dp(6)
            Label:
                text: 'Filter:'
                color: app.DIM
                font_size: dp(12)
                size_hint_x: None
                width: dp(40)
            DarkInput:
                id: filter_input
                hint_text: 'filter by keyword…'
                on_text: app.apply_filter(self.text)
                multiline: False
                font_size: dp(12)
                size_hint_y: None
                height: dp(32)

        RecycleView:
            id: findings_rv
            viewclass: 'FindingRow'
            RecycleBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                default_size: None, dp(82)
                default_size_hint: 1, None
                spacing: dp(6)
                padding: dp(4)

        Label:
            id: no_findings_lbl
            text: ''
            font_size: dp(13)
            color: app.DIM
            size_hint_y: None
            height: dp(36)
            halign: 'center'
            text_size: self.size

<BrowserScreen>:
    name: 'browser'
    canvas.before:
        Color:
            rgba: app.BG
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(8), dp(8)
        spacing: dp(6)

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(6)
            DarkInput:
                id: url_bar
                hint_text: 'https://...'
                multiline: False
                font_size: dp(13)
                on_minimum_height: self.height = self.minimum_height
            AccentBtn:
                text: 'Go'
                size_hint_x: None
                width: dp(50)
                on_release: app.browser_go()

        BoxLayout:
            size_hint_y: None
            height: dp(32)
            spacing: dp(6)
            PanelBtn:
                text: '< Back'
                size_hint_x: None
                width: dp(70)
                on_release: app.browser_back()
            PanelBtn:
                text: 'Fwd >'
                size_hint_x: None
                width: dp(70)
                on_release: app.browser_forward()
            PanelBtn:
                text: 'Reload'
                size_hint_x: None
                width: dp(70)
                on_release: app.browser_reload()
            Label:
                id: browser_title
                text: 'Browser'
                font_size: dp(12)
                color: app.DIM
                halign: 'left'
                text_size: self.size

        ScrollView:
            id: page_scroll
            Label:
                id: page_content
                text: ''
                markup: True
                font_size: dp(12)
                color: app.TEXT
                size_hint_y: None
                height: self.texture_size[1]
                text_size: self.width, None
                padding: dp(6), dp(6)
                valign: 'top'
                halign: 'left'

<UrlsScreen>:
    name: 'urls'
    canvas.before:
        Color:
            rgba: app.BG
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10), dp(10)
        spacing: dp(6)

        BoxLayout:
            size_hint_y: None
            height: dp(32)
            spacing: dp(8)
            Label:
                text: 'All Found URLs'
                font_size: dp(15)
                bold: True
                color: app.TEXT
                halign: 'left'
                text_size: self.size
            Label:
                id: url_count
                text: ''
                font_size: dp(12)
                color: app.DIM
                size_hint_x: None
                width: dp(80)
                halign: 'right'
                text_size: self.size

        DarkInput:
            id: url_filter
            hint_text: 'filter URLs…'
            size_hint_y: None
            height: dp(36)
            on_text: app.filter_urls(self.text)

        RecycleView:
            id: urls_rv
            viewclass: 'UrlRow'
            RecycleBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                default_size: None, dp(44)
                default_size_hint: 1, None
                spacing: dp(4)
                padding: dp(4)

<LogScreen>:
    name: 'log'
    canvas.before:
        Color:
            rgba: app.BG
        Rectangle:
            pos: self.pos
            size: self.size
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10), dp(10)
        spacing: dp(6)

        BoxLayout:
            size_hint_y: None
            height: dp(32)
            spacing: dp(8)
            Label:
                text: 'Live Log'
                font_size: dp(15)
                bold: True
                color: app.TEXT
                halign: 'left'
                text_size: self.size
            PanelBtn:
                text: 'Clear'
                size_hint_x: None
                width: dp(60)
                on_release: app.clear_log()

        ScrollView:
            id: log_scroll
            Label:
                id: log_label
                text: ''
                markup: True
                font_size: dp(11)
                color: app.TEXT
                size_hint_y: None
                height: self.texture_size[1]
                text_size: self.width, None
                padding: dp(4), dp(4)
                valign: 'top'
                halign: 'left'

<CatToggle>:
    size_hint_y: None
    height: dp(32)
    font_size: dp(11)
    canvas.before:
        Color:
            rgba: app.ACCENT if self.active else app.PANEL
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]
"""

    # ── widgets ────────────────────────────────────────────────────

    class TabBar(BoxLayout): pass

    class CatToggle(Button):
        active = BooleanProperty(False)
        def on_release(self): self.active = not self.active

    class CatGrid(BoxLayout):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.orientation = "vertical"
            self.size_hint_y = None
            self.spacing = dp(4)
            self.bind(minimum_height=self.setter("height"))
            self._toggles = {}
            Clock.schedule_once(lambda dt: self._build(), 0)

        def _build(self):
            row = None
            for i, cat in enumerate(ALL_CATS):
                if i % 3 == 0:
                    row = BoxLayout(size_hint_y=None, height=dp(34), spacing=dp(4))
                    self.add_widget(row)
                tb = CatToggle(text=cat, active=True)
                self._toggles[cat] = tb
                row.add_widget(tb)
            if row:
                rem = len(ALL_CATS) % 3
                if rem:
                    for _ in range(3 - rem): row.add_widget(Widget())

        def selected(self): return [c for c, t in self._toggles.items() if t.active]
        def select_all(self):
            for t in self._toggles.values(): t.active = True
        def deselect_all(self):
            for t in self._toggles.values(): t.active = False

    class FindingRow(RecycleDataViewBehavior, BoxLayout):
        sev_text   = StringProperty("")
        title_text = StringProperty("")
        url_text   = StringProperty("")
        sev_color  = ListProperty([0.9, 0.9, 0.9, 1])
        def refresh_view_attrs(self, rv, index, data):
            self.sev_text   = data.get("sev_text", "")
            self.title_text = data.get("title_text", "")
            self.url_text   = data.get("url_text", "")
            self.sev_color  = data.get("sev_color", [0.9, 0.9, 0.9, 1])
            return super().refresh_view_attrs(rv, index, data)

    class UrlRow(RecycleDataViewBehavior, BoxLayout):
        url_text = StringProperty("")
        def refresh_view_attrs(self, rv, index, data):
            self.url_text = data.get("url_text", "")
            return super().refresh_view_attrs(rv, index, data)

    class ScanScreen(Screen):   pass
    class ResultsScreen(Screen): pass
    class BrowserScreen(Screen): pass
    class UrlsScreen(Screen):   pass
    class LogScreen(Screen):    pass

    # ── app ────────────────────────────────────────────────────────

    class DorkMasterApp(App):
        BG    = ListProperty(list(BG))
        PANEL = ListProperty(list(PANEL))
        PANEL2= ListProperty(list(PANEL2))
        ACCENT= ListProperty(list(ACCENT))
        ACCENT2=ListProperty(list(ACCENT2))
        DANGER= ListProperty(list(DANGER))
        WARN  = ListProperty(list(WARN))
        TEXT  = ListProperty(list(TEXT))
        DIM   = ListProperty(list(DIM))

        def build(self):
            Builder.load_string(KV)
            Window.clearcolor = BG

            self.sm = ScreenManager(transition=SlideTransition())
            for name, cls in [
                ("scan",    ScanScreen),
                ("results", ResultsScreen),
                ("browser", BrowserScreen),
                ("urls",    UrlsScreen),
                ("log",     LogScreen),
            ]:
                self.sm.add_widget(cls(name=name))

            root = BoxLayout(orientation="vertical")

            # tab bar
            tabs = TabBar()
            tab_defs = [
                ("Scan",    "scan"),
                ("Findings","results"),
                ("Browser", "browser"),
                ("URLs",    "urls"),
                ("Log",     "log"),
            ]
            for label, screen in tab_defs:
                btn = Button(
                    text=label, font_size=dp(12),
                    background_normal="", background_color=PANEL,
                    color=list(ACCENT))
                btn.bind(on_release=lambda inst, s=screen:
                         setattr(self.sm, "current", s))
                tabs.add_widget(btn)

            root.add_widget(tabs)
            root.add_widget(self.sm)

            # state
            self._log_lines: list[str] = []
            self._findings_data: list[dict] = []
            self._findings_all: list[dict] = []
            self._urls_data: list[dict] = []
            self._urls_all: list[dict] = []
            self._engine: Optional[ScanEngine] = None
            self._thread: Optional[threading.Thread] = None
            self._current_target: Optional[Target] = None
            self._browser_history: list[str] = []
            self._browser_idx: int = -1

            Clock.schedule_once(lambda dt:
                self.sm.get_screen("scan").ids.cat_grid.select_all(), 0.2)

            return root

        # ── log ───────────────────────────────────────────────────

        def _append_log(self, msg: str, level: str = "info"):
            col = {"ok":"33cc77","warn":"ffcc00","err":"ff4444","info":"aabbff"}.get(level,"eeeeee")
            ts  = datetime.now().strftime("%H:%M:%S")
            self._log_lines.append(f"[color={col}][{ts}] {msg}[/color]")
            if len(self._log_lines) > 600:
                self._log_lines = self._log_lines[-500:]
            def _upd(dt):
                try:
                    lbl = self.sm.get_screen("log").ids.log_label
                    lbl.text = "\n".join(self._log_lines[-250:])
                    self.sm.get_screen("log").ids.log_scroll.scroll_y = 0
                except: pass
            Clock.schedule_once(_upd, 0)

        def clear_log(self):
            self._log_lines = []
            try: self.sm.get_screen("log").ids.log_label.text = ""
            except: pass

        # ── findings ──────────────────────────────────────────────

        def _add_finding(self, finding: Finding):
            entry = {
                "sev_text":   finding.severity.upper() + "  •  " + finding.category,
                "title_text": finding.title[:65],
                "url_text":   finding.url[:80],
                "sev_color":  SEV_COL.get(finding.severity, [0.9,0.9,0.9,1]),
            }
            self._findings_all.append(entry)
            self._findings_data.append(entry)
            def _upd(dt):
                try:
                    rs = self.sm.get_screen("results")
                    rs.ids.findings_rv.data = list(self._findings_data)
                    rs.ids.findings_rv.refresh_from_data()
                    rs.ids.results_stats.text = (
                        f"{len(self._findings_data)} finding(s)  •  "
                        f"{len(self._urls_data)} URL(s)")
                    rs.ids.no_findings_lbl.text = ""
                except: pass
            Clock.schedule_once(_upd, 0)

        def apply_filter(self, keyword: str):
            kw = keyword.lower().strip()
            if kw:
                self._findings_data = [
                    e for e in self._findings_all
                    if kw in e["title_text"].lower()
                    or kw in e["url_text"].lower()
                    or kw in e["sev_text"].lower()
                ]
            else:
                self._findings_data = list(self._findings_all)
            def _upd(dt):
                try:
                    rv = self.sm.get_screen("results").ids.findings_rv
                    rv.data = list(self._findings_data)
                    rv.refresh_from_data()
                except: pass
            Clock.schedule_once(_upd, 0)

        # ── urls tab ──────────────────────────────────────────────

        def _add_url(self, url: str):
            self._append_log(f"  {url[:90]}", "info")
            entry = {"url_text": url}
            self._urls_all.append(entry)
            self._urls_data.append(entry)
            def _upd(dt):
                try:
                    us = self.sm.get_screen("urls")
                    us.ids.urls_rv.data = list(self._urls_data)
                    us.ids.urls_rv.refresh_from_data()
                    us.ids.url_count.text = f"{len(self._urls_data)} URLs"
                except: pass
            Clock.schedule_once(_upd, 0)

        def filter_urls(self, keyword: str):
            kw = keyword.lower().strip()
            self._urls_data = (
                [e for e in self._urls_all if kw in e["url_text"].lower()]
                if kw else list(self._urls_all))
            def _upd(dt):
                try:
                    rv = self.sm.get_screen("urls").ids.urls_rv
                    rv.data = list(self._urls_data)
                    rv.refresh_from_data()
                except: pass
            Clock.schedule_once(_upd, 0)

        # ── browser ───────────────────────────────────────────────

        def open_in_browser(self, url: str):
            if not url or not url.startswith("http"): return
            self._browser_history = self._browser_history[:self._browser_idx+1]
            self._browser_history.append(url)
            self._browser_idx = len(self._browser_history) - 1
            self.sm.current = "browser"
            self._browser_load(url)

        def browser_go(self):
            try:
                url = self.sm.get_screen("browser").ids.url_bar.text.strip()
                if url: self.open_in_browser(url)
            except: pass

        def browser_back(self):
            if self._browser_idx > 0:
                self._browser_idx -= 1
                self._browser_load(self._browser_history[self._browser_idx])

        def browser_forward(self):
            if self._browser_idx < len(self._browser_history) - 1:
                self._browser_idx += 1
                self._browser_load(self._browser_history[self._browser_idx])

        def browser_reload(self):
            if 0 <= self._browser_idx < len(self._browser_history):
                self._browser_load(self._browser_history[self._browser_idx])

        def _browser_load(self, url: str):
            def _upd(dt):
                try:
                    bs = self.sm.get_screen("browser")
                    bs.ids.url_bar.text = url
                    bs.ids.browser_title.text = "Loading…"
                    bs.ids.page_content.text = "[color=aabbff]Loading…[/color]"
                    bs.ids.page_scroll.scroll_y = 1
                except: pass
            Clock.schedule_once(_upd, 0)

            def _fetch():
                try:
                    session = _make_session()
                    r = session.get(url, timeout=20)
                    html = r.text
                    session.close()
                    # strip tags, convert links to plain text
                    text = re.sub(r'<script[^>]*>.*?</script>', '',
                                  html, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r'<style[^>]*>.*?</style>', '',
                                  text, flags=re.DOTALL | re.IGNORECASE)
                    # extract links
                    links = re.findall(r'href=["\']?(https?://[^"\'<> ]+)', html)
                    links = list(dict.fromkeys(links))[:60]
                    # plain text body
                    plain = re.sub(r'<[^>]+>', ' ', text)
                    plain = re.sub(r'[ \t]+', ' ', plain)
                    plain = re.sub(r'\n{3,}', '\n\n', plain)
                    plain = plain.strip()[:8000]

                    title_m = re.search(r'<title[^>]*>(.*?)</title>', html,
                                        re.IGNORECASE | re.DOTALL)
                    title = title_m.group(1).strip()[:60] if title_m else url[:60]

                    # build display
                    lines = [
                        f"[b][color=33aaff]{title}[/color][/b]",
                        f"[color=888888]{url}[/color]",
                        "",
                        plain,
                        "",
                        "[b][color=33aaff]— Links found —[/color][/b]",
                    ]
                    for lnk in links:
                        lines.append(f"[color=55aaff][ref={lnk}]{lnk[:80]}[/ref][/color]")

                    def _show(dt):
                        try:
                            bs = self.sm.get_screen("browser")
                            lbl = bs.ids.page_content
                            lbl.markup = True
                            lbl.text = "\n".join(lines)
                            lbl.bind(on_ref_press=lambda inst, val:
                                     self.open_in_browser(val))
                            bs.ids.browser_title.text = title
                            bs.ids.page_scroll.scroll_y = 1
                        except: pass
                    Clock.schedule_once(_show, 0)

                except Exception as e:
                    def _err(dt):
                        try:
                            bs = self.sm.get_screen("browser")
                            bs.ids.page_content.text = (
                                f"[color=ff4444]Error loading page:[/color]\n{e}")
                            bs.ids.browser_title.text = "Error"
                        except: pass
                    Clock.schedule_once(_err, 0)

            threading.Thread(target=_fetch, daemon=True).start()

        def copy_url(self, url: str):
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(url)
                self._append_log(f"Copied: {url[:60]}", "ok")
            except Exception as e:
                self._append_log(f"Copy failed: {e}", "warn")

        # ── scan control ──────────────────────────────────────────

        def _set_scan_active(self, active: bool):
            def _upd(dt):
                try:
                    ss = self.sm.get_screen("scan")
                    ss.ids.scan_btn.disabled = active
                    ss.ids.stop_btn.disabled = not active
                except: pass
            Clock.schedule_once(_upd, 0)

        def _set_status(self, msg: str):
            def _upd(dt):
                try: self.sm.get_screen("scan").ids.status_lbl.text = msg
                except: pass
            Clock.schedule_once(_upd, 0)

        def start_scan(self):
            try:
                ss = self.sm.get_screen("scan")
                domain = ss.ids.domain_input.text.strip()
            except: return
            if not domain:
                self._append_log("enter a domain first", "warn"); return
            for pref in ("https://", "http://"):
                if domain.startswith(pref): domain = domain[len(pref):]
            domain = domain.rstrip("/")

            engines = []
            try:
                if ss.ids.tb_google.active: engines.append("google")
                if ss.ids.tb_bing.active:   engines.append("bing")
                if ss.ids.tb_ddg.active:    engines.append("ddg")
            except: pass
            if not engines: engines = ["google"]

            try: cats = ss.ids.cat_grid.selected() or ["all"]
            except: cats = ["all"]
            try: proxy = ss.ids.proxy_input.text.strip() or None
            except: proxy = None
            try: delay = float(ss.ids.delay_input.text.strip() or "3.0")
            except: delay = 3.0
            try: pages = int(ss.ids.pages_input.text.strip() or "2")
            except: pages = 2

            cfg = ScanConfig(domain=domain, engines=engines,
                             categories=cats, proxy=proxy,
                             delay=delay, pages=pages, threads=6)

            # reset state
            self._findings_all = []; self._findings_data = []
            self._urls_all = [];     self._urls_data = []

            def _reset(dt):
                try:
                    rs = self.sm.get_screen("results")
                    rs.ids.findings_rv.data = []
                    rs.ids.findings_rv.refresh_from_data()
                    rs.ids.results_title.text = f"Results — {domain}"
                    rs.ids.results_stats.text = ""
                    rs.ids.no_findings_lbl.text = "scanning…"
                    if hasattr(rs.ids, "filter_input"):
                        rs.ids.filter_input.text = ""
                    us = self.sm.get_screen("urls")
                    us.ids.urls_rv.data = []
                    us.ids.urls_rv.refresh_from_data()
                    us.ids.url_count.text = "0 URLs"
                    if hasattr(us.ids, "url_filter"):
                        us.ids.url_filter.text = ""
                except: pass
            Clock.schedule_once(_reset, 0)

            self._append_log(
                f"Starting: {domain}  engines={engines}  cats={len(cats)}", "ok")
            self._set_status("scanning…")
            self._set_scan_active(True)

            self._engine = ScanEngine(
                cfg,
                on_log=lambda m, lv="info": Clock.schedule_once(
                    lambda dt: self._append_log(m, lv), 0),
                on_url=lambda u: Clock.schedule_once(
                    lambda dt: self._add_url(u), 0),
                on_finding=lambda f: self._add_finding(f),
            )

            def _thread_fn():
                try:
                    target = self._engine.run()
                    self._current_target = target
                    Clock.schedule_once(lambda dt: self._scan_done(target), 0)
                except Exception as exc:
                    Clock.schedule_once(lambda dt: (
                        self._append_log(f"FATAL: {exc!r}", "err"),
                        self._set_scan_active(False)), 0)

            self._thread = threading.Thread(target=_thread_fn, daemon=True)
            self._thread.start()

        def stop_scan(self):
            if self._engine: self._engine.stop()
            self._append_log("stop requested", "warn")
            self._set_status("stopping…")

        def _scan_done(self, target: Target):
            self._set_scan_active(False)
            n = len(target.findings); u = len(target.urls)
            self._set_status(f"done — {u} URLs  {n} finding(s)")
            self._append_log(f"Scan complete: {u} URLs, {n} findings", "ok")
            def _upd(dt):
                try:
                    rs = self.sm.get_screen("results")
                    rs.ids.results_stats.text = (
                        f"{u} URLs  •  {n} findings")
                    rs.ids.no_findings_lbl.text = (
                        "" if n else "No findings — check URLs tab")
                    us = self.sm.get_screen("urls")
                    us.ids.url_count.text = f"{u} URLs"
                except: pass
            Clock.schedule_once(_upd, 0)
            self.sm.current = "results"

    def run_app(): DorkMasterApp().run()


# ═══════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if _KIVY:
        run_app()
    else:
        import argparse
        ap = argparse.ArgumentParser(description="DorkMaster engine-only")
        ap.add_argument("domain")
        ap.add_argument("--engines", default="google")
        ap.add_argument("--proxy",   default=None)
        ap.add_argument("--no-probe", action="store_true")
        ap.add_argument("--cats",    default="all")
        args = ap.parse_args()
        cfg = ScanConfig(
            domain=args.domain,
            engines=[e.strip() for e in args.engines.split(",")],
            categories=[c.strip() for c in args.cats.split(",")],
            proxy=args.proxy, no_probe=args.no_probe)
        def _log(m, lv="info"): print(f"[{lv.upper()}] {m}")
        engine = ScanEngine(cfg, on_log=_log,
            on_url=lambda u: print(f"  URL  {u}"),
            on_finding=lambda f: print(f"  [{f.severity.upper()}] {f.title}"))
        engine.run()
