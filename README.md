# ANKI-card-maker

A Claude Code skill that turns a topic, a web article, or an LLM chat
conversation into a set of [Anki](https://apps.ankiweb.net/) flashcards,
written out as a CSV that's ready to import.

## Why this is interesting

Asking a chatbot to "make me some flashcards" generally produces a pile of
trivia: one card per fact, every fact weighted equally, phrased however the
source phrased it. That's a bad deck. This skill is opinionated about what a
*good* deck looks like, and encodes those opinions so you get them every time:

- **It writes for understanding, not recall of surface facts.** Every deck is
  required to include cards that ask for plain-English intuition — *why is this
  used at all*, *explain this to an undergrad new to your lab*, *explain why
  this matters to someone outside your field*. These are the cards people skip
  when writing decks by hand, and they're the ones that make the technical
  cards stick.
- **It insists on limitations.** There are always cards about where the method
  or idea breaks down, when it gives bad answers, when you shouldn't use it.
  Source material (papers, docs, chatbot explanations) is systematically
  optimistic; a deck built straight from it inherits that bias.
- **It prunes.** The skill is told to focus on the main topic and the most
  important ideas, and to use only a subset of the examples in a source, rather
  than trying to cover everything. Long sources produce focused decks, not
  200-card slogs you'll never actually review.
- **Equations get the full treatment.** Any card with an equation must show the
  equation, an intuitive explanation of what it's doing, and the meaning of
  *every* symbol — rendered so Anki displays it properly rather than as raw
  ASCII soup.
- **It can mine your own confusion.** Point it at a ChatGPT or Claude
  conversation and it reads the *dialogue*, not just the answers: where you
  asked a follow-up, backtracked, or misunderstood something is exactly where
  it concentrates the cards. A chat log is a record of what you didn't know an
  hour ago, which is far better card-selection signal than a textbook's table
  of contents.
- **It's calibrated to you.** See [ABOUT-ME.md](#about-memd--tuning-the-cards-to-you)
  below.
- **It checks its own work.** After writing the CSV, the skill reads it back in
  and reviews every card for accuracy and clarity before handing it over.

## What's in this folder

- `SKILL.md` — the instructions Claude follows when the skill is invoked: the
  card-writing rules above, plus how to handle each kind of source.
- `ABOUT-ME.md` — a short description of your background, used to calibrate how
  much explanation and detail the cards carry. **Edit this before first use.**
- `scripts/chatgpt_share_extractor.py` — a standalone helper that recovers the
  full text of a `chatgpt.com/share/...` conversation. Required whenever the
  source is a ChatGPT share link; see below for why.

## Requirements

- **Claude Code** (this is a skill, not a standalone program).
- **Python 3.9 or later** — only needed for the ChatGPT share-link extractor.
- **No third-party packages.** `chatgpt_share_extractor.py` uses the standard
  library only (`argparse`, `json`, `re`, `sys`, `urllib.request`, `pathlib`).
  Nothing to `pip install`, no API key.
- Network access to `chatgpt.com`, if and only if you're extracting a share
  link.
- Anki itself, to import the resulting CSV.

## Installing

The skill is the repo, so clone it straight into a `.claude/skills/` directory:

```bash
# user-scoped: available in every project
git clone https://github.com/<your-username>/ANKI-card-maker \
  ~/.claude/skills/ANKI-card-maker

# project-scoped: available in one repo
git clone https://github.com/<your-username>/ANKI-card-maker \
  /path/to/project/.claude/skills/ANKI-card-maker
```

Or, if you already have the folder on disk, just copy it:

```bash
cp -r ANKI-card-maker ~/.claude/skills/
```

Then invoke it in Claude Code as `/ANKI-card-maker`, or just describe what you
want ("make Anki cards from this paper") and Claude will pick it up from the
skill's description.

The folder name is the command name. `SKILL.md` pins it with `name:
ANKI-card-maker`, so a differently-named clone directory still gives you
`/ANKI-card-maker`; change both if you want to rename it.

## ABOUT-ME.md — tuning the cards to you

`ABOUT-ME.md` is read *first*, before any card is written, and it shapes
everything after it. It's a free-form description of who you are and what you
already know. The shipped version is a single line:

```
I am PhD biomedical scientist with solid understanding of statistics and machine learning
```

That's the original author's background, and it is doing real work: with it in
place, a deck about a regularized regression method won't waste cards defining
"p-value" or "overfitting", and it will use `L2 penalty` without apologizing for
the term. Leave it as-is and every deck you generate — on any subject — will be
pitched at a biomedical PhD who's comfortable with ML.

**So edit it.** Useful things to state:

- Your field and level ("second-year CS undergrad", "practicing cardiologist",
  "self-taught programmer, no formal math past calculus").
- Areas where you're strong, so the skill can skip the basics.
- Areas where you're weak or rusty, so it slows down and explains more.
- Subjects you're actively studying, and why.

Two examples of how differently the same source gets carded:

| ABOUT-ME.md says | A card on "eigenvector" becomes |
| --- | --- |
| strong linear algebra | assumed known; used freely in other cards, no card of its own |
| rusty on linear algebra | its own card, with a geometric intuition and a worked 2×2 example |

When in doubt the skill errs toward *more* explanation and clarity rather than
less, so an under-specified `ABOUT-ME.md` produces verbose cards rather than
incomprehensible ones.

## Sources you can point it at

### A topic or your own notes

Just ask. "Make Anki cards on the bias–variance tradeoff", or point it at a
local file.

### A web page

The skill deliberately does **not** use Claude Code's built-in `WebFetch` for
this. That tool runs the page through a separate small model and returns *that
model's paraphrase*, so you'd be writing cards from a lossy summary — exact
wording, specific numbers, and equations all get flattened or dropped. Instead
the skill fetches the real page text itself (`curl`, or a source-specific text
API — e.g. Wikipedia's `action=query&prop=extracts&explaintext=1`) and reads the
actual content.

### A ChatGPT share link — the special case

`chatgpt.com/share/...` pages are client-rendered. Fetching one gives you the
`<title>` and essentially nothing else: the conversation isn't in the HTML as
readable text. It's buried inside
`<script>window.__reactRouterContext.streamController.enqueue("...")</script>`
tags as a JSON-stringified turbo-stream payload — a flat array in which objects
and lists store *integer indices back into the same array* instead of inline
values. Nothing readable falls out until that reference graph is walked and
resolved.

`scripts/chatgpt_share_extractor.py` does that whole pipeline: fetch → pull the
`enqueue(...)` string literals → JSON-unescape and concatenate → parse the
leading array → resolve the index-reference graph (with cycle handling) → walk
it for message nodes → de-duplicate and sort by timestamp → write out the
transcript.

Run it yourself to sanity-check it:

```bash
python3 scripts/chatgpt_share_extractor.py https://chatgpt.com/share/<id> --out-dir /tmp
```

It writes two files into `--out-dir`, named after the share id:

- `<id>.transcript.txt` — role-labeled `=== USER ===` / `=== ASSISTANT ===`
  blocks; this is what the skill reads to write cards.
- `<id>.messages.json` — the same content structured as
  `{"role", "create_time", "text"}` per message.

and prints a one-line JSON summary to stdout so the skill can find them:

```json
{"share_id": "...", "title": "...", "num_messages": 42,
 "transcript_path": "...", "messages_path": "..."}
```

`--html-file page.html` reads a previously-saved copy instead of fetching, which
is handy for debugging.

On failure it exits non-zero with an explanation on stderr — "no
`streamController.enqueue` payloads found" (OpenAI changed the format, or you
hit a login wall) or "zero user/assistant messages recovered" (the node shape
changed) — rather than quietly emitting an empty transcript. The skill is
instructed to read that stderr and stop, not to silently fall back to
guesswork. Since this depends on an undocumented internal format, it *will*
eventually break when OpenAI changes their share pages; the error messages are
written to make that obvious when it happens.

### A Claude conversation, or any other chat UI

There's no extractor for `claude.ai/share/...` links, and there can't easily be
one: unlike ChatGPT's share pages, Claude's is a pure client-rendered shell with
no conversation content anywhere in the page source. There is nothing to fetch
or decode.

Instead, copy the conversation out of the browser into a plain `.txt` file and
point the skill at that:

- Name it with a `chat-` or `dialogue-` prefix (e.g.
  `chat-gini-coefficient.txt`) as a hint that it's a pasted conversation and not
  an article.
- The filename alone isn't enough — say so in your prompt: *"make flashcards
  from `chat-gini-coefficient.txt`, it's a pasted conversation with Claude."*
  That's what tells the skill to look for your weak spots rather than treat it
  as a reference document.
- You don't need to label who said what. The skill infers user vs. assistant
  turns from context (short questions vs. long structured answers) and only
  asks if the turn-taking is genuinely ambiguous.
- **Expect mangled equations.** Copy-pasted math routinely arrives as stray
  unicode, half-broken LaTeX, or an alt-text placeholder where the formula used
  to be. The skill reconstructs the equation from context and re-renders it
  cleanly rather than transcribing the garbage onto a card — and if a formula is
  too far gone to reconstruct confidently, it asks you instead of guessing.

## Importing the CSV into Anki

The output is a simple two-field front/back CSV. In Anki: **File → Import**,
pick the CSV, choose the **Basic** note type and the deck you want, and map
field 1 → Front, field 2 → Back.

If the deck contains equations, tick **Allow HTML in fields** on the import
screen so the math renders instead of showing as literal markup. Anki renders
MathJax between `\(...\)` (inline) and `\[...\]` (display) out of the box on
desktop, AnkiMobile, and AnkiDroid.

It's worth skimming the CSV before importing — the skill reviews its own output,
but you're the one who knows whether a card is actually worth reviewing 200
times.

## Customizing further

`SKILL.md` is just prose instructions; edit it directly to change the house
style. The numbered rules are independent, so you can add, drop, or reweight
them freely — e.g. raise or lower how many intuition cards are required, add a
rule for cloze-deletion cards, or change the required CSV layout to match a
different note type.

## License

MIT &mdash; see [LICENSE](LICENSE). `ABOUT-ME.md` ships with the original
author's one-line background as a worked example; replace it with your own.
