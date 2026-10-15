#!/usr/bin/env python3
"""
DorkMaster Mobile v4.2 — Kivy app, pure-Python HTTP (requests).
No C extensions. Builds clean on Android via Buildozer + p4a.
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
version = 4.2.0
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
import io
import json
import re
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import requests as _requests
    from requests.adapters import HTTPAdapter
    _REQUESTS = True
except ImportError:
    _REQUESTS = False

import random

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
except ImportError as e:
    _KIVY = False
    print(f"[WARN] Kivy not available: {e}")

# ═══════════════════════════════════════════════════════════
#  ENGINE
# ═══════════════════════════════════════════════════════════

def _utcnow(): return datetime.now(timezone.utc)

def _read_text_safe(path):
    p = Path(path)
    if not p.exists(): return ""
    try: return p.read_text(encoding="utf-8", errors="replace")
    except: return ""

def _write_text_safe(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", errors="replace", newline="\n") as f:
        f.write(data)

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
    rule_summary: list = field(default_factory=list)
    def add_finding(self, f): self.findings.append(f)
    def add_result(self, r):
        if r not in self.dork_results:
            self.dork_results.append(r)
            self.urls.append(r.url)
    def add_pulled(self, e): self.pulled_files.append(e)
    def note_rule(self, l): self.rule_summary.append(l)

@dataclass
class DorkResult:
    query: str; url: str; snippet: str = ""
    source_engine: str = "google"; domain: str = ""
    def __hash__(self): return hash(self.url)
    def __eq__(self, o): return isinstance(o, DorkResult) and self.url == o.url

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
]

def _make_session(proxy=None):
    s = _requests.Session()
    s.headers.update({
        "User-Agent": random.choice(_UA_POOL),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
    })
    if proxy:
        s.proxies = {"http": proxy, "https": proxy}
    s.verify = False
    return s

def _s(d): return f"site:{d}"

DORK_CATS = {
"credentials": lambda d: [
    f'{_s(d)} filetype:txt intext:"username" intext:"password"',
    f'{_s(d)} filetype:cfg intext:"password"',
    f'{_s(d)} filetype:yml intext:"password"',
    f'{_s(d)} inurl:"/.htpasswd"',
    f'{_s(d)} filetype:sh intext:"password="',
    f'intext:"username" intext:"password" intext:"{d}" filetype:txt',
],
"logs": lambda d: [
    f'{_s(d)} intitle:"index of" "access.log"',
    f'{_s(d)} filetype:log intext:"password"',
    f'{_s(d)} filetype:log intext:"bearer"',
    f'{_s(d)} intitle:"index of" "debug.log"',
],
"databases": lambda d: [
    f'{_s(d)} filetype:sql intext:"INSERT INTO" intext:"password"',
    f'{_s(d)} inurl:"/phpmyadmin/" intext:"Welcome to phpMyAdmin"',
    f'{_s(d)} filetype:sqlite inurl:".sqlite"',
    f'{_s(d)} inurl:":9200/_cat/indices"',
],
"git": lambda d: [
    f'{_s(d)} intitle:"index of" ".git"',
    f'{_s(d)} inurl:"/.git/config" intext:"url ="',
    f'{_s(d)} inurl:"/.git/HEAD" intext:"ref:"',
    f'intitle:"index of" ".git" "{d}"',
],
"env": lambda d: [
    f'{_s(d)} filetype:env intext:"DB_PASSWORD"',
    f'{_s(d)} inurl:".env" intext:"APP_KEY"',
    f'{_s(d)} filetype:env "AWS_SECRET_ACCESS_KEY"',
    f'{_s(d)} filetype:env "OPENAI_API_KEY"',
    f'{_s(d)} filetype:env "DATABASE_URL"',
],
"backups": lambda d: [
    f'{_s(d)} filetype:bak inurl:"wp-config"',
    f'{_s(d)} intitle:"index of" "backup.zip"',
    f'{_s(d)} filetype:zip inurl:"backup"',
    f'{_s(d)} inurl:".swp"',
],
"admin": lambda d: [
    f'{_s(d)} inurl:admin intitle:"login"',
    f'{_s(d)} inurl:/wp-admin/ intitle:"WordPress"',
    f'{_s(d)} inurl:grafana intitle:"Grafana"',
    f'{_s(d)} intitle:"RabbitMQ Management"',
],
"cloud": lambda d: [
    f'site:s3.amazonaws.com inurl:{d}',
    f'site:storage.googleapis.com inurl:{d}',
    f'filetype:json intext:"aws_access_key_id"',
],
"s3": lambda d: [
    f'site:s3.amazonaws.com "{d.replace(".","-")}"',
    f'site:s3.amazonaws.com "{d.replace(".","-")}-backup"',
    f'site:storage.googleapis.com "{d.replace(".","-")}"',
],
"apikeys": lambda d: [
    f'{_s(d)} filetype:js intext:"api_key"',
    f'{_s(d)} filetype:js intext:"AIza"',
    f'{_s(d)} inurl:"config.js"',
    f'{_s(d)} inurl:"service-account.json"',
],
"pastebin": lambda d: [
    f'site:pastebin.com "{d}" password',
    f'site:pastebin.com "{d}" token',
],
"github": lambda d: [
    f'site:github.com "{d}" password',
    f'site:github.com "{d}" .env',
    f'site:gist.github.com "{d}"',
],
"emails": lambda d: [
    f'{_s(d)} intext:"@{d}" filetype:csv',
    f'site:linkedin.com/in "{d}"',
],
"errors": lambda d: [
    f'{_s(d)} intext:"Fatal error"',
    f'{_s(d)} intext:"Traceback (most recent call last)"',
    f'{_s(d)} inurl:"/actuator/env"',
    f'{_s(d)} intitle:"Werkzeug" intext:"Traceback"',
],
"cms": lambda d: [
    f'{_s(d)} inurl:wp-config.php.bak',
    f'{_s(d)} inurl:"/wp-json/wp/v2/users"',
    f'{_s(d)} inurl:xmlrpc.php',
],
"network": lambda d: [
    f'{_s(d)} intitle:"webcamXP" inurl:8080',
    f'{_s(d)} intitle:"Hikvision" inurl:login',
],
"jira": lambda d: [
    f'{_s(d)} inurl:/jira/ intext:"issue"',
    f'site:*.atlassian.net "{d}"',
],
"xmlrpc": lambda d: [
    f'{_s(d)} inurl:"xmlrpc.php"',
    f'{_s(d)} inurl:"/swagger-ui.html"',
],
"stealer": lambda d: [
    f'{_s(d)} intitle:"index of" "combolist"',
    f'intext:"{d}" intext:"password" filetype:txt -site:{d}',
],
}

ALL_CATS = list(DORK_CATS.keys())

_SECRET_PATTERNS = [
    ("AWS_ACCESS_KEY",      re.compile(r'AKIA[0-9A-Z]{16}')),
    ("GCP_API_KEY",         re.compile(r'AIza[0-9A-Za-z\-_]{35}')),
    ("GITHUB_TOKEN",        re.compile(r'ghp_[a-zA-Z0-9]{36}')),
    ("GITHUB_TOKEN_V2",     re.compile(r'github_pat_[a-zA-Z0-9_]{82}')),
    ("STRIPE_SECRET",       re.compile(r'sk_live_[a-zA-Z0-9]{24,}')),
    ("OPENAI_KEY",          re.compile(r'sk-[a-zA-Z0-9]{20}T3BlbkFJ[a-zA-Z0-9]{20}')),
    ("OPENAI_KEY_V2",       re.compile(r'sk-proj-[a-zA-Z0-9_\-]{40,}')),
    ("ANTHROPIC_KEY",       re.compile(r'sk-ant-[a-zA-Z0-9_\-]{40,}')),
    ("SLACK_TOKEN",         re.compile(r'xox[baprs]-[0-9]{10,}-[0-9]{10,}-[a-zA-Z0-9]+')),
    ("PRIVATE_KEY_RSA",     re.compile(r'-----BEGIN RSA PRIVATE KEY-----')),
    ("PRIVATE_KEY_OPENSSH", re.compile(r'-----BEGIN OPENSSH PRIVATE KEY-----')),
    ("DB_PASSWORD",         re.compile(r'DB_PASS(?:WORD)?\s*[=:]\s*\S+')),
    ("DATABASE_URL",        re.compile(r'(?:mysql|postgres|mongodb|redis)://[^\s"\']+')),
    ("JWT",                 re.compile(r'eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+')),
    ("SENDGRID_KEY",        re.compile(r'SG\.[a-zA-Z0-9\-_]{22}\.[a-zA-Z0-9\-_]{43}')),
    ("DISCORD_WEBHOOK",     re.compile(r'https://discord\.com/api/webhooks/\d+/[a-zA-Z0-9_\-]+')),
    ("SECRET_KEY_GENERIC",  re.compile(r'(?i)(?:secret[_\-]?key|api[_\-]?key)\s*[=:]\s*["\']?([a-zA-Z0-9\-_]{16,})')),
]

def scan_text(text, source_url=""):
    hits = []
    lines = text.splitlines()
    seen = set()
    for name, pat in _SECRET_PATTERNS:
        for line in lines:
            for m in pat.finditer(line):
                val = m.group(0)[:120]
                key = (name, val)
                if key in seen: continue
                seen.add(key)
                hits.append(SecretHit(name, val, line.strip()[:200], source_url))
    return hits

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
            if not body or _is_captcha(body):
                time.sleep(3)
                continue
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
            body = r.text
            urls = _extract_bing_urls(body)
            for u in urls:
                results.append(DorkResult(query=query, url=u, source_engine="bing"))
            if not urls: break
        except Exception: break
    return results

def _ddg_search(query, session):
    try:
        data = urllib.parse.urlencode({"q": query, "b": "", "kl": "us-en"})
        r = session.post(
            "https://html.duckduckgo.com/html/",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded",
                     "Referer": "https://html.duckduckgo.com/"},
            timeout=15)
        body = r.text
        if not body: return []
        urls = [urllib.parse.unquote(m)
                for m in re.findall(r'uddg=([^&"\'<> ]+)', body)]
        return [DorkResult(query=query, url=u, source_engine="ddg") for u in urls]
    except Exception:
        return []

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
    def __init__(self, config, on_log=None, on_url=None, on_finding=None):
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
            results = []
            time.sleep(self.config.delay + random.uniform(-0.5, 0.5))
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

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.threads) as ex:
            futures = {ex.submit(fire, q): q for q in queries}
            for fut in concurrent.futures.as_completed(futures):
                if self._stop: break
                try:
                    for r in (fut.result() or []):
                        r.domain = target.domain
                        target.add_result(r)
                        self.on_url(r.url)
                except Exception: pass

        self.on_log(f"Dork phase: {len(target.dork_results)} unique URLs", "ok")

    def _phase_probe(self, target, session):
        # .env pull
        for url in [r.url for r in target.dork_results if ".env" in r.url.lower()][:10]:
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
                    evidence="\n".join(f"{h.pattern_name}: {h.matched_value[:80]}" for h in hits[:20]),
                    secrets=hits)
                target.add_finding(f)
                self.on_finding(f)

        # .git check
        for url in [r.url for r in target.dork_results if ".git" in r.url][:5]:
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
                            title=f"Exposed .git/{gf}" + (f" — {len(hits)} secrets" if hits else ""),
                            url=url,
                            evidence=r.text[:1000],
                            secrets=hits)
                        target.add_finding(f)
                        self.on_finding(f)
                        break
                except Exception: pass

        # secret scan all pulled
        for pf in target.pulled_files:
            content = pf.get("content", "")
            if not content: continue
            hits = scan_text(content, pf.get("url", ""))
            if hits:
                f = Finding(
                    severity="critical", category="secrets",
                    title=f"Secrets in pulled file — {len(hits)} hits",
                    url=pf.get("url", ""),
                    evidence="\n".join(
                        f"{h.pattern_name}: {h.matched_value[:80]}" for h in hits[:20]),
                    secrets=hits)
                target.add_finding(f)
                self.on_finding(f)

        self.on_log(f"Probe phase: {len(target.findings)} findings", "ok")

    def _write_report(self, target):
        out = Path(self.config.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        lines = [
            "=" * 60,
            f"DorkMaster Report — {target.domain}",
            f"Generated: {_utcnow().isoformat()}",
            "=" * 60,
            f"URLs: {len(target.urls)}  Findings: {len(target.findings)}",
            "",
        ]
        for i, f in enumerate(sorted(target.findings,
                key=lambda x: x.severity_rank(), reverse=True), 1):
            lines += [f"[{i}] {f.severity.upper()} | {f.category}", f"    {f.title}", f"    {f.url}", ""]
        lines.append("ALL URLS:")
        lines.extend(f"  {u}" for u in target.urls)
        _write_text_safe(out / "report.txt", "\n".join(lines) + "\n")
        data = {
            "domain": target.domain, "urls": target.urls,
            "findings": [{"severity": f.severity, "category": f.category,
                "title": f.title, "url": f.url, "evidence": f.evidence[:500]}
                for f in sorted(target.findings,
                    key=lambda x: x.severity_rank(), reverse=True)]
        }
        _write_text_safe(out / "report.json", json.dumps(data, indent=2, ensure_ascii=False))
        self.on_log(f"Report saved → {out}", "ok")


# ═══════════════════════════════════════════════════════════
#  KIVY UI
# ═══════════════════════════════════════════════════════════

if _KIVY:
    BG=(0.06,0.06,0.08,1); PANEL=(0.10,0.10,0.13,1)
    ACCENT=(0.20,0.60,1.00,1); DANGER=(1.00,0.25,0.25,1)
    TEXT=(0.92,0.92,0.92,1); DIM=(0.50,0.50,0.55,1)
    SEV_COL={"critical":[1.0,0.25,0.25,1],"high":[1.0,0.55,0.10,1],
             "medium":[1.0,0.80,0.10,1],"low":[0.2,0.80,0.50,1],"info":[0.5,0.50,0.55,1]}

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
<AccentButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: app.ACCENT
    color: 1,1,1,1
    font_size: dp(14)
    bold: True
<DangerButton@Button>:
    background_normal: ''
    background_down: ''
    background_color: app.DANGER
    color: 1,1,1,1
    font_size: dp(14)
<FindingRow>:
    orientation: 'vertical'
    padding: dp(10), dp(6)
    spacing: dp(2)
    size_hint_y: None
    height: dp(78)
    canvas.before:
        Color:
            rgba: 0.12, 0.12, 0.15, 1
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
                text: '[b][color=33aaff]DorkMaster[/color] v4.2[/b]'
                markup: True
                font_size: dp(20)
                size_hint_y: None
                height: dp(36)
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
                text: 'Engines'
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
            DarkInput:
                id: proxy_input
                hint_text: 'socks5h://127.0.0.1:9050'
                size_hint_y: None
                height: dp(40)
            BoxLayout:
                size_hint_y: None
                height: dp(44)
                spacing: dp(10)
                AccentButton:
                    id: scan_btn
                    text: 'SCAN'
                    on_release: app.start_scan()
                DangerButton:
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
        spacing: dp(8)
        Label:
            id: results_title
            text: 'Results'
            font_size: dp(16)
            bold: True
            color: app.TEXT
            size_hint_y: None
            height: dp(32)
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
        RecycleView:
            id: findings_rv
            viewclass: 'FindingRow'
            RecycleBoxLayout:
                orientation: 'vertical'
                size_hint_y: None
                height: self.minimum_height
                default_size: None, dp(78)
                default_size_hint: 1, None
                spacing: dp(6)
                padding: dp(4)
        Label:
            id: no_findings_lbl
            text: ''
            font_size: dp(13)
            color: app.DIM
            size_hint_y: None
            height: dp(40)
            halign: 'center'
            text_size: self.size
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
        spacing: dp(8)
        Label:
            text: 'Live Log'
            font_size: dp(16)
            bold: True
            color: app.TEXT
            size_hint_y: None
            height: dp(32)
            halign: 'left'
            text_size: self.size
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
    font_size: dp(12)
    canvas.before:
        Color:
            rgba: app.ACCENT if self.active else app.PANEL
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [dp(6)]
"""

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

    class FindingRow(RecycleDataViewBehavior, BoxLayout):
        sev_text   = StringProperty("")
        title_text = StringProperty("")
        url_text   = StringProperty("")
        sev_color  = ListProperty([0.9,0.9,0.9,1])
        def refresh_view_attrs(self, rv, index, data):
            self.sev_text   = data.get("sev_text","")
            self.title_text = data.get("title_text","")
            self.url_text   = data.get("url_text","")
            self.sev_color  = data.get("sev_color",[0.9,0.9,0.9,1])
            return super().refresh_view_attrs(rv, index, data)

    class ScanScreen(Screen): pass
    class ResultsScreen(Screen): pass
    class LogScreen(Screen): pass

    class DorkMasterApp(App):
        BG=ListProperty(list(BG)); PANEL=ListProperty(list(PANEL))
        ACCENT=ListProperty(list(ACCENT)); DANGER=ListProperty(list(DANGER))
        TEXT=ListProperty(list(TEXT)); DIM=ListProperty(list(DIM))

        def build(self):
            Builder.load_string(KV)
            Window.clearcolor = BG
            self.sm = ScreenManager(transition=SlideTransition())
            self.sm.add_widget(ScanScreen(name="scan"))
            self.sm.add_widget(ResultsScreen(name="results"))
            self.sm.add_widget(LogScreen(name="log"))
            root = BoxLayout(orientation="vertical")
            tabs = BoxLayout(size_hint_y=None, height=dp(40),
                             spacing=dp(4), padding=[dp(8), dp(4)])
            for label, screen in [("Scan","scan"),("Results","results"),("Log","log")]:
                btn = Button(text=label, font_size=dp(13),
                             background_normal="", background_color=PANEL,
                             color=list(ACCENT))
                btn.bind(on_release=lambda inst, s=screen:
                         setattr(self.sm, "current", s))
                tabs.add_widget(btn)
            root.add_widget(tabs)
            root.add_widget(self.sm)
            self._log_lines = []
            self._findings_data = []
            self._engine = None
            self._thread = None
            return root

        def _append_log(self, msg, level="info"):
            col = {"ok":"33cc77","warn":"ffcc00","err":"ff4444","info":"aabbff"}.get(level,"eeeeee")
            ts = datetime.now().strftime("%H:%M:%S")
            self._log_lines.append(f"[color={col}][{ts}] {msg}[/color]")
            if len(self._log_lines) > 600: self._log_lines = self._log_lines[-500:]
            def _upd(dt):
                try:
                    lbl = self.sm.get_screen("log").ids.log_label
                    lbl.text = "\n".join(self._log_lines[-250:])
                    self.sm.get_screen("log").ids.log_scroll.scroll_y = 0
                except: pass
            Clock.schedule_once(_upd, 0)

        def _add_finding(self, finding):
            self._findings_data.append({
                "sev_text":   finding.severity.upper() + "  •  " + finding.category,
                "title_text": finding.title[:65],
                "url_text":   finding.url[:80],
                "sev_color":  SEV_COL.get(finding.severity, [0.9,0.9,0.9,1]),
            })
            def _upd(dt):
                try:
                    rs = self.sm.get_screen("results")
                    rs.ids.findings_rv.data = list(self._findings_data)
                    rs.ids.findings_rv.refresh_from_data()
                    rs.ids.results_stats.text = f"{len(self._findings_data)} finding(s)"
                    rs.ids.no_findings_lbl.text = ""
                except: pass
            Clock.schedule_once(_upd, 0)

        def _set_scan_active(self, active):
            def _upd(dt):
                try:
                    ss = self.sm.get_screen("scan")
                    ss.ids.scan_btn.disabled = active
                    ss.ids.stop_btn.disabled = not active
                except: pass
            Clock.schedule_once(_upd, 0)

        def _set_status(self, msg):
            def _upd(dt):
                try: self.sm.get_screen("scan").ids.status_lbl.text = msg
                except: pass
            Clock.schedule_once(_upd, 0)

        def start_scan(self):
            try: ss = self.sm.get_screen("scan"); domain = ss.ids.domain_input.text.strip()
            except: return
            if not domain: self._append_log("enter a domain first","warn"); return
            for pref in ("https://","http://"):
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

            cfg = ScanConfig(domain=domain, engines=engines,
                             categories=cats, proxy=proxy)
            self._findings_data = []
            def _reset(dt):
                try:
                    rs = self.sm.get_screen("results")
                    rs.ids.findings_rv.data = []
                    rs.ids.findings_rv.refresh_from_data()
                    rs.ids.results_title.text = f"Results — {domain}"
                    rs.ids.results_stats.text = ""
                    rs.ids.no_findings_lbl.text = "scanning…"
                except: pass
            Clock.schedule_once(_reset, 0)

            self._append_log(f"Starting: {domain}  engines={engines}", "ok")
            self._set_status("scanning…")
            self._set_scan_active(True)

            self._engine = ScanEngine(
                cfg,
                on_log=lambda m, lv="info": Clock.schedule_once(
                    lambda dt: self._append_log(m, lv), 0),
                on_url=lambda u: Clock.schedule_once(
                    lambda dt: self._append_log(f"  {u[:90]}", "info"), 0),
                on_finding=lambda f: self._add_finding(f),
            )

            def _thread_fn():
                try:
                    target = self._engine.run()
                    Clock.schedule_once(lambda dt: self._scan_done(target), 0)
                except Exception as exc:
                    Clock.schedule_once(
                        lambda dt: self._append_log(f"FATAL: {exc!r}", "err"), 0)
                    Clock.schedule_once(lambda dt: self._set_scan_active(False), 0)

            self._thread = threading.Thread(target=_thread_fn, daemon=True)
            self._thread.start()

        def stop_scan(self):
            if self._engine: self._engine.stop()
            self._append_log("stop requested", "warn")
            self._set_status("stopping…")

        def _scan_done(self, target):
            self._set_scan_active(False)
            n = len(target.findings); u = len(target.urls)
            self._set_status(f"done — {u} URLs  {n} finding(s)")
            self._append_log(f"Complete: {u} URLs, {n} findings", "ok")
            def _upd(dt):
                try:
                    rs = self.sm.get_screen("results")
                    rs.ids.results_stats.text = f"{u} URLs  •  {n} findings"
                    rs.ids.no_findings_lbl.text = ("" if n else
                        "No findings — check Log tab for URLs")
                except: pass
            Clock.schedule_once(_upd, 0)
            self.sm.current = "results"

    def run_app(): DorkMasterApp().run()


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    if _KIVY:
        run_app()
    else:
        import argparse
        ap = argparse.ArgumentParser(description="DorkMaster engine-only")
        ap.add_argument("domain")
        ap.add_argument("--engines", default="google")
        ap.add_argument("--proxy", default=None)
        ap.add_argument("--no-probe", action="store_true")
        args = ap.parse_args()
        cfg = ScanConfig(
            domain=args.domain,
            engines=[e.strip() for e in args.engines.split(",")],
            proxy=args.proxy, no_probe=args.no_probe)
        def _log(m, lv="info"): print(f"[{lv.upper()}] {m}")
        engine = ScanEngine(cfg, on_log=_log,
            on_url=lambda u: print(f"  URL  {u}"),
            on_finding=lambda f: print(f"  [{f.severity.upper()}] {f.title}"))
        engine.run()
