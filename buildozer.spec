[app]
title = MTProto Checker
package.name = mtchecker
package.domain = org.test
source.dir = .
source.include_exts = py
version = 0.1
requirements = python3,kivy,telethon,cryptography==42.0.8,openssl
orientation = portrait
android.ant_path = /usr/share/ant
android.permissions = INTERNET
android.api = 33
android.minapi = 21
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = True
