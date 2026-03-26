# Telegram Interchange JSON Schema

Standard JSON format exchanged between Telegram skill scripts and pipeline ingest modules.

## Channel Messages (tg_fetch_channels.py → market_signals/ingest.py)

One JSON object per line (JSONL). Fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `channel` | string | yes | Channel username (e.g., "SEOBAZA") |
| `channel_id` | string | yes | Telegram channel numeric ID |
| `id` | integer | yes | Message ID within channel |
| `date` | string | yes | ISO 8601 datetime |
| `text` | string | no | Raw message text |
| `text_sanitized` | string | no | Sanitized text (control chars stripped, emoji reduced, backticks escaped) |
| `links` | array[string] | no | Extracted URLs |
| `hash` | string | no | SHA256 content hash (first 16 chars) for dedup |
| `reply_to` | integer | no | Parent message ID if reply |
| `views` | integer | no | View count |
| `forwards` | integer | no | Forward count |

Example:
```json
{"channel": "SEOBAZA", "channel_id": "1234567", "id": 456, "date": "2026-03-06T12:00:00+00:00", "text": "Google update...", "text_sanitized": "Google update...", "links": ["https://example.com"], "hash": "abc123def456", "reply_to": null, "views": 1200, "forwards": 5}
```

## Voice Messages (tg_fetch_voice.py → voice_notes/ingest.py)

One JSON object per line (JSONL). Fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | integer | yes | Message ID |
| `chat_id` | string | yes | Chat numeric ID |
| `chat_name` | string | yes | Chat identifier ("saved_messages" or username) |
| `date` | string | yes | ISO 8601 datetime |
| `duration` | integer | no | Audio duration in seconds |
| `media_type` | string | no | "voice", "audio", or "video_note" |
| `file_path` | string | yes | Absolute path to downloaded audio file (.ogg) |
| `file_size` | integer | no | File size in bytes |

Example:
```json
{"id": 789, "chat_id": "123456", "chat_name": "saved_messages", "date": "2026-03-06T12:00:00+00:00", "duration": 653, "media_type": "voice", "file_path": "/Users/sk/Desktop/seo-geo-expert/.claude/data/voice_notes/audio/20260306-120000-789.ogg", "file_size": 123456}
```

## Notes

- Both formats use JSONL (newline-delimited JSON), not JSON arrays.
- All dates are ISO 8601 format.
- Audio files are always .ogg (Opus codec). video_note audio is extracted via ffmpeg.
- The `text_sanitized` field uses the canonical sanitizer from `src/pipelines/market_signals/sanitizer.py`.
- Content hash uses SHA256 of normalized (lowered, whitespace-collapsed) text, truncated to 16 hex chars.
