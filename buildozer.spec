[app]
title = DorkMaster
package.name = dorkmaster
package.domain = org.dorkmaster
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,txt
version = 4.3.0
requirements = python3,kivy==2.3.0,pyjnius,requests,urllib3,certifi,charset-normalizer,idna,attrs
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
