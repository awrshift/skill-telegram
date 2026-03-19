"""Input sanitizer for Market Signals System.

Anti prompt-injection + text normalization:
- Strip excessive emoji
- Extract URLs to separate field
- Truncate long messages
- Remove zero-width/control characters
- Escape backticks (prevent markdown poisoning)
- Normalize whitespace
"""

import hashlib
import re

# Zero-width and control characters (except newlines/tabs)
CONTROL_CHARS = re.compile(
  r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f'
  r'\u200b\u200c\u200d\u200e\u200f'
  r'\u202a\u202b\u202c\u202d\u202e'
  r'\ufeff\u2060\u2061\u2062\u2063\u2064]'
)

# Consecutive emoji (5+ in a row)
EXCESSIVE_EMOJI = re.compile(
  r'([\U0001F600-\U0001F9FF\U00002702-\U000027B0'
  r'\U0001F1E0-\U0001F1FF\U00002600-\U000026FF'
  r'\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
  r'\U0001F300-\U0001F5FF]{5,})'
)

# URL pattern
URL_PATTERN = re.compile(
  r'https?://[^\s<>\[\]()"\'\`]{1,500}'
)

MAX_TEXT_LENGTH = 2000


def sanitize(text: str) -> str:
  """Sanitize message text for safe storage and LLM processing."""
  if not text:
    return ""

  # Remove zero-width and control characters
  text = CONTROL_CHARS.sub('', text)

  # Replace excessive emoji with single space
  text = EXCESSIVE_EMOJI.sub(' ', text)

  # Escape backticks (prevent markdown/code injection)
  text = text.replace('`', "'")

  # Normalize whitespace (collapse multiple spaces/newlines)
  text = re.sub(r'\n{3,}', '\n\n', text)
  text = re.sub(r'[ \t]{2,}', ' ', text)

  # Truncate
  if len(text) > MAX_TEXT_LENGTH:
    text = text[:MAX_TEXT_LENGTH] + "..."

  return text.strip()


def extract_links(text: str) -> list[str]:
  """Extract URLs from message text."""
  if not text:
    return []
  urls = URL_PATTERN.findall(text)
  # Deduplicate preserving order
  seen = set()
  result = []
  for url in urls:
    # Strip trailing punctuation
    url = url.rstrip('.,;:!?)')
    if url not in seen:
      seen.add(url)
      result.append(url)
  return result


def content_hash(text: str) -> str:
  """Generate SHA256 hash for dedup."""
  normalized = re.sub(r'\s+', ' ', (text or "").strip().lower())
  return hashlib.sha256(normalized.encode()).hexdigest()[:16]
