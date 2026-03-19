# Telegram Skill — Setup Guide

## 1. Get API Credentials

1. Go to https://my.telegram.org/apps
2. Log in with your phone number
3. Create an application (any name)
4. Copy `api_id` and `api_hash`

## 2. Configure Environment

Add to `.env` in project root:
```
TG_API_ID=12345678
TG_API_HASH=0123456789abcdef0123456789abcdef
```

## 3. Install Dependencies

```bash
# Required
pip install telethon

# For voice transcription (Apple Silicon)
pip install mlx-whisper

# For voice transcription (CPU fallback)
pip install openai-whisper

# For pipeline configs
pip install pyyaml

# For video_note audio extraction
brew install ffmpeg
```

## 4. Create Session File

```bash
cd /path/to/project/.claude
set -a && source /path/to/project/.env && set +a
python3 skills/telegram/scripts/tg_setup.py --auth
```

This prompts for phone number + SMS code. Session saved to `.claude/data/market_signals/tg_session.session`.

**Security:** Session file = your Telegram identity. Never commit to git. Never share.

## 5. Verify Setup

```bash
python3 skills/telegram/scripts/tg_setup.py
```

Should show all checks passing.

## Porting to Another Agent

Copy these to the target project:
```
.claude/skills/telegram/           # Skill + scripts
.claude/data/market_signals/tg_session.session  # Session (symlink OK)
.env                               # With TG_API_ID, TG_API_HASH
```

Install deps: `pip install telethon mlx-whisper pyyaml`

For full pipeline features (classification, auto-triage, FTS search), also copy:
```
.claude/src/pipelines/market_signals/       # Channel intelligence pipeline
.claude/src/pipelines/voice_notes/ # Voice notes pipeline
.claude/src/__init__.py
```
