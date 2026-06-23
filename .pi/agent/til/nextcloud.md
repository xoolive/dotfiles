# TIL: Nextcloud menu bar icon disappears silently on macOS

**Date:** 2026-05-13

## Problem

The Nextcloud desktop client runs for a while, then its icon disappears from the
menu bar without any crash dialog or notification. Restarting it manually brings
it back, but it vanishes again later.

## Root Cause: macOS Automatic Termination (TAL)

This is **not a crash** — macOS silently kills Nextcloud via the Automatic
Termination (TAL) mechanism when it needs resources.

Evidence in the system log (`log show --predicate 'process == "Nextcloud"'`):

```
[com.apple.AppKit:AutomaticTermination] Setting _kLSApplicationWouldBeTerminatedByTALKey=1
```

This happens because:

1. Nextcloud is a menu-bar-only app (`LSUIElement = 1`) with no visible windows.
2. macOS treats background apps with no windows as eligible for automatic termination.
3. Nextcloud does not declare `NSSupportsAutomaticTermination = NO` in its `Info.plist`
   and has no `background-networking` entitlement to protect it.

Secondary symptom — every launch also logs a missing XPC service:

```
failed lookup: name = com.nextcloud.desktopclient-spks, error = 3: No such process
```

This is the Sparkle updater helper not being found, which may prevent the app from
fully registering its background activity.

## Fix: launchd watchdog

Create `~/Library/LaunchAgents/com.nextcloud.watchdog.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nextcloud.watchdog</string>

    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Nextcloud.app/Contents/MacOS/Nextcloud</string>
    </array>

    <!-- Start at login -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Only restart on non-zero exit (crash or TAL kill).
         SuccessfulExit=false means: do NOT restart on clean exit (code 0),
         so manually quitting Nextcloud from its menu works as expected. -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <!-- 10s cooldown to avoid tight restart loops on repeated crashes -->
    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>/tmp/nextcloud-watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/nextcloud-watchdog-error.log</string>
</dict>
</plist>
```

Load it immediately (no reboot needed) — but first kill the existing Nextcloud
process so launchd owns it going forward:

```bash
kill $(pgrep -x Nextcloud)
launchctl load ~/Library/LaunchAgents/com.nextcloud.watchdog.plist

# Verify it's running under launchd
launchctl list | grep nextcloud
```

## Why `KeepAlive: true` (the naive approach) breaks things

Using `KeepAlive = true` unconditionally causes launchd to respawn Nextcloud
immediately after every exit — including when it's already running. This results
in a second instance launching on top of the first, which pops the status bar
dropdown open every few seconds and makes the app unusable.

The fix is `KeepAlive -> SuccessfulExit = false`, which only restarts on
non-clean exits (signals, TAL kills) and leaves intentional quits alone.

## Restart behaviour summary

| Situation | Exit code | launchd restarts? |
|---|---|---|
| macOS kills via TAL | signal `-9` (non-zero) | ✅ Yes |
| Nextcloud crashes | non-zero | ✅ Yes |
| User quits from menu | `0` (clean) | ❌ No |

## Useful commands

```bash
# Check if watchdog is running and get Nextcloud's PID
launchctl list | grep nextcloud

# Tail watchdog logs
tail -f /tmp/nextcloud-watchdog.log /tmp/nextcloud-watchdog-error.log

# Unload watchdog (disables auto-restart)
launchctl unload ~/Library/LaunchAgents/com.nextcloud.watchdog.plist

# Reload after editing the plist
launchctl unload ~/Library/LaunchAgents/com.nextcloud.watchdog.plist
launchctl load   ~/Library/LaunchAgents/com.nextcloud.watchdog.plist
```
