#!/usr/bin/env python3

from __future__ import annotations

# ── bootstrap: write build files if missing ──────────────────────────────
import os, sys, pathlib

def _write_if_missing(path: str, content: str) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        p.write_text(content, encoding="utf-8")
        print(f"[bootstrap] wrote {path}")

_BUILDOZER_SPEC = r"""
[app]
title = DorkMaster
package.name = dorkmaster
package.domain = org.dorkmaster
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 4.0.0
requirements = python3,kivy==2.3.0,aiohttp,aiohttp-socks,certifi,charset-normalizer,multidict,yarl,frozenlist,aiosignal,attrs
orientation = portrait
osx.python_version = 3
osx.kivy_version = 2.3.0
fullscreen = 0
android.permissions = INTERNET,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a,armeabi-v7a
android.allow_backup = True
android.logcat_filters = *:S python:D
[buildozer]
log_level = 2
warn_on_root = 1
""".strip()

_GH_WORKFLOW = r"""
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

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install system deps
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y \
            git zip unzip openjdk-17-jdk autoconf libtool \
            pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev \
            libtinfo5 cmake libffi-dev libssl-dev \
            python3-pip build-essential ccache

      - name: Cache Buildozer global
        uses: actions/cache@v4
        with:
          path: ~/.buildozer
          key: buildozer-${{ runner.os }}-${{ hashFiles('buildozer.spec') }}

      - name: Install Buildozer
        run: pip install buildozer cython==0.29.36

      - name: Build APK
        run: |
          buildozer -v android debug 2>&1 | tail -200
        env:
          ANDROID_HOME: /usr/local/lib/android/sdk

      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: DorkMaster-APK
          path: bin/*.apk
          if-no-files-found: error
""".strip()

_write_if_missing("buildozer.spec", _BUILDOZER_SPEC)
_write_if_missing(".github/workflows/build.yml", _GH_WORKFLOW)

# ── Kivy environment setup (must happen before kivy import) ───────────────
os.environ.setdefault("KIVY_NO_ENV_CONFIG", "1")
os.environ.setdefault("PYTHONUTF8", "1")

# ── stdlib ────────────────────────────────────────────────────────────────
import asyncio
import io
import json
import re
import threading
import time
import types
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Kivy ──────────────────────────────────────────────────────────────────
try:
    import kivy
    kivy.require("2.0.0")
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.core.window import Window
    from kivy.lang import Builder
    from kivy.metrics import dp
    from kivy.properties import (BooleanProperty, ListProperty,
                                  NumericProperty, ObjectProperty,
                                  StringProperty)
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.floatlayout import FloatLayout
    from kivy.uix.label import Label
    from kivy.uix.modalview import ModalView
    from kivy.uix.popup import Popup
    from kivy.uix.recycleview import RecycleView
    from kivy.uix.recycleview.views import RecycleDataViewBehavior
    from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.spinner import Spinner
    from kivy.uix.textinput import TextInput
    from kivy.uix.togglebutton import ToggleButton
    from kivy.uix.widget import Widget
    _KIVY = True
except ImportError as _kivy_err:
    _KIVY = False
    print(f"[WARN] Kivy not available: {_kivy_err}  —  running engine-only mode")


# ════════════════════════════════════════════════════════════════════════════
#  EMBEDDED ENGINE  (DorkMaster v4, stripped of argparse / __main__)
# ════════════════════════════════════════════════════════════════════════════

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _slug_url(url: str, max_len: int = 120) -> str:
    import hashlib
    h = hashlib.sha1(url.encode("utf-8", errors="replace")).hexdigest()[:8]
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in url)
    return f"{safe[:max_len]}_{h}"

def _read_text_safe(path) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

