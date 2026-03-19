#!/usr/bin/env python3
"""Ad-hoc Telegram reader — fetch messages from any chat/channel/saved_messages.

Usage:
  python3 tg_read.py --saved-messages --limit 10
  python3 tg_read.py --chat username --limit 20
  python3 tg_read.py --channel SEOBAZA --limit 5

Output: JSON lines to stdout (one message per line).
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Session file resolution order:
# 1. --session CLI flag
# 2. TG_SESSION env var
# 3. .claude/data/telegram/tg_session.session (relative to project root)
# 4. ~/.telegram/tg_session.session (global fallback)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = str(SCRIPT_DIR.parents[3])  # up from skills/telegram/scripts/


def resolve_session(cli_session=None):
    if cli_session:
        return cli_session
    if os.getenv("TG_SESSION"):
        return os.getenv("TG_SESSION")
    project_session = os.path.join(PROJECT_ROOT, ".claude", "data", "telegram", "tg_session.session")
    if os.path.exists(project_session):
        return project_session
    home_session = os.path.expanduser("~/.telegram/tg_session.session")
    if os.path.exists(home_session):
        return home_session
    return project_session  # default path (will be created on first auth)


async def read_messages(entity_type: str, entity_name: str, limit: int, session: str = None):
  """Read messages from a Telegram entity and print as JSON lines."""
  try:
    from telethon import TelegramClient
  except ImportError:
    print('{"error": "telethon not installed. Run: pip install telethon"}', file=sys.stderr)
    sys.exit(1)

  api_id = int(os.getenv("TG_API_ID", "0"))
  api_hash = os.getenv("TG_API_HASH", "")
  session_file = resolve_session(session)

  if not api_id or not api_hash:
    print('{"error": "TG_API_ID / TG_API_HASH not set"}', file=sys.stderr)
    sys.exit(1)

  client = TelegramClient(session_file, api_id, api_hash)

  try:
    await client.start()

    if entity_type == "saved_messages":
      entity = await client.get_me()
    elif entity_type in ("chat", "channel"):
      entity = await client.get_entity(entity_name)
    else:
      print(f'{{"error": "unknown entity type: {entity_type}"}}', file=sys.stderr)
      return

    messages = await client.get_messages(entity, limit=limit)

    for msg in reversed(messages):
      record = {
        "id": msg.id,
        "date": msg.date.isoformat() if msg.date else None,
        "text": msg.text or msg.message or None,
        "has_voice": bool(msg.voice),
        "has_audio": bool(msg.audio),
        "has_video_note": bool(msg.video_note),
        "has_photo": bool(msg.photo),
        "has_document": bool(msg.document),
      }

      if msg.document:
        record["mime_type"] = msg.document.mime_type
        record["file_size"] = msg.document.size
        for attr in msg.document.attributes:
          if hasattr(attr, "duration"):
            record["duration"] = int(attr.duration) if attr.duration else None
          if hasattr(attr, "file_name"):
            record["file_name"] = attr.file_name

      print(json.dumps(record, ensure_ascii=False))

  finally:
    await client.disconnect()


def main():
  parser = argparse.ArgumentParser(description="Ad-hoc Telegram reader")
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("--saved-messages", action="store_true", help="Read from Saved Messages")
  group.add_argument("--chat", type=str, help="Read from a specific chat (username)")
  group.add_argument("--channel", type=str, help="Read from a public channel (username)")

  parser.add_argument("--limit", type=int, default=10, help="Number of messages (default: 10)")
  parser.add_argument("--session", type=str, help="Path to .session file (or set TG_SESSION env)")

  args = parser.parse_args()

  if args.saved_messages:
    entity_type, entity_name = "saved_messages", ""
  elif args.chat:
    entity_type, entity_name = "chat", args.chat
  elif args.channel:
    entity_type, entity_name = "channel", args.channel

  asyncio.run(read_messages(entity_type, entity_name, args.limit, session=args.session))


if __name__ == "__main__":
  main()
