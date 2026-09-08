#!/usr/bin/env python3
"""
chatgpt_share_extractor.py

Extracts the full conversation text from a ChatGPT "share" link
(https://chatgpt.com/share/<id>) for use by the ANKI-card-maker skill.

WHY THIS EXISTS
---------------
chatgpt.com/share pages are client-rendered. A plain HTML/text fetch (or a
generic web-fetch tool) only sees the <title> tag -- the actual Q&A text is
not present as readable HTML. It is embedded inside one or more
<script>window.__reactRouterContext.streamController.enqueue("...")</script>
tags as a JSON-stringified payload, and that payload itself is a flat,
reference-based array format (used by the "turbo-stream" protocol React
Router's streaming loader data uses): objects/arrays store plain integers
that are indices back into the same top-level array instead of inline
values, so the JSON has to be walked and resolved before any message text
is recoverable.

This script does the whole pipeline in one shot:
  1. Fetch the share page HTML (or read a previously-saved copy).
  2. Pull out every streamController.enqueue("...") string literal and
     JSON-unescape it.
  3. Concatenate them and parse the leading JSON array (trailing
     "P<n>:..." promise-resolution lines are discarded).
  4. Resolve the index-reference graph into plain nested Python objects.
  5. Walk the resolved tree for every {"author": {...}, "content": {...}}
     node with content_type "text", pull out role + create_time + text.
  6. De-duplicate (the same node is often reachable via more than one
     path in the graph) and sort by create_time.
  7. Write a plain transcript.txt (role-labeled, ready to hand to the
     flashcard-writing step) and a messages.json (structured, for
     anything that wants role/create_time/text separately).

USAGE
-----
    python3 chatgpt_share_extractor.py <share_url_or_id> [--out-dir DIR]

    # or, to avoid a network fetch (e.g. you already saved the page):
    python3 chatgpt_share_extractor.py <share_url_or_id> --html-file page.html

OUTPUT
------
Writes into --out-dir (default: current directory), named after the share id:
    <id>.transcript.txt   -- "=== USER ===" / "=== ASSISTANT ===" text blocks
    <id>.messages.json    -- [{"role", "create_time", "text"}, ...]

Prints a one-line JSON summary to stdout on success:
    {"share_id": "...", "title": "...", "num_messages": N,
     "transcript_path": "...", "messages_path": "..."}

so a calling skill/agent can locate the output without re-parsing prose.

Exits non-zero with a message on stderr if the page structure doesn't
match what this script expects (e.g. OpenAI changed the format) -- it does
NOT silently produce an empty/garbage transcript.
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

SHARE_ID_RE = re.compile(r"^[0-9a-fA-F-]{20,}$")
ENQUEUE_RE = re.compile(
    r'streamController\.enqueue\(("(?:[^"\\]|\\.)*")\)', re.S
)


def normalize_share_id_or_url(value: str) -> tuple[str, str]:
    """Return (share_id, canonical_url) from either a bare id or a full URL."""
    m = re.search(r"chatgpt\.com/share/([0-9a-fA-F-]+)", value)
    if m:
        share_id = m.group(1)
    elif SHARE_ID_RE.match(value):
        share_id = value
    else:
        raise ValueError(
            f"Could not recognize {value!r} as a chatgpt.com share URL or id"
        )
    return share_id, f"https://chatgpt.com/share/{share_id}"


def fetch_html(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_stream_text(html: str) -> str:
    """Pull every streamController.enqueue("...") payload and concatenate them."""
    matches = ENQUEUE_RE.findall(html)
    if not matches:
        raise RuntimeError(
            "No streamController.enqueue(...) payloads found in the page. "
            "OpenAI may have changed the share-page format, or this wasn't "
            "a real chatgpt.com/share page (e.g. it was a login wall)."
        )
    parts = []
    for raw in matches:
        try:
            parts.append(json.loads(raw))
        except json.JSONDecodeError:
            # Skip a chunk we can't unescape rather than aborting the whole
            # extraction -- most of the useful content lives in one chunk.
            continue
    if not parts:
        raise RuntimeError(
            "Found enqueue(...) calls but none of them were valid "
            "JSON-escaped strings -- cannot proceed."
        )
    return "".join(parts)


def parse_stream_array(stream_text: str) -> list:
    """
    The decoded stream is a big JSON array optionally followed by trailing
    "P<n>:[...]" promise-resolution lines that are not part of the array.
    Parse just the array.
    """
    decoder = json.JSONDecoder()
    stream_text = stream_text.lstrip()
    try:
        arr, _end = decoder.raw_decode(stream_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Could not parse the decoded stream as JSON: {e}")
    if not isinstance(arr, list):
        raise RuntimeError(
            f"Expected the decoded stream to start with a JSON array, got {type(arr)}"
        )
    return arr


def resolve_stream_array(arr: list):
    """
    Resolve the turbo-stream-style index-reference graph.

    Encoding rules observed in chatgpt.com share pages:
      - The array is 0-indexed; every element may be referenced by its index.
      - A dict value like {"_5": 6} means: the real key is arr[5] (a string),
        and the real value is resolve(6).
      - A list value like [241] means: the real list is [resolve(241)].
      - A negative index is a sentinel (undefined/null-ish) -> resolved as None.
      - Leaves (str/int/float/bool/None) resolve to themselves.

    Returns the resolved value of arr[0] (the root), with a memo dict so
    that repeated/circular references decode instead of infinite-looping.
    """
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    memo: dict[int, object] = {}

    def resolve(idx):
        if not isinstance(idx, int):
            return idx
        if idx in memo:
            return memo[idx]
        if idx < 0 or idx >= len(arr):
            return None
        val = arr[idx]
        if isinstance(val, dict):
            result: dict = {}
            memo[idx] = result
            for k, v in val.items():
                # keys are encoded as "_<index>" pointing at the real key string
                key_idx = int(k[1:]) if k.startswith("_") and k[1:].isdigit() else None
                if key_idx is not None:
                    key_raw = arr[key_idx] if key_idx < len(arr) else k
                    key = key_raw if isinstance(key_raw, str) else resolve(key_idx)
                else:
                    key = k
                result[key] = resolve(v)
            return result
        elif isinstance(val, list):
            result_list: list = []
            memo[idx] = result_list
            for item in val:
                result_list.append(resolve(item) if isinstance(item, int) else item)
            return result_list
        else:
            memo[idx] = val
            return val

    return resolve(0)


def collect_messages(root) -> list[dict]:
    """
    Walk the resolved tree (which contains cycles) and collect every
    {"author": {"role": ...}, "content": {"content_type": "text", "parts": [...]}}
    node, for roles that represent actual conversation turns.
    """
    visited: set[int] = set()
    messages: list[dict] = []
    stack = [root]
    while stack:
        node = stack.pop()
        oid = id(node)
        if oid in visited:
            continue
        visited.add(oid)
        if isinstance(node, dict):
            author = node.get("author")
            content = node.get("content")
            if isinstance(author, dict) and isinstance(content, dict):
                role = author.get("role")
                ctype = content.get("content_type")
                parts = content.get("parts")
                if role in ("user", "assistant") and ctype == "text" and parts:
                    text = "\n".join(p for p in parts if isinstance(p, str)).strip()
                    if text:
                        messages.append(
                            {
                                "role": role,
                                "create_time": node.get("create_time"),
                                "text": text,
                            }
                        )
            for v in node.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append(item)
    return messages


def dedupe_and_sort(messages: list[dict]) -> list[dict]:
    seen = set()
    uniq = []
    for m in messages:
        key = (m["create_time"], m["role"], m["text"])
        if key not in seen:
            seen.add(key)
            uniq.append(m)
    uniq.sort(key=lambda m: (m["create_time"] is None, m["create_time"]))
    return uniq


def extract_title(html: str) -> str:
    m = re.search(r"<title>([^<]*)</title>", html)
    return m.group(1).strip() if m else ""


def write_outputs(out_dir: Path, share_id: str, title: str, messages: list[dict]):
    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = out_dir / f"{share_id}.transcript.txt"
    messages_path = out_dir / f"{share_id}.messages.json"

    with transcript_path.open("w", encoding="utf-8") as f:
        if title:
            f.write(f"# {title}\n")
        for m in messages:
            f.write(f"\n=== {m['role'].upper()} ===\n{m['text']}\n")

    with messages_path.open("w", encoding="utf-8") as f:
        json.dump(
            {"share_id": share_id, "title": title, "messages": messages},
            f,
            indent=2,
            ensure_ascii=False,
        )

    return transcript_path, messages_path


def main():
    parser = argparse.ArgumentParser(
        description="Extract the full transcript of a chatgpt.com/share conversation."
    )
    parser.add_argument(
        "share", help="chatgpt.com/share URL, or just the share id"
    )
    parser.add_argument(
        "--out-dir",
        default=".",
        help="Directory to write <id>.transcript.txt / <id>.messages.json into (default: cwd)",
    )
    parser.add_argument(
        "--html-file",
        help="Read page HTML from this local file instead of fetching from the network "
        "(useful for debugging, or if the page was already downloaded)",
    )
    args = parser.parse_args()

    try:
        share_id, url = normalize_share_id_or_url(args.share)
        html = (
            Path(args.html_file).read_text(encoding="utf-8", errors="replace")
            if args.html_file
            else fetch_html(url)
        )
        stream_text = extract_stream_text(html)
        arr = parse_stream_array(stream_text)
        root = resolve_stream_array(arr)
        messages = dedupe_and_sort(collect_messages(root))
        if not messages:
            raise RuntimeError(
                "Parsed the page successfully but found zero user/assistant "
                "text messages -- the conversation may be empty, or the "
                "message-node shape has changed."
            )
        title = extract_title(html)
        transcript_path, messages_path = write_outputs(
            Path(args.out_dir), share_id, title, messages
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        json.dumps(
            {
                "share_id": share_id,
                "title": title,
                "num_messages": len(messages),
                "transcript_path": str(transcript_path),
                "messages_path": str(messages_path),
            }
        )
    )


if __name__ == "__main__":
    main()
