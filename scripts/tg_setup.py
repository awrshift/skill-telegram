#!/usr/bin/env python3
"""Diagnostic script — verify Telegram skill setup.

Checks env vars, session file, dependencies, and connectivity.

Usage:
  python3 tg_setup.py          # Full diagnostic
  python3 tg_setup.py --auth   # Interactive auth (create session file)
"""

import argparse
import asyncio
import os
import shutil
import sys
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



def check_env():
  """Check required environment variables."""
  api_id = os.getenv("TG_API_ID", "")
  api_hash = os.getenv("TG_API_HASH", "")
  ok = True

  if not api_id or api_id == "0":
    print("  [FAIL] TG_API_ID not set")
    ok = False
  else:
    print(f"  [ OK ] TG_API_ID = {api_id[:4]}...")

  if not api_hash:
    print("  [FAIL] TG_API_HASH not set")
    ok = False
  else:
    print(f"  [ OK ] TG_API_HASH = {api_hash[:6]}...")

  return ok


def check_session():
  """Check session file exists."""
  session = os.getenv("TG_SESSION", resolve_session())
  if Path(session).exists():
    size = Path(session).stat().st_size
    print(f"  [ OK ] Session file: {session} ({size} bytes)")
    return True
  else:
    print(f"  [FAIL] Session file not found: {session}")
    print("         Run: python3 tg_setup.py --auth")
    return False


def check_dependencies():
  """Check Python packages and system tools."""
  ok = True

  # telethon
  try:
    import telethon
    print(f"  [ OK ] telethon {telethon.__version__}")
  except ImportError:
    print("  [FAIL] telethon — pip install telethon")
    ok = False

  # mlx-whisper
  try:
    import mlx_whisper
    v = getattr(mlx_whisper, "__version__", "?")
    print(f"  [ OK ] mlx-whisper {v}")
  except ImportError:
    print("  [WARN] mlx-whisper not installed (needed for voice transcription)")
    try:
      import whisper
      print(f"  [ OK ] openai-whisper (fallback)")
    except ImportError:
      print("  [WARN] openai-whisper not installed either")
      print("         pip install mlx-whisper   (Apple Silicon)")
      print("         pip install openai-whisper (CPU fallback)")

  # pyyaml
  try:
    import yaml
    print(f"  [ OK ] pyyaml")
  except ImportError:
    print("  [WARN] pyyaml not installed (needed for pipeline configs)")

  # ffmpeg
  if shutil.which("ffmpeg"):
    print(f"  [ OK ] ffmpeg (system)")
  else:
    print("  [WARN] ffmpeg not found (needed for video_note audio extraction)")
    print("         brew install ffmpeg")

  return ok


async def check_connection():
  """Test Telegram connection."""
  try:
    from telethon import TelegramClient
  except ImportError:
    print("  [SKIP] Cannot test connection (telethon not installed)")
    return False

  api_id = int(os.getenv("TG_API_ID", "0"))
  api_hash = os.getenv("TG_API_HASH", "")
  session = os.getenv("TG_SESSION", resolve_session())

  if not api_id or not api_hash:
    print("  [SKIP] Cannot test connection (env vars missing)")
    return False

  if not Path(session).exists():
    print("  [SKIP] Cannot test connection (no session file)")
    return False

  client = TelegramClient(session, api_id, api_hash)
  try:
    await client.start()
    me = await client.get_me()
    name = me.first_name or me.username or str(me.id)
    print(f"  [ OK ] Connected as: {name} (ID: {me.id})")
    return True
  except Exception as e:
    print(f"  [FAIL] Connection failed: {e}")
    return False
  finally:
    await client.disconnect()


async def do_auth():
  """Interactive authentication — creates session file."""
  try:
    from telethon import TelegramClient
  except ImportError:
    print("Error: telethon not installed — pip install telethon")
    sys.exit(1)

  api_id = int(os.getenv("TG_API_ID", "0"))
  api_hash = os.getenv("TG_API_HASH", "")

  if not api_id or not api_hash:
    print("Error: set TG_API_ID and TG_API_HASH in .env first")
    sys.exit(1)

  session = os.getenv("TG_SESSION", resolve_session())
  Path(session).parent.mkdir(parents=True, exist_ok=True)

  print(f"Creating session at: {session}")
  print("You will be prompted for your phone number and code.\n")

  client = TelegramClient(session, api_id, api_hash)
  await client.start()
  me = await client.get_me()
  print(f"\nAuthenticated as: {me.first_name} ({me.username})")
  await client.disconnect()
  print(f"Session saved: {session}")


def main():
  parser = argparse.ArgumentParser(description="Telegram Skill — Setup Diagnostic")
  parser.add_argument("--auth", action="store_true",
                      help="Interactive authentication (create session file)")

  args = parser.parse_args()

  if args.auth:
    asyncio.run(do_auth())
    return

  print("\n=== Telegram Skill — Setup Diagnostic ===\n")

  print("[1] Environment Variables")
  env_ok = check_env()

  print("\n[2] Session File")
  session_ok = check_session()

  print("\n[3] Dependencies")
  deps_ok = check_dependencies()

  print("\n[4] Connection Test")
  conn_ok = asyncio.run(check_connection())

  print("\n" + "=" * 42)
  all_ok = env_ok and session_ok and deps_ok and conn_ok
  if all_ok:
    print("  All checks passed. Telegram skill ready.")
  else:
    print("  Some checks failed. Fix issues above.")
  print()


if __name__ == "__main__":
  main()
