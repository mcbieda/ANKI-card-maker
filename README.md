# ANKI-card-maker

A Claude Code skill that turns a topic, article, or ChatGPT conversation into a
set of Anki flashcards, saved as a CSV ready for Anki's import.

## What's in this folder

- `SKILL.md` &mdash; the instructions Claude follows when the skill is invoked
  (card-writing rules, tone, what to emphasize, etc.).
- `ABOUT-ME.md` &mdash; a short description of the user's background, used to
  calibrate how much explanation/detail the cards include.
- `scripts/chatgpt_share_extractor.py` &mdash; a standalone helper that extracts
  the full text of a `chatgpt.com/share/...` conversation. Plain web-fetch
  tools only see the page `<title>` for these links (the conversation is
  client-rendered), so this script is required whenever the flashcard source
  is a ChatGPT share link.

## Requirements

- **Python 3.9 or later.**
- **No third-party packages.** `chatgpt_share_extractor.py` only uses the
  Python standard library (`argparse`, `json`, `re`, `sys`, `urllib.request`,
  `pathlib`) &mdash; nothing to `pip install`.
- Network access to `chatgpt.com` (only needed if you're extracting a share
  link; not needed for other flashcard sources).

## Installing the skill

Copy this whole folder into your `.claude/skills/` directory (project-level
`.claude/skills/ANKI-card-maker/` or your user-level `~/.claude/skills/`), then
invoke it in Claude Code as `/ANKI-card-maker`.

**Before using it, edit `ABOUT-ME.md` to describe your own background.** It
comes with the original author's description (a PhD biomedical scientist) as
an example — the skill uses whatever is in that file to calibrate how much
explanation and detail the cards include, so leaving it as-is will pitch
every deck at that level regardless of who's actually using it.

## Testing the extractor script manually

You can run the extractor on its own, outside of Claude, to sanity-check it:

```bash
python3 scripts/chatgpt_share_extractor.py https://chatgpt.com/share/<id> --out-dir /tmp
```

On success it prints a one-line JSON summary and writes two files into
`--out-dir`:

- `<id>.transcript.txt` &mdash; role-labeled `=== USER ===` / `=== ASSISTANT ===`
  text blocks (what the skill reads to write cards)
- `<id>.messages.json` &mdash; the same content as structured JSON
  (`role`, `create_time`, `text` per message)

On failure it exits non-zero with a message on stderr explaining what went
wrong (e.g. no share-page payload found, or zero messages recovered) rather
than silently writing an empty/garbage transcript.
