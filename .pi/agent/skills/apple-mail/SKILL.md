---
name: apple-mail
description: Access and read emails from Apple Mail on macOS using AppleScript. Use when the user asks to search for emails by subject/sender/keywords, read email content, find emails by date range, or check for attachments in Apple Mail.
---

# Apple Mail Skill

Access and read emails from Apple Mail on macOS using AppleScript.

## Usage

Trigger this skill when the user asks to:
- Search for emails by subject, sender, or keywords
- Read email content from Apple Mail
- Find emails by date range
- Check for attachments in emails

## Core Implementation

The skill uses AppleScript to access Mail.app. Here are the working implementations:

### Search Recent Emails (Last 7 Days)

```bash
osascript -e '
tell application "Mail"
  set results to {}
  set cutoffDate to (current date) - (7 * 86400)
  set recentMessages to (every message of inbox whose date received > cutoffDate)
  repeat with i from 1 to (count of recentMessages)
    set aMessage to item i of recentMessages
    try
      set hasAttach to (count of attachments of aMessage) > 0
    on error
      set hasAttach to false
    end try
    set end of results to {subject: subject of aMessage, sender: sender of aMessage, date: date received of aMessage, hasAttachments: hasAttach}
  end repeat
  return results
end tell
'
```

### Search by Subject/Sender

```bash
osascript -e '
tell application "Mail"
  set foundMessages to (every message of inbox whose subject contains "search term")
  repeat with aMessage in foundMessages
    log "SUBJECT: " & (subject of aMessage)
    log "SENDER: " & (sender of aMessage)
    log "DATE: " & (date received of aMessage)
  end repeat
end tell
'
```

### Read Full Email Content

```bash
osascript -e '
tell application "Mail"
  set foundMessages to (every message of inbox whose subject contains "Strava API Update")
  repeat with aMessage in foundMessages
    log "=== SUBJECT: " & (subject of aMessage)
    log "SENDER: " & (sender of aMessage)
    log "DATE: " & (date received of aMessage)
    log "CONTENT:"
    set msgContent to content of aMessage
    set previewText to (text 1 through 500) of msgContent
    log previewText
    log "..."
  end repeat
end tell
'
```

### Search All Mailboxes

```bash
osascript -e '
tell application "Mail"
  set results to {}
  repeat with a in accounts
    repeat with mb in mailboxes of a
      try
        set msgs to (messages of mb whose subject contains "search term")
        if (count of msgs) > 0 then
          set end of results to {mailbox: name of mb, count: count of msgs}
        end if
      end try
    end repeat
  end repeat
  return results
end tell
'
```

### Check for Attachments

```bash
osascript -e '
tell application "Mail"
  set foundMessages to (every message of inbox whose subject contains "term")
  repeat with aMessage in foundMessages
    try
      set attachmentCount to count of attachments of aMessage
      if attachmentCount > 0 then
        log {subject: subject of aMessage, attachments: attachmentCount}
      end if
    end try
  end repeat
end tell
'
```

## Implementation Notes

- **Read-only**: This skill only reads emails, never modifies or deletes
- **Inline display**: Email content is displayed in the chat, not saved to files
- **Attachments**: Attachment names and counts are shown; actual files are not extracted
- **Performance**: For large mailboxes, limit results with `whose` clauses
- **Accounts**: Supports multiple mail accounts if configured in Mail.app

## Example Usage

**User**: "Find emails from Strava about API"
**Skill**: Searches inbox for messages where subject contains "API" and sender contains "Strava"

**User**: "What emails did I get yesterday?"
**Skill**: Searches for messages with `date received` within yesterday's date range

**User**: "Do I have any emails with attachments from my boss?"
**Skill**: Searches inbox, checks attachment count for each matching message

## Limitations

- Requires Mail.app to be installed and accessible
- May prompt for permission on first run (System Preferences > Privacy > Automation)
- Large result sets should be paginated or limited
- HTML content is returned as-is; plain text extraction may be needed for better formatting
