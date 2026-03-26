#!/usr/bin/env python3
"""Fetch and download voice/audio/video_note/video messages from Telegram.

Pure Telegram data layer — downloads audio files and outputs metadata JSON.
No transcription, no DB writes. Transcription is handled by voice_notes pipeline.

Usage:
  python3 tg_fetch_voice.py --saved-messages                    # From Saved Messages
  python3 tg_fetch_voice.py --chat username                     # From specific chat
  python3 tg_fetch_voice.py --saved-messages --limit 5          # Last 5 voice messages
  python3 tg_fetch_voice.py --saved-messages --output meta.jsonl # Save metadata to file
  python3 tg_fetch_voice.py --saved-messages --audio-dir /path  # Custom audio directory

Requires: telethon, ffmpeg (for video_note)
Env: TG_API_ID, TG_API_HASH
Session: reuses shared session file at .claude/data/telegram/tg_session.session

Output JSON schema: see references/json-schema.md
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Session file resolution order:
# 1. --session CLI flag  2. TG_SESSION env  3. project .claude/data/telegram/  4. ~/.telegram/
SCRIPT_DIR = Path(__file__).resolve().parent

def resolve_session(cli_session=None):
    if cli_session:
        return cli_session
    if os.getenv('TG_SESSION'):
        return os.getenv('TG_SESSION')
    # Walk up to find project root (look for .claude dir)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / '.claude' / 'data' / 'telegram' / 'tg_session.session'
        if candidate.exists():
            return str(candidate)
    home_session = os.path.expanduser('~/.telegram/tg_session.session')
    if os.path.exists(home_session):
        return home_session
    return os.path.expanduser('~/.telegram/tg_session.session')

# Project root: 4 levels up from .claude/skills/telegram/scripts/
DEFAULT_AUDIO_DIR = os.path.expanduser("~/.telegram/audio")


def get_client():
  """Create Telethon client from env vars."""
  try:
    from telethon import TelegramClient
  except ImportError:
    print('{"error": "telethon not installed — pip install telethon"}', file=sys.stderr)
    sys.exit(1)

  api_id = int(os.getenv("TG_API_ID", "0"))
  api_hash = os.getenv("TG_API_HASH", "")
  session = os.getenv("TG_SESSION", resolve_session())

  if not api_id or not api_hash:
    print('{"error": "TG_API_ID / TG_API_HASH not set"}', file=sys.stderr)
    sys.exit(1)

  return TelegramClient(session, api_id, api_hash)


def extract_audio_from_video(video_path: str, output_path: str) -> bool:
  """Extract audio track from video_note using ffmpeg."""
  try:
    subprocess.run(
      ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libopus", "-y", output_path],
      capture_output=True, timeout=60,
    )
    Path(video_path).unlink(missing_ok=True)
    return Path(output_path).exists()
  except (subprocess.TimeoutExpired, FileNotFoundError) as e:
    print(f'{{"error": "ffmpeg failed: {e}"}}', file=sys.stderr)
    return False


async def fetch_voice_messages(
  entity_type: str,
  entity_name: str,
  limit: int = 10,
  audio_dir: str | None = None,
  media_types: list[str] | None = None,
) -> list[dict]:
  """Fetch and download voice messages.

  Returns list of metadata records (no transcription).
  """
  if media_types is None:
    media_types = ["voice", "audio", "video_note", "video"]

  client = get_client()
  results = []

  if audio_dir is None:
    audio_dir = DEFAULT_AUDIO_DIR
  Path(audio_dir).mkdir(parents=True, exist_ok=True)

  try:
    await client.start()

    if entity_type == "saved_messages":
      entity = await client.get_me()
      chat_name = "saved_messages"
    else:
      entity = await client.get_entity(entity_name)
      chat_name = entity_name

    chat_id = str(entity.id)
    messages = await client.get_messages(entity, limit=limit)

    for msg in reversed(messages):
      # Detect voice/audio/video_note/video/video_document
      media_type = None
      if msg.voice and "voice" in media_types:
        media_type = "voice"
      elif msg.audio and "audio" in media_types:
        media_type = "audio"
      elif msg.video_note and "video_note" in media_types:
        media_type = "video_note"
      elif msg.video and "video" in media_types:
        media_type = "video"
      elif msg.document and "video" in media_types:
        # Document with video MIME type (e.g. video/mp4 sent as file)
        mime = getattr(msg.document, "mime_type", "") or ""
        if mime.startswith("video/"):
          media_type = "video"
        else:
          continue
      else:
        continue

      # Extract duration from document attributes
      duration = None
      doc = msg.document
      if doc and doc.attributes:
        for attr in doc.attributes:
          if hasattr(attr, "duration"):
            duration = int(attr.duration) if attr.duration else None
            break

      msg_date = msg.date if msg.date else datetime.utcnow()
      ts = msg_date.strftime("%Y%m%d-%H%M%S")
      filename = f"{ts}-{msg.id}.ogg"
      file_path = os.path.join(audio_dir, filename)

      # Download
      try:
        downloaded = await client.download_media(msg, file=file_path)
        if not downloaded:
          continue
        downloaded_path = str(downloaded)

        # Extract audio from video_note or video
        if media_type in ("video_note", "video"):
          ogg_path = file_path
          if not extract_audio_from_video(downloaded_path, ogg_path):
            continue
          downloaded_path = ogg_path

        file_size = Path(downloaded_path).stat().st_size if Path(downloaded_path).exists() else None

        record = {
          "id": msg.id,
          "chat_id": chat_id,
          "chat_name": chat_name,
          "date": msg_date.isoformat(),
          "duration": duration,
          "media_type": media_type,
          "file_path": str(Path(downloaded_path).resolve()),
          "file_size": file_size,
        }
        results.append(record)

      except Exception as e:
        print(f'{{"warning": "download failed for msg {msg.id}: {e}"}}', file=sys.stderr)
        continue

  finally:
    await client.disconnect()

  return results


def main():
  parser = argparse.ArgumentParser(description="Telegram Voice Fetcher → metadata JSONL")
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("--saved-messages", action="store_true", help="Read from Saved Messages")
  group.add_argument("--chat", type=str, help="Read from a specific chat (username)")

  parser.add_argument("--limit", type=int, default=10, help="Max messages to process (default: 10)")
  parser.add_argument("--output", "-o", type=str, help="Save metadata to file (default: stdout)")
  parser.add_argument("--audio-dir", type=str, default=None,
                      help=f"Directory for downloaded audio (default: {DEFAULT_AUDIO_DIR})")
  parser.add_argument("--media-types", type=str, default="voice,audio,video_note,video",
                      help="Comma-separated media types (default: voice,audio,video_note,video)")

  args = parser.parse_args()

  if args.saved_messages:
    entity_type, entity_name = "saved_messages", ""
  else:
    entity_type, entity_name = "chat", args.chat

  media_types = [t.strip() for t in args.media_types.split(",")]

  results = asyncio.run(fetch_voice_messages(
    entity_type=entity_type,
    entity_name=entity_name,
    limit=args.limit,
    audio_dir=args.audio_dir,
    media_types=media_types,
  ))

  output = "\n".join(json.dumps(r, ensure_ascii=False) for r in results)

  if args.output:
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(output, encoding="utf-8")
    print(f'{{"info": "saved {len(results)} metadata records to {args.output}"}}', file=sys.stderr)
  else:
    print(output)

  print(f'{{"info": "downloaded {len(results)} voice messages"}}', file=sys.stderr)


if __name__ == "__main__":
  main()
