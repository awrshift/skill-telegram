#!/usr/bin/env python3
"""Fetch text messages from public Telegram channels → JSONL.

Pure Telegram data layer — no DB writes, no classification.
Outputs JSON lines to stdout (one record per message).

Usage:
  python3 tg_fetch_channels.py --channel SEOBAZA --limit 20
  python3 tg_fetch_channels.py --channels SEOBAZA,seo_inside --limit 10
  python3 tg_fetch_channels.py --channel SEOBAZA --since 2026-03-01
  python3 tg_fetch_channels.py --channel SEOBAZA --output messages.jsonl
  python3 tg_fetch_channels.py --channel SEOBAZA --pretty

Requires: telethon
Env: TG_API_ID, TG_API_HASH
Session: reuses shared session file at .claude/data/telegram/tg_session.session

Output JSON schema: see references/json-schema.md
"""

import argparse
import asyncio
import json
import os
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

# Bundled sanitizer (co-located in scripts/)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sanitizer import sanitize, extract_links, content_hash


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


async def fetch_channel(client, channel_name: str, limit: int = 50,
                        since: str | None = None) -> list[dict]:
  """Fetch text messages from a single channel.

  Returns list of records matching the interchange JSON schema.
  """
  from telethon.errors import ChannelPrivateError

  results = []
  try:
    entity = await client.get_entity(channel_name)
    channel_id = str(entity.id)

    kwargs = {"limit": limit}
    if since:
      kwargs["offset_date"] = datetime.fromisoformat(since + "T23:59:59")

    messages = await client.get_messages(entity, **kwargs)

    for msg in reversed(messages):
      raw_text = msg.text or msg.message or ""
      if not raw_text.strip():
        continue

      reply_to = None
      if msg.reply_to:
        reply_to = msg.reply_to.reply_to_msg_id

      record = {
        "channel": channel_name,
        "channel_id": channel_id,
        "id": msg.id,
        "date": msg.date.isoformat() if msg.date else None,
        "text": raw_text,
        "text_sanitized": sanitize(raw_text),
        "links": extract_links(raw_text),
        "hash": content_hash(raw_text),
        "reply_to": reply_to,
        "views": msg.views,
        "forwards": msg.forwards,
      }
      results.append(record)

  except ChannelPrivateError:
    print(f'{{"error": "channel {channel_name} is private"}}', file=sys.stderr)
  except Exception as e:
    print(f'{{"error": "failed to fetch {channel_name}: {e}"}}', file=sys.stderr)

  return results


async def fetch_all_channels(channels: list[str], limit: int = 50,
                             since: str | None = None) -> list[dict]:
  """Fetch from multiple channels with rate limiting."""
  client = get_client()
  all_results = []

  try:
    await client.start()

    for i, ch in enumerate(channels):
      if i > 0:
        await asyncio.sleep(2)  # Rate limit
      results = await fetch_channel(client, ch, limit=limit, since=since)
      all_results.extend(results)
      print(f'{{"info": "fetched {len(results)} from {ch}"}}', file=sys.stderr)

  finally:
    await client.disconnect()

  return all_results


def main():
  parser = argparse.ArgumentParser(description="Telegram Channel Fetcher → JSONL")
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("--channel", type=str, help="Single channel username")
  group.add_argument("--channels", type=str, help="Comma-separated channel usernames")

  parser.add_argument("--limit", type=int, default=50, help="Max messages per channel (default: 50)")
  parser.add_argument("--since", type=str, default=None,
                      help="Fetch messages since date (YYYY-MM-DD)")
  parser.add_argument("--output", "-o", type=str, help="Save to file (default: stdout)")
  parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")

  args = parser.parse_args()

  if args.channel:
    channel_list = [args.channel]
  else:
    channel_list = [ch.strip() for ch in args.channels.split(",") if ch.strip()]

  results = asyncio.run(fetch_all_channels(channel_list, limit=args.limit, since=args.since))

  if args.pretty:
    output = json.dumps(results, ensure_ascii=False, indent=2)
  else:
    output = "\n".join(json.dumps(r, ensure_ascii=False) for r in results)

  if args.output:
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(output, encoding="utf-8")
    print(f'{{"info": "saved {len(results)} messages to {args.output}"}}', file=sys.stderr)
  else:
    print(output)


if __name__ == "__main__":
  main()
