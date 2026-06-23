# TIL: hostname

**Date:** 2026-06-13

## Background / context

My Mac was showing its computer name as `alcyon1` instead of `alcyon`. I found old shell history that fixed it by resetting several macOS naming layers back to `alcyon` and flushing caches.

This likely happened because macOS/Bonjour detected a local network naming conflict or stale discovery state and automatically adjusted the advertised name to avoid a duplicate.

## What it is

`hostname` is the system/network name of a computer. On macOS there are multiple related names, and different services use different ones:

- `HostName`: Unix/network hostname, used by Terminal, SSH, logs, and networking tools.
- `LocalHostName`: Bonjour/mDNS name, used for `.local` discovery such as `alcyon.local`.
- `ComputerName`: human-friendly Mac name shown in System Settings, AirDrop, Finder sidebar, and sharing UIs.
- `NetBIOSName`: SMB/Windows file-sharing name.

These can drift or be auto-renamed independently, so seeing `alcyon1` in one place does not necessarily mean every naming layer changed.

## Key finding or fix

To force a Mac back to a consistent name, set all relevant macOS names explicitly:

- set `HostName`
- set `LocalHostName`
- set `ComputerName`
- set SMB `NetBIOSName`
- flush caches afterward

If the name keeps reverting or getting a suffix like `1`, another device or stale router/Bonjour/DHCP entry may still be claiming the same name on the network.

## Commands / examples

Fix used:

```bash
sudo scutil --set HostName alcyon
sudo scutil --set LocalHostName alcyon
sudo scutil --set ComputerName alcyon
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName -string alcyon
sudo dscacheutil -flushcache
```

Check current macOS names:

```bash
scutil --get HostName
scutil --get LocalHostName
scutil --get ComputerName
hostname
```

Check SMB/NetBIOS name:

```bash
defaults read /Library/Preferences/SystemConfiguration/com.apple.smb.server NetBIOSName
```

Useful meanings:

```bash
sudo scutil --set HostName alcyon       # Unix/network hostname
sudo scutil --set LocalHostName alcyon  # Bonjour name: alcyon.local
sudo scutil --set ComputerName alcyon   # Human-facing Mac name
```
