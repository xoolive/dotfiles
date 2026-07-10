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

## Fix: launchd wrapper watchdog

Older workaround: run Nextcloud directly from launchd with
`KeepAlive -> SuccessfulExit = false`. That only restarts non-zero exits. After
Nextcloud 33.0.7, the app can disappear while launchd records `last exit code =
0`; FinderSync then keeps logging `Connection refused` because the main client
socket is gone. In that case launchd thinks this was a clean/manual quit and does
not restart it.

More robust fix: launchd keeps a small watchdog loop alive; the loop launches
Nextcloud whenever the main `Nextcloud` process is missing. This handles crashes,
TAL kills, and surprising clean exits, while avoiding the repeated menu-bar
reactivation caused by running Nextcloud itself with unconditional `KeepAlive`.

Create `~/.local/bin/nextcloud-watchdog.zsh`:

```zsh
#!/bin/zsh
set -u

APP="/Applications/Nextcloud.app"
DISABLE_FILE="$HOME/.nextcloud-watchdog-disabled"
LOG="/tmp/nextcloud-watchdog.log"
INTERVAL="${NEXTCLOUD_WATCHDOG_INTERVAL:-60}"

log() {
  print -r -- "[$(/bin/date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"
}

log "watchdog started (interval=${INTERVAL}s)"

while true; do
  if [[ -e "$DISABLE_FILE" ]]; then
    log "disabled by $DISABLE_FILE"
    sleep "$INTERVAL"
    continue
  fi

  if [[ ! -d "$APP" ]]; then
    log "app not found: $APP"
    sleep "$INTERVAL"
    continue
  fi

  if ! /usr/bin/pgrep -x Nextcloud >/dev/null 2>&1; then
    log "Nextcloud not running; launching"
    /usr/bin/open -g -j -a "$APP" >> "$LOG" 2>&1 || log "open failed with status $?"
    sleep 10
  fi

  sleep "$INTERVAL"
done
```

```bash
chmod +x ~/.local/bin/nextcloud-watchdog.zsh
```

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
        <string>/Users/xo/.local/bin/nextcloud-watchdog.zsh</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <!-- Keep the watchdog loop alive. The watchdog, not launchd, decides when
         to launch Nextcloud. -->
    <key>KeepAlive</key>
    <true/>

    <key>ThrottleInterval</key>
    <integer>10</integer>

    <key>StandardOutPath</key>
    <string>/tmp/nextcloud-watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/nextcloud-watchdog-error.log</string>
</dict>
</plist>
```

Load it:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nextcloud.watchdog.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nextcloud.watchdog.plist
```

To intentionally keep Nextcloud stopped:

```bash
touch ~/.nextcloud-watchdog-disabled
pkill -x Nextcloud
```

Re-enable it:

```bash
rm ~/.nextcloud-watchdog-disabled
```

## Why direct `KeepAlive` on Nextcloud breaks

Bad direct plist shape:

```xml
<key>ProgramArguments</key>
<array>
    <string>/Applications/Nextcloud.app/Contents/MacOS/Nextcloud</string>
</array>
<key>KeepAlive</key>
<true/>
```

This can repeatedly respawn/reactivate the menu-bar app and make the status-bar
dropdown open every few seconds.

The less-bad direct form was:

```xml
<key>KeepAlive</key>
<dict>
    <key>SuccessfulExit</key>
    <false/>
</dict>
```

But this misses the newer failure mode where Nextcloud disappears with exit code
`0`. The wrapper watchdog is now preferred.

## Useful commands

```bash
# Check if watchdog and Nextcloud are running
launchctl list | grep nextcloud
pgrep -afil 'nextcloud-watchdog|/Applications/Nextcloud.app/Contents/MacOS/Nextcloud'

# Inspect launchd job
launchctl print gui/$(id -u)/com.nextcloud.watchdog | grep -E 'state =|program =|runs =|last exit code|properties ='

# Tail watchdog logs
tail -f /tmp/nextcloud-watchdog.log /tmp/nextcloud-watchdog-error.log

# Temporarily keep Nextcloud stopped without unloading the watchdog
touch ~/.nextcloud-watchdog-disabled
pkill -x Nextcloud

# Re-enable automatic launch
rm ~/.nextcloud-watchdog-disabled

# Unload watchdog completely
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nextcloud.watchdog.plist

# Reload after editing the plist
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.nextcloud.watchdog.plist 2>/dev/null || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nextcloud.watchdog.plist
```
