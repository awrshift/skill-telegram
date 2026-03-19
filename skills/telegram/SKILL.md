---
name: telegram
description: "The only Telegram skill your AI agent needs. Read messages, parse channels, download and transcribe voice notes — all via Telethon user API. One session file, zero bots. Use when user says 'read telegram', 'check saved messages', 'fetch from telegram', 'parse channel', 'transcribe voice', 'telegram search', 'check my telegram', or when any agent needs Telegram data. Also trigger on 'what did I save in telegram', 'read my saved messages', 'get messages from channel X', 'download voice notes'. Covers: ad-hoc reading, channel parsing with sanitization, voice/audio download. Requires TG_API_ID, TG_API_HASH env vars and a session file."
---

# Telegram Skill — User API Integration

All operations via Telethon (user API, not bot API). One session file for everything.

## Setup (first run)

1. **Get API credentials** at https://my.telegram.org/apps → create app → copy `api_id` and `api_hash`
2. **Set env vars** in your `.env`:
   ```
   TG_API_ID=your_api_id
   TG_API_HASH=your_api_hash
   ```
3. **Install Telethon:** `pip install telethon`
4. **Run setup diagnostic:** `python3 scripts/tg_setup.py`
5. **Authenticate** (first time): `python3 scripts/tg_setup.py --auth` → enter phone + code from Telegram

Session file is saved automatically. All subsequent operations reuse it.

Set `TG_SESSION` env var to point to your session file, or the skill auto-discovers it.

## 1. Read Messages (any chat)

```bash
# Saved Messages
python3 scripts/tg_read.py --saved-messages --limit 10

# Specific chat/person
python3 scripts/tg_read.py --chat username --limit 20

# Public channel
python3 scripts/tg_read.py --channel SEOBAZA --limit 5

# With explicit session file
python3 scripts/tg_read.py --saved-messages --limit 5 --session /path/to/tg_session.session
```

Output: JSON lines (one per message) with: `id`, `date`, `text`, `has_voice`, `has_audio`, `has_photo`, `has_document`, `mime_type`, `file_size`, `duration`.

## 2. Parse Channels

Fetch messages from public channels with text sanitization (anti-injection, emoji cleanup, link extraction, dedup hashing).

```bash
# Single channel
python3 scripts/tg_fetch_channels.py --channel SEOBAZA --limit 20

# Multiple channels
python3 scripts/tg_fetch_channels.py --channels SEOBAZA,seo_inside,serpstat --limit 10

# Since date
python3 scripts/tg_fetch_channels.py --channel SEOBAZA --since 2026-03-01

# Save to file
python3 scripts/tg_fetch_channels.py --channel SEOBAZA --output messages.jsonl

# Pretty JSON
python3 scripts/tg_fetch_channels.py --channel SEOBAZA --pretty
```

Output: JSONL with: `channel`, `channel_id`, `id`, `date`, `text`, `text_sanitized`, `links`, `hash`, `views`, `forwards`.

Sanitization: strips zero-width chars, excessive emoji, backtick injection, truncates at 2000 chars.

## 3. Download Voice Notes

Fetch voice/audio/video_note messages and download the audio files.

```bash
# From Saved Messages
python3 scripts/tg_fetch_voice.py --saved-messages

# From specific chat
python3 scripts/tg_fetch_voice.py --chat username --limit 5

# Custom output directory
python3 scripts/tg_fetch_voice.py --saved-messages --audio-dir ./my-audio
```

Output: metadata JSONL (id, date, duration, media_type, file_path, file_size) + downloaded audio files.

**Transcription:** Use mlx-whisper or any Whisper model on the downloaded audio files. The skill handles Telegram I/O only — transcription is your choice of tool.

## 4. Setup & Diagnostics

```bash
# Full diagnostic (env, session, deps, connectivity)
python3 scripts/tg_setup.py

# Create/refresh session (interactive auth)
python3 scripts/tg_setup.py --auth
```

## Architecture

```
skills/telegram/
├── SKILL.md              ← This file
├── scripts/
│   ├── tg_read.py        ← Read any chat (104 lines)
│   ├── tg_fetch_channels.py  ← Parse channels → JSONL (165 lines)
│   ├── tg_fetch_voice.py ← Download voice/audio (219 lines)
│   ├── tg_setup.py       ← Auth + diagnostics (198 lines)
│   └── sanitizer.py      ← Text sanitization (84 lines)
└── references/
    ├── setup.md          ← Detailed setup guide
    └── json-schema.md    ← Output format spec
```

**Design principle:** Scripts produce JSON. No business logic, no classification, no transcription. Pure Telegram I/O. Pipe the output to whatever you need.

## Session Resolution

Scripts find the session file in this order:
1. `--session` CLI flag
2. `TG_SESSION` env var
3. `.claude/data/telegram/tg_session.session` (project-level)
4. `~/.telegram/tg_session.session` (global fallback)

## Limitations

- **User API only** — not a bot. You authenticate as yourself.
- **Rate limits** — FloodWaitError handled with auto-delay between channels.
- **One active session** — only one Telethon client per session at a time.
- **Media download** — large files throttled by Telegram.
- **No sending** — this skill reads only. It does not send messages.