def _write_text_safe(path, data: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", errors="replace", newline="\n") as f:
        f.write(data)


# ── models ────────────────────────────────────────────────────────────────

@dataclass
class DorkResult:
    query: str
    url: str
    snippet: str = ""
    source_engine: str = "google"
    domain: str = ""
    timestamp: datetime = field(default_factory=_utcnow)
    def __hash__(self): return hash(self.url)
    def __eq__(self, o): return isinstance(o, DorkResult) and self.url == o.url

@dataclass
class SecretHit:
    pattern_name: str
    matched_value: str
    context_line: str
    source_url: str = ""

@dataclass
class Finding:
    severity: str
    category: str
    title: str
    url: str
    description: str = ""
    evidence: str = ""
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
    shodan_data: list = field(default_factory=list)
    rule_summary: list = field(default_factory=list)
    def add_finding(self, f): self.findings.append(f)
    def add_result(self, r):
        if r not in self.dork_results:
            self.dork_results.append(r)
            self.urls.append(r.url)
    def add_pulled(self, e): self.pulled_files.append(e)
    def note_rule(self, l): self.rule_summary.append(l)


# ── session ───────────────────────────────────────────────────────────────

try:
    import aiohttp
    from aiohttp import ClientSession, TCPConnector, CookieJar
    _AIOHTTP = True
except ImportError:
    _AIOHTTP = False

try:
    from aiohttp_socks import ProxyConnector
    _SOCKS_OK = True
except ImportError:
    _SOCKS_OK = False

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

import random

def _is_soft_cancel():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        return False
    if task is None:
        return False
    cancelling = getattr(task, "cancelling", None)
    if callable(cancelling):
        try:
            return cancelling() == 0
        except Exception:
            return False
    return True


class DorkSession:
    def __init__(self, proxy=None, proxy_list=None,
                 delay=3.0, max_conn=8, timeout=20):
        self.proxy = proxy
        self.proxies = proxy_list or ([proxy] if proxy else [])
        self.delay = delay
        self.max_conn = max_conn
        self.timeout = aiohttp.ClientTimeout(total=timeout, connect=min(15,timeout)) if _AIOHTTP else None
        self._session = None
        self._last_req = 0.0
        self._proxy_idx = 0
        self._proxy_arg = None
        self._lock = asyncio.Lock()

    def _next_proxy(self):
        if not self.proxies:
            return None
        p = self.proxies[self._proxy_idx % len(self.proxies)]
        self._proxy_idx += 1
        return p

    def _headers(self, extra=None):
        h = {
            "User-Agent": random.choice(_UA_POOL),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
        }
        if extra:
            h.update(extra)
        return h

    async def _build_session(self, proxy=None):
        if proxy and proxy.startswith("socks") and _SOCKS_OK:
            connector = ProxyConnector.from_url(proxy, limit=self.max_conn, ssl=False)
            self._proxy_arg = None
        else:
            connector = TCPConnector(limit=self.max_conn, ssl=False,
                                     force_close=False, enable_cleanup_closed=True)
            self._proxy_arg = proxy
        return ClientSession(connector=connector,
                             cookie_jar=CookieJar(unsafe=True),
                             timeout=self.timeout)

    async def start(self):
        async with self._lock:
            if self._session is None or self._session.closed:
                self._session = await self._build_session(self._next_proxy())

    async def close(self):
        async with self._lock:
            s = self._session
            self._session = None
        if s:
            try:
                await s.close()
                await asyncio.sleep(0)
            except Exception:
                pass

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def _throttle(self):
        now = time.monotonic()
        wait = max(0.0, self.delay + random.uniform(-1,1) - (now - self._last_req))
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_req = time.monotonic()

    async def _request(self, method, url, retries=3, **kwargs):
        await self.start()
        await self._throttle()
        last_exc = RuntimeError("no attempts")
        for attempt in range(retries):
            async with self._lock:
                sess = self._session
                proxy_arg = self._proxy_arg
            call_kw = dict(kwargs)
            call_kw.setdefault("headers", self._headers())
            if proxy_arg:
                call_kw["proxy"] = proxy_arg
            try:
                return await sess.request(method, url, **call_kw)
            except asyncio.CancelledError as exc:
                if _is_soft_cancel():
                    last_exc = exc
                    await asyncio.sleep(0.5)
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    await asyncio.sleep(2**attempt + random.uniform(0.1,0.9))
        raise last_exc

    async def get(self, url, retries=3, **kw):
        return await self._request("GET", url, retries=retries, **kw)

    async def post(self, url, retries=3, **kw):
        return await self._request("POST", url, retries=retries, **kw)

    async def get_text(self, url, **kw):
        r = await self.get(url, **kw)
        try:
            return await r.text(errors="replace")
        finally:
            r.release()

    async def get_bytes(self, url, **kw):
        r = await self.get(url, **kw)
        try:
            return await r.read()
        finally:
            r.release()

    async def post_text(self, url, **kw):
        r = await self.post(url, **kw)
        try:
            return await r.text(errors="replace")
        finally:
            r.release()

    async def get_json(self, url, **kw):
        r = await self.get(url, **kw)
        try:
            return await r.json(content_type=None)
        finally:
            r.release()


# ── dork generators (all 20 categories) ──────────────────────────────────

def _d(domain):
    return f"site:{domain}"

DORK_CATS = {
"credentials": lambda d: [
    f'{_d(d)} filetype:txt intext:"username" intext:"password"',
    f'{_d(d)} filetype:cfg intext:"password"',
    f'{_d(d)} filetype:ini intext:"password="',
    f'{_d(d)} filetype:yml intext:"password"',
    f'{_d(d)} filetype:yaml intext:"password"',
    f'{_d(d)} filetype:json intext:"password"',
    f'{_d(d)} inurl:"/.htpasswd"',
    f'{_d(d)} intitle:"index of" "shadow"',
    f'{_d(d)} filetype:sh intext:"password="',
    f'{_d(d)} filetype:ps1 intext:"password"',
    f'intext:"username" intext:"password" intext:"{d}" filetype:txt',
],
"logs": lambda d: [
    f'{_d(d)} intitle:"index of" "access.log"',
    f'{_d(d)} intitle:"index of" "error.log"',
    f'{_d(d)} filetype:log intext:"password"',
    f'{_d(d)} filetype:log intext:"Authorization"',
    f'{_d(d)} filetype:log intext:"bearer"',
    f'{_d(d)} filetype:log intext:"api_key"',
    f'{_d(d)} filetype:log intext:"token"',
    f'{_d(d)} intitle:"index of" "debug.log"',
    f'{_d(d)} intitle:"index of" "laravel.log"',
],
"databases": lambda d: [
    f'{_d(d)} filetype:sql intext:"INSERT INTO" intext:"password"',
    f'{_d(d)} intitle:"index of" filetype:sql',
    f'{_d(d)} inurl:"/phpmyadmin/" intext:"Welcome to phpMyAdmin"',
    f'{_d(d)} inurl:adminer.php intitle:"Login"',
    f'{_d(d)} filetype:mdb inurl:".mdb"',
    f'{_d(d)} filetype:sqlite inurl:".sqlite"',
    f'{_d(d)} inurl:":9200/_cat/indices"',
    f'{_d(d)} inurl:":27017" intitle:"mongo"',
    f'{_d(d)} inurl:":6379" intitle:"redis"',
],
"git": lambda d: [
    f'{_d(d)} intitle:"index of" ".git"',
    f'{_d(d)} inurl:"/.git/config" intext:"url ="',
    f'{_d(d)} inurl:"/.git/HEAD" intext:"ref:"',
    f'{_d(d)} intitle:"index of" ".git/logs"',
    f'{_d(d)} inurl:"/.git/COMMIT_EDITMSG"',
    f'{_d(d)} intitle:"index of" ".svn"',
    f'intitle:"index of" ".git" "{d}"',
],
"env": lambda d: [
    f'{_d(d)} filetype:env intext:"DB_PASSWORD"',
    f'{_d(d)} inurl:".env" intext:"APP_KEY"',
    f'{_d(d)} inurl:".env.production"',
    f'{_d(d)} filetype:env "AWS_SECRET_ACCESS_KEY"',
    f'{_d(d)} filetype:env "AWS_ACCESS_KEY_ID"',
    f'{_d(d)} filetype:env "STRIPE_SECRET"',
    f'{_d(d)} filetype:env "OPENAI_API_KEY"',
    f'{_d(d)} filetype:env "SECRET_KEY"',
    f'{_d(d)} filetype:env "DATABASE_URL"',
    f'{_d(d)} filetype:env "PRIVATE_KEY"',
],
"backups": lambda d: [
    f'{_d(d)} filetype:bak inurl:"wp-config"',
    f'{_d(d)} intitle:"index of" "backup.zip"',
    f'{_d(d)} intitle:"index of" "backup.tar.gz"',
    f'{_d(d)} filetype:zip inurl:"backup"',
    f'{_d(d)} inurl:".bak" filetype:bak',
    f'{_d(d)} inurl:".swp"',
    f'{_d(d)} intitle:"index of" "database.bak"',
],
"admin": lambda d: [
    f'{_d(d)} inurl:admin intitle:"login"',
    f'{_d(d)} inurl:/wp-admin/ intitle:"WordPress"',
    f'{_d(d)} inurl:"/jenkins" intitle:"Dashboard"',
    f'{_d(d)} inurl:grafana intitle:"Grafana"',
    f'{_d(d)} inurl:kibana intitle:"Kibana"',
    f'{_d(d)} inurl:":5601" intitle:"Kibana"',
    f'{_d(d)} inurl:":9090" intitle:"Prometheus"',
    f'{_d(d)} intitle:"RabbitMQ Management"',
],
"cloud": lambda d: [
    f'site:s3.amazonaws.com inurl:{d}',
    f'site:blob.core.windows.net inurl:{d}',
    f'site:storage.googleapis.com inurl:{d}',
    f'filetype:json intext:"aws_access_key_id"',
    f'{_d(d)} intext:"s3.amazonaws.com" intext:"bucket"',
],
"s3": lambda d: [
    f'site:s3.amazonaws.com "{d.replace(".","-")}"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-backup"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-prod"',
    f'site:storage.googleapis.com "{d.replace(".","-")}"',
    f'site:blob.core.windows.net "{d.replace(".","-")}"',
],
"apikeys": lambda d: [
    f'{_d(d)} filetype:js intext:"api_key"',
    f'{_d(d)} filetype:js intext:"AIza"',
    f'{_d(d)} filetype:js intext:"AKIA"',
    f'{_d(d)} filetype:js intext:"pk_live_"',
    f'{_d(d)} filetype:js intext:"eyJ"',
    f'{_d(d)} inurl:"config.js"',
    f'{_d(d)} inurl:"service-account.json"',
    f'{_d(d)} inurl:"google-services.json"',
],
"pastebin": lambda d: [
    f'site:pastebin.com "{d}"',
    f'site:pastebin.com "{d}" password',
    f'site:pastebin.com "{d}" DB_PASSWORD',
    f'site:pastebin.com "{d}" token',
    f'site:ghostbin.co "{d}"',
    f'site:rentry.co "{d}"',
],
"github": lambda d: [
    f'site:github.com "{d}" password',
    f'site:github.com "{d}" api_key',
    f'site:github.com "{d}" .env',
    f'site:github.com "{d}" AWS_SECRET_ACCESS_KEY',
    f'site:gist.github.com "{d}"',
    f'site:gitlab.com "{d}" password',
],
"emails": lambda d: [
    f'{_d(d)} intext:"@{d}" filetype:csv',
    f'{_d(d)} intitle:"index of" "email" filetype:txt',
    f'"{d}" intext:"@" filetype:csv',
    f'site:linkedin.com/in "{d}"',
],
"errors": lambda d: [
    f'{_d(d)} intext:"Fatal error"',
    f'{_d(d)} intext:"Stack trace"',
    f'{_d(d)} intext:"Traceback (most recent call last)"',
    f'{_d(d)} inurl:"phpinfo.php"',
    f'{_d(d)} inurl:"/actuator/env"',
    f'{_d(d)} intitle:"Whoops!" intext:"Laravel"',
    f'{_d(d)} intitle:"Werkzeug" intext:"Traceback"',
],
"cms": lambda d: [
    f'{_d(d)} inurl:wp-config.php.bak',
    f'{_d(d)} inurl:"/wp-json/wp/v2/users"',
    f'{_d(d)} inurl:xmlrpc.php',
    f'{_d(d)} inurl:"/administrator/index.php" intitle:"Joomla"',
    f'{_d(d)} inurl:"/sites/default/settings.php" intitle:"Drupal"',
],
"network": lambda d: [
    f'{_d(d)} intitle:"webcamXP" inurl:8080',
    f'{_d(d)} intitle:"Live View / - AXIS"',
    f'{_d(d)} intitle:"Hikvision" inurl:login',
    f'{_d(d)} inurl:":10000" intitle:"Webmin"',
    f'{_d(d)} intitle:"pfSense" inurl:index.php',
],
"jira": lambda d: [
    f'{_d(d)} inurl:/jira/ intext:"issue"',
    f'{_d(d)} inurl:"/confluence/" intext:"spaces"',
    f'{_d(d)} intitle:"Dashboard - Jira"',
    f'site:*.atlassian.net "{d}"',
],
"xmlrpc": lambda d: [
    f'{_d(d)} inurl:"xmlrpc.php"',
    f'{_d(d)} inurl:"/swagger-ui.html"',
    f'{_d(d)} inurl:"/api-docs"',
    f'{_d(d)} intitle:"Swagger UI"',
],
"stealer": lambda d: [
    f'{_d(d)} intitle:"index of" "stealer" filetype:txt',
    f'{_d(d)} intitle:"index of" "combolist"',
    f'{_d(d)} filetype:txt intext:"URL:" intext:"USER:" intext:"PASS:"',
    f'intext:"{d}" intext:"password" filetype:txt -site:{d}',
],
}


# ── secret scanner (core patterns) ───────────────────────────────────────

_SECRET_PATTERNS = [
    ("AWS_ACCESS_KEY",   re.compile(r'AKIA[0-9A-Z]{16}')),
    ("GCP_API_KEY",      re.compile(r'AIza[0-9A-Za-z\-_]{35}')),
    ("GITHUB_TOKEN",     re.compile(r'ghp_[a-zA-Z0-9]{36}')),
    ("GITHUB_TOKEN_V2",  re.compile(r'github_pat_[a-zA-Z0-9_]{82}')),
    ("GITLAB_TOKEN",     re.compile(r'glpat-[a-zA-Z0-9_\-]{20,}')),
    ("STRIPE_SECRET",    re.compile(r'sk_live_[a-zA-Z0-9]{24,}')),
    ("OPENAI_KEY",       re.compile(r'sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}')),
    ("OPENAI_KEY_V2",    re.compile(r'sk-proj-[a-zA-Z0-9_\-]{40,}')),
    ("ANTHROPIC_KEY",    re.compile(r'sk-ant-[a-zA-Z0-9_\-]{40,}')),
    ("SLACK_TOKEN",      re.compile(r'xox[baprs]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]+')),
    ("SLACK_WEBHOOK",    re.compile(r'https://hooks\.slack\.com/services/T[a-zA-Z0-9]+/B[a-zA-Z0-9]+/[a-zA-Z0-9]+')),
    ("DISCORD_WEBHOOK",  re.compile(r'https://discord\.com/api/webhooks/\d+/[a-zA-Z0-9_\-]+')),
    ("PRIVATE_KEY_RSA",  re.compile(r'-----BEGIN RSA PRIVATE KEY-----')),
    ("PRIVATE_KEY_OPENSSH", re.compile(r'-----BEGIN OPENSSH PRIVATE KEY-----')),
    ("DB_PASSWORD",      re.compile(r'DB_PASS(?:WORD)?\s*[=:]\s*\S+')),
    ("DATABASE_URL",     re.compile(r'(?:mysql|postgres|postgresql|mongodb|redis)://[^\s"\']+')),
    ("BEARER_TOKEN",     re.compile(r'Bearer\s+[a-zA-Z0-9\-_\.]{20,}')),
    ("JWT",              re.compile(r'eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+')),
    ("SECRET_KEY_GENERIC", re.compile(r'(?i)(?:secret[_\-]?key|api[_\-]?key)\s*[=:]\s*["\']?([a-zA-Z0-9\-_]{16,})')),
    ("SENDGRID_KEY",     re.compile(r'SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43}')),
    ("TWILIO_SID",       re.compile(r'AC[a-zA-Z0-9]{32}')),
    ("FIREBASE_KEY",     re.compile(r'AAAA[A-Za-z0-9_\-]{7}:[A-Za-z0-9_\-]{140}')),
]

def scan_text(text: str, source_url: str = "") -> list:
    hits = []
    lines = text.splitlines()
    seen: set = set()
    for name, pat in _SECRET_PATTERNS:
        for line in lines:
            for m in pat.finditer(line):
                val = m.group(0)[:120]
                key = (name, val)
                if key in seen:
                    continue
                seen.add(key)
                hits.append(SecretHit(
                    pattern_name=name,
                    matched_value=val,
                    context_line=line.strip()[:200],
                    source_url=source_url,
                ))
    return hits


# ── search scrapers ───────────────────────────────────────────────────────

_CAPTCHA_SIGS = ["detected unusual traffic","recaptcha","captcha","/sorry/"]

def _is_captcha(body): return any(s in body.lower() for s in _CAPTCHA_SIGS)

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


async def google_search(query, session, pages=2):
    results = []
    for page in range(pages):
        start = page * 10
        params = urllib.parse.urlencode({"q":query,"start":start,"num":10,"hl":"en","safe":"off"})
        url = f"https://www.google.com/search?{params}"
        try:
            body = await session.get_text(url, retries=2)
            if not body or _is_captcha(body):
                await asyncio.sleep(3)
                continue
            for u in _extract_google_urls(body):
                results.append(DorkResult(query=query, url=u,
                                          source_engine="google"))
            if "did not match" in body.lower():
                break
        except Exception:
            break
    return results

async def bing_search(query, session, pages=2):
    results = []
    for page in range(pages):
        params = urllib.parse.urlencode({"q":query,"first":page*10+1,"count":10})
        url = f"https://www.bing.com/search?{params}"
        try:
            body = await session.get_text(url, retries=2)
            if not body:
                break
            for u in _extract_bing_urls(body):
                results.append(DorkResult(query=query, url=u,
                                          source_engine="bing"))
            if not _extract_bing_urls(body):
                break
        except Exception:
            break
    return results

async def ddg_search(query, session):
    data = urllib.parse.urlencode({"q":query,"b":"","kl":"us-en"})
    headers = {"Content-Type":"application/x-www-form-urlencoded",
               "Referer":"https://html.duckduckgo.com/"}
    try:
        body = await session.post_text(
            "https://html.duckduckgo.com/html/",
            data=data,
            headers={**session._headers(), **headers},
            retries=2)
        if not body:
            return []
        urls = [urllib.parse.unquote(m)
                for m in re.findall(r'uddg=([^&"\'<> ]+)', body)]
        return [DorkResult(query=query, url=u, source_engine="ddg")
                for u in urls]
    except Exception:
        return []


# ── file pull ─────────────────────────────────────────────────────────────

async def pull_url(url, session, size_limit_mb=5.0):
    size_limit = int(size_limit_mb * 1024 * 1024)
    try:
        r = await session.get(url)
        try:
            data = await r.read()
        finally:
            r.release()
        if len(data) > size_limit:
            return {"url":url,"error":"too large","content":"","type":"too_large"}
        return {"url":url,"content":data.decode("utf-8",errors="replace"),"type":"text"}
    except Exception as exc:
        return {"url":url,"error":str(exc),"content":"","type":"error"}


# ── engine ────────────────────────────────────────────────────────────────

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
        self.on_log = on_log or (lambda msg, lv="info": None)
        self.on_url = on_url or (lambda url: None)
        self.on_finding = on_finding or (lambda f: None)
        self._stop = False

    def stop(self):
        self._stop = True

    async def run(self) -> Target:
        cfg = self.config
        session = DorkSession(
            proxy=cfg.proxy,
            delay=cfg.delay,
            max_conn=cfg.threads,
            timeout=20,
        )
        await session.start()
        target = Target(domain=cfg.domain)

        try:
            await self._phase_dorks(target, session)
            if not cfg.no_probe and not self._stop:
                await self._phase_probe(target, session)
        finally:
            await session.close()
            self._write_report(target)

        return target

    async def _phase_dorks(self, target, session):
        cats = self.config.categories
        queries = []
        for cat, fn in DORK_CATS.items():
            if cats == ["all"] or cat in cats:
                queries.extend(fn(self.config.domain))
        queries = list(dict.fromkeys(queries))
        self.on_log(f"Generated {len(queries)} queries", "info")

        sem = asyncio.Semaphore(self.config.threads)

        async def fire(q):
            if self._stop:
                return []
            results = []
            async with sem:
                for eng in self.config.engines:
                    try:
                        if eng == "google":
                            r = await google_search(q, session, self.config.pages)
                        elif eng == "bing":
                            r = await bing_search(q, session, self.config.pages)
                        elif eng == "ddg":
                            r = await ddg_search(q, session)
                        else:
                            r = []
                        results.extend(r)
                    except Exception as exc:
                        self.on_log(f"search error [{eng}]: {exc}", "warn")
            return results

        batches = await asyncio.gather(*[fire(q) for q in queries],
                                        return_exceptions=True)
        for batch in batches:
            if isinstance(batch, list):
                for r in batch:
                    r.domain = target.domain
                    target.add_result(r)
                    self.on_url(r.url)

        self.on_log(f"Dork phase: {len(target.dork_results)} unique URLs", "ok")

    async def _phase_probe(self, target, session):
        # env pull
        env_urls = [r.url for r in target.dork_results
                    if ".env" in r.url.lower()][:10]
        for url in env_urls:
            if self._stop:
                break
            pf = await pull_url(url, session, self.config.size_limit_mb)
            if pf and pf.get("content"):
                target.add_pulled(pf)
                hits = scan_text(pf["content"], url)
                if hits:
                    f = Finding(
                        severity="critical", category="env_exposure",
                        title=f".env pulled: {len(hits)} secrets",
                        url=url,
                        evidence="\n".join(
                            f"{h.pattern_name}: {h.matched_value[:80]}"
                            for h in hits[:20]),
                        secrets=hits,
                    )
                    target.add_finding(f)
                    self.on_finding(f)

        # git check
        git_urls = [r.url for r in target.dork_results if ".git" in r.url][:5]
        for url in git_urls:
            if self._stop:
                break
            base = url.split("/.git/")[0] + "/.git" if "/.git/" in url else url.rstrip("/") + "/.git"
            for gf in ["HEAD","config","COMMIT_EDITMSG"]:
                try:
                    text = await session.get_text(base + "/" + gf, retries=1)
                    if text and len(text) > 10:
                        hits = scan_text(text, url)
                        f = Finding(
                            severity="high" if not hits else "critical",
                            category="git_exposure",
                            title=f"Exposed .git/{gf}",
                            url=url,
                            evidence=text[:1000],
                            secrets=hits,
                        )
                        target.add_finding(f)
                        self.on_finding(f)
                        break
                except Exception:
                    pass

        # secret scan all pulled
        for pf in target.pulled_files:
            content = pf.get("content","")
            if not content:
                continue
            hits = scan_text(content, pf.get("url",""))
            if hits:
                f = Finding(
                    severity="critical", category="secrets",
                    title=f"Secrets in {pf.get('url','')[:50]}",
                    url=pf.get("url",""),
                    evidence="\n".join(
                        f"{h.pattern_name}: {h.matched_value[:80]}"
                        for h in hits[:20]),
                    secrets=hits,
                )
                target.add_finding(f)
                self.on_finding(f)

        self.on_log(f"Probe phase: {len(target.findings)} findings", "ok")

    def _write_report(self, target):
        out_dir = Path(self.config.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "=" * 60,
            f"DorkMaster Report — {target.domain}",
            f"Generated: {_utcnow().isoformat()}",
            "=" * 60,
            f"URLs found:  {len(target.urls)}",
            f"Files pulled: {len(target.pulled_files)}",
            f"Findings:    {len(target.findings)}",
            "",
        ]
        for i, f in enumerate(sorted(target.findings,
                                      key=lambda x: x.severity_rank(),
                                      reverse=True), 1):
            lines += [
                f"[{i}] {f.severity.upper()} | {f.category}",
                f"    {f.title}",
                f"    {f.url}",
                "",
            ]
        lines.append("ALL URLS:")
        lines.extend(f"  {u}" for u in target.urls)
        _write_text_safe(out_dir / "report.txt", "\n".join(lines) + "\n")

        data = {
            "domain": target.domain,
            "urls": target.urls,
            "findings": [
                {"severity": f.severity, "category": f.category,
                 "title": f.title, "url": f.url,
                 "evidence": f.evidence[:500]}
                for f in sorted(target.findings,
                                key=lambda x: x.severity_rank(), reverse=True)
            ]
        }
        _write_text_safe(out_dir / "report.json",
                         json.dumps(data, indent=2, ensure_ascii=False))
        self.on_log(f"Report written to {out_dir}", "ok")


# ════════════════════════════════════════════════════════════════════════════
#  KIVY UI
# ════════════════════════════════════════════════════════════════════════════

if _KIVY:

    # ── color palette ─────────────────────────────────────────────────────
    BG      = (0.06, 0.06, 0.08, 1)
    PANEL   = (0.10, 0.10, 0.13, 1)
    ACCENT  = (0.20, 0.60, 1.00, 1)
    ACCENT2 = (0.10, 0.80, 0.50, 1)
    DANGER  = (1.00, 0.25, 0.25, 1)
    WARN    = (1.00, 0.75, 0.10, 1)
    TEXT    = (0.92, 0.92, 0.92, 1)
    DIM     = (0.50, 0.50, 0.55, 1)

    SEV_COL = {
        "critical": (1.0, 0.25, 0.25, 1),
        "high":     (1.0, 0.55, 0.10, 1),
        "medium":   (1.0, 0.80, 0.10, 1),
        "low":      (0.2, 0.80, 0.50, 1),
        "info":     (0.5, 0.50, 0.55, 1),
    }

    KV = """
#:import dp kivy.metrics.dp

<RootLayout>:
    orientation: 'vertical'
    canvas.before:
        Color:
            rgba: app.BG
        Rectangle:
            pos: self.pos
            size: self.size

<HeaderBar>:
    size_hint_y: None
    height: dp(52)
    padding: dp(12), dp(8)
    canvas.before:
        Color:
            rgba: app.PANEL
        Rectangle:
            pos: self.pos
            size: self.size
    Label:
        text: 'DorkMaster'
        font_size: dp(18)
        bold: True
        color: app.ACCENT
        size_hint_x: None
        width: dp(160)
    Widget:
    Label:
        id: status_lbl
        text: 'idle'
        font_size: dp(12)
        color: app.DIM
        size_hint_x: None
        width: dp(120)
        halign: 'right'
        text_size: self.size

<ScanScreen>:
    name: 'scan'
    ScrollView:
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: self.minimum_height
            padding: dp(14)
            spacing: dp(10)

            Label:
                text: 'Target Domain'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            TextInput:
                id: domain_input
                hint_text: 'example.com'
                font_size: dp(15)
                size_hint_y: None
                height: dp(42)
                background_color: app.PANEL
                foreground_color: app.TEXT
                cursor_color: app.ACCENT
                padding: dp(10), dp(10)
                multiline: False

            Label:
                text: 'Engines'
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
                EngineToggle:
                    id: tb_google
                    text: 'Google'
                    state: 'down'
                EngineToggle:
                    id: tb_bing
                    text: 'Bing'
                EngineToggle:
                    id: tb_ddg
                    text: 'DDG'

            Label:
                text: 'Categories'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            CatGrid:
                id: cat_grid

            Label:
                text: 'Proxy (optional)'
                color: app.DIM
                font_size: dp(12)
                size_hint_y: None
                height: dp(20)
                halign: 'left'
                text_size: self.size

            TextInput:
                id: proxy_input
                hint_text: 'socks5h://127.0.0.1:9050'
                font_size: dp(13)
                size_hint_y: None
                height: dp(38)
                background_color: app.PANEL
                foreground_color: app.TEXT
                cursor_color: app.ACCENT
                padding: dp(10), dp(8)
                multiline: False

            BoxLayout:
                size_hint_y: None
                height: dp(44)
                spacing: dp(10)

                Button:
                    id: scan_btn
                    text: 'SCAN'
                    font_size: dp(15)
                    bold: True
                    background_color: app.ACCENT
                    background_normal: ''
                    on_release: app.start_scan()

                Button:
                    id: stop_btn
                    text: 'STOP'
                    font_size: dp(15)
                    background_color: app.DANGER
                    background_normal: ''
                    disabled: True
                    on_release: app.stop_scan()

            Button:
                text: 'VIEW RESULTS'
                font_size: dp(13)
                size_hint_y: None
                height: dp(38)
                background_color: app.PANEL
                background_normal: ''
                color: app.ACCENT
                on_release: app.goto_results()

<ResultsScreen>:
    name: 'results'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(8)

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)

            Button:
                text: '< Back'
                size_hint_x: None
                width: dp(80)
                font_size: dp(13)
                background_color: app.PANEL
                background_normal: ''
                color: app.ACCENT
                on_release: app.goto_scan()

            Label:
                id: results_title
                text: 'Results'
                font_size: dp(15)
                bold: True
                color: app.TEXT

        RecycleView:
            id: findings_rv
            viewclass: 'FindingRow'
            RecycleBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                default_size: None, dp(72)
                default_size_hint: 1, None

<LogScreen>:
    name: 'log'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(10)
        spacing: dp(8)

        BoxLayout:
            size_hint_y: None
            height: dp(40)
            spacing: dp(8)

            Button:
                text: '< Back'
                size_hint_x: None
                width: dp(80)
                font_size: dp(13)
                background_color: app.PANEL
                background_normal: ''
                color: app.ACCENT
                on_release: app.goto_scan()

            Label:
                text: 'Live Log'
                font_size: dp(15)
                bold: True
                color: app.TEXT

        ScrollView:
            id: log_scroll
            Label:
                id: log_label
                text: ''
                font_size: dp(11)
                color: app.TEXT
                size_hint_y: None
                height: self.texture_size[1]
                text_size: self.width, None
                padding: dp(4), dp(4)
                valign: 'top'
                halign: 'left'

<EngineToggle@ToggleButton>:
    group: 'engines'
    allow_no_selection: False
    font_size: dp(13)
    background_normal: ''
    background_down: ''
    canvas.before:
        Color:
            rgba: app.ACCENT if self.state == 'down' else app.PANEL
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]

<FindingRow>:
    orientation: 'vertical'
    padding: dp(10), dp(6)
    spacing: dp(2)
    canvas.before:
        Color:
            rgba: app.PANEL
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]
    Label:
        id: sev_lbl
        text: root.severity_text
        font_size: dp(11)
        bold: True
        color: root.sev_color
        size_hint_y: None
        height: dp(18)
        halign: 'left'
        text_size: self.size
    Label:
        id: title_lbl
        text: root.title_text
        font_size: dp(13)
        color: app.TEXT
        size_hint_y: None
        height: dp(20)
        halign: 'left'
        text_size: self.size
    Label:
        id: url_lbl
        text: root.url_text
        font_size: dp(10)
        color: app.DIM
        size_hint_y: None
        height: dp(16)
        halign: 'left'
        text_size: self.size
"""

    # ── custom widgets ─────────────────────────────────────────────────────

    class RootLayout(BoxLayout):
        pass

    class HeaderBar(BoxLayout):
        pass

    class CatGrid(BoxLayout):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.orientation = "vertical"
            self.size_hint_y = None
            self.spacing = dp(4)
            self.bind(minimum_height=self.setter("height"))
            self._toggles = {}
            self._build()

        def _build(self):
            cats = list(DORK_CATS.keys())
            row = None
            for i, cat in enumerate(cats):
                if i % 3 == 0:
                    row = BoxLayout(size_hint_y=None, height=dp(34),
                                    spacing=dp(4))
                    self.add_widget(row)
                tb = ToggleButton(
                    text=cat,
                    font_size=dp(11),
                    group="cats",
                    allow_no_selection=False,
                    background_normal="",
                    background_down="",
                )
                tb.bind(state=lambda inst, val: None)
                self._toggles[cat] = tb
                row.add_widget(tb)
            # fill last row
            if row and len(row.children) < 3:
                for _ in range(3 - len(row.children)):
                    row.add_widget(Widget())

        def selected(self):
            return [cat for cat, tb in self._toggles.items()
                    if tb.state == "down"]

        def select_all(self):
            for tb in self._toggles.values():
                tb.state = "down"

    class FindingRow(RecycleDataViewBehavior, BoxLayout):
        severity_text = StringProperty("")
        title_text    = StringProperty("")
        url_text      = StringProperty("")
        sev_color     = ListProperty([0.9, 0.9, 0.9, 1])

        def refresh_view_attrs(self, rv, index, data):
            self.severity_text = data.get("severity_text", "")
            self.title_text    = data.get("title_text", "")
            self.url_text      = data.get("url_text", "")
            self.sev_color     = data.get("sev_color", [0.9, 0.9, 0.9, 1])
            return super().refresh_view_attrs(rv, index, data)

    class ScanScreen(Screen):
        pass

    class ResultsScreen(Screen):
        pass

    class LogScreen(Screen):
        pass

    # ── app ────────────────────────────────────────────────────────────────

    class DorkMasterApp(App):
        BG     = ListProperty(list(BG))
        PANEL  = ListProperty(list(PANEL))
        ACCENT = ListProperty(list(ACCENT))
        ACCENT2= ListProperty(list(ACCENT2))
        DANGER = ListProperty(list(DANGER))
        WARN   = ListProperty(list(WARN))
        TEXT   = ListProperty(list(TEXT))
        DIM    = ListProperty(list(DIM))

        def build(self):
            Builder.load_string(KV)
            Window.clearcolor = BG

            self.sm = ScreenManager(transition=SlideTransition())
            self.scan_screen    = ScanScreen(name="scan")
            self.results_screen = ResultsScreen(name="results")
            self.log_screen     = LogScreen(name="log")

            self.sm.add_widget(self.scan_screen)
            self.sm.add_widget(self.results_screen)
            self.sm.add_widget(self.log_screen)

            root = RootLayout()
            self._header = HeaderBar()
            root.add_widget(self._header)

            # tab bar
            tabs = BoxLayout(size_hint_y=None, height=dp(38), spacing=dp(4),
                             padding=dp(8), 0)
            for label, screen in [("Scan","scan"),("Results","results"),("Log","log")]:
                btn = Button(text=label, font_size=dp(13),
                             background_normal="", background_color=PANEL)
                btn.bind(on_release=lambda inst, s=screen: self._goto(s))
                tabs.add_widget(btn)
            root.add_widget(tabs)
            root.add_widget(self.sm)

            self._log_lines: list[str] = []
            self._findings_data: list[dict] = []
            self._engine: Optional[ScanEngine] = None
            self._loop: Optional[asyncio.AbstractEventLoop] = None
            self._thread: Optional[threading.Thread] = None

            # select all cats by default
            Clock.schedule_once(lambda dt: self.scan_screen.ids.cat_grid.select_all(), 0.1)

            return root

        def _goto(self, name):
            self.sm.current = name

        def goto_scan(self):    self.sm.current = "scan"
        def goto_results(self): self.sm.current = "results"

        def _set_status(self, msg):
            try:
                self._header.ids.status_lbl.text = msg
            except Exception:
                pass

        def _append_log(self, msg, level="info"):
            col = {"ok":"[color=33cc77]","warn":"[color=ffcc00]",
                   "err":"[color=ff4444]","info":"[color=aaaaff]"}.get(level,"[color=eeeeee]")
            line = f"{col}{msg}[/color]"
            self._log_lines.append(line)
            if len(self._log_lines) > 500:
                self._log_lines = self._log_lines[-400:]

            def _update(dt):
                try:
                    lbl = self.log_screen.ids.log_label
                    lbl.markup = True
                    lbl.text = "\n".join(self._log_lines[-200:])
                    sv = self.log_screen.ids.log_scroll
                    sv.scroll_y = 0
                except Exception:
                    pass
            Clock.schedule_once(_update, 0)

        def _add_url(self, url):
            self._append_log(f"  {url[:80]}", "info")

        def _add_finding(self, finding):
            self._findings_data.append({
                "severity_text": finding.severity.upper() + " | " + finding.category,
                "title_text":    finding.title[:60],
                "url_text":      finding.url[:70],
                "sev_color":     list(SEV_COL.get(finding.severity, TEXT)),
            })
            def _update(dt):
                try:
                    rv = self.results_screen.ids.findings_rv
                    rv.data = list(self._findings_data)
                    rv.refresh_from_data()
                except Exception:
                    pass
            Clock.schedule_once(_update, 0)

        def _set_scan_active(self, active: bool):
            def _update(dt):
                try:
                    self.scan_screen.ids.scan_btn.disabled = active
                    self.scan_screen.ids.stop_btn.disabled = not active
                except Exception:
                    pass
            Clock.schedule_once(_update, 0)

        def start_scan(self):
            try:
                domain = self.scan_screen.ids.domain_input.text.strip()
            except Exception:
                return
            if not domain:
                self._append_log("enter a domain first", "warn")
                return

            for pref in ("https://","http://"):
                if domain.startswith(pref):
                    domain = domain[len(pref):]
            domain = domain.rstrip("/")

            engines = []
            try:
                if self.scan_screen.ids.tb_google.state == "down":
                    engines.append("google")
                if self.scan_screen.ids.tb_bing.state == "down":
                    engines.append("bing")
                if self.scan_screen.ids.tb_ddg.state == "down":
                    engines.append("ddg")
            except Exception:
                engines = ["google"]
            if not engines:
                engines = ["google"]

            cats = self.scan_screen.ids.cat_grid.selected()
            if not cats:
                cats = ["all"]

            try:
                proxy = self.scan_screen.ids.proxy_input.text.strip() or None
            except Exception:
                proxy = None

            cfg = ScanConfig(
                domain=domain,
                engines=engines,
                categories=cats,
                proxy=proxy,
                delay=3.0,
                pages=2,
                threads=6,
            )

            self._findings_data = []
            try:
                self.results_screen.ids.findings_rv.data = []
                self.results_screen.ids.results_title.text = f"Results — {domain}"
            except Exception:
                pass

            self._append_log(f"Starting scan: {domain}", "ok")
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

            def _run_loop():
                loop = asyncio.new_event_loop()
                self._loop = loop
                asyncio.set_event_loop(loop)
                try:
                    target = loop.run_until_complete(self._engine.run())
                    Clock.schedule_once(lambda dt: self._scan_done(target), 0)
                except Exception as exc:
                    Clock.schedule_once(
                        lambda dt: self._append_log(f"FATAL: {exc!r}", "err"), 0)
                finally:
                    loop.close()
                    self._loop = None

            self._thread = threading.Thread(target=_run_loop, daemon=True)
            self._thread.start()

        def stop_scan(self):
            if self._engine:
                self._engine.stop()
                self._append_log("stop requested", "warn")
            self._set_status("stopping…")

        def _scan_done(self, target):
            self._set_scan_active(False)
            n = len(target.findings)
            self._set_status(f"done — {n} finding(s)")
            self._append_log(
                f"Scan complete: {len(target.urls)} URLs, {n} findings", "ok")
            if not self._findings_data:
                self._append_log("no findings — results still in report.txt", "info")
            self.sm.current = "results"


    def run_app():
        DorkMasterApp().run()


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if _KIVY:
        run_app()
    else:
        # headless engine mode — useful for testing on CI without a display
        import argparse
        ap = argparse.ArgumentParser(description="DorkMaster engine-only mode")
        ap.add_argument("domain")
        ap.add_argument("--engines", default="google")
        ap.add_argument("--proxy", default=None)
        ap.add_argument("--no-probe", action="store_true")
        args = ap.parse_args()

        cfg = ScanConfig(
            domain=args.domain,
            engines=[e.strip() for e in args.engines.split(",")],
            proxy=args.proxy,
            no_probe=args.no_probe,
        )

        def log(m, lv="info"):
            print(f"[{lv.upper()}] {m}")

        engine = ScanEngine(cfg, on_log=log,
                            on_url=lambda u: print(f"  URL: {u}"),
                            on_finding=lambda f: print(f"  FINDING [{f.severity}] {f.title}"))
        asyncio.run(engine.run())
