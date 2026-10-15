# DorkMaster Android

Native Android project built with Kotlin, Gradle, Material Components, and WebView.

## Features
- Domain input and 20 selectable search categories
- Google, Bing, or DuckDuckGo search-link generation
- Results list with category/query filtering, open, and copy actions
- In-app browser with back, forward, reload, and address entry
- Activity log

This app generates search-engine links for manual review. It does not automatically crawl sites, fetch exposed files, or extract credentials.

## Build
The GitHub Actions workflow builds a debug APK on pushes to `main`/`master` or via **Actions → Build APK → Run workflow**. Download the `DorkMaster-APK` artifact from the completed workflow run.

The workflow installs Gradle 8.4 directly, so a `gradlew` launcher script and wrapper JAR are not required in this repository.
