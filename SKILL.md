---
description: creates a set of flashcards that are appropriate for ANKI, evaluates these, and saves them to an appropriately named csv file for import into ANKI
---

See README.md for setup requirements (Python version, dependencies) if installing this skill elsewhere.

## INSTRUCTIONS

0. Follow description of my skills and interests found in ABOUT-ME.md to shape the rest of this
	- if in doubt, include a bit more information in the answer and a bit more clarity
1. The goal of this is to create a file of flashcards for import into ANKI.
2. Each card has the simple back and front format.
3. The file should be named as the user indicates, or creating a reasonable name.

4. If a web address is given, the contents of the web address should be read and the cards based on the content at the web address and associated knowledge.
5. Note that if chatgpt web addresses are given, these will be dialogues with the LLM.
	- chatgpt.com/share pages are client-rendered: a plain fetch only returns the page `<title>`, not the conversation. Do NOT rely on a generic web-fetch tool for these links.
	- instead, run `scripts/chatgpt_share_extractor.py` (in this skill's folder) on the share URL, e.g.:
	  `python3 scripts/chatgpt_share_extractor.py <share_url_or_id> --out-dir <scratch_dir>`
	- it prints a one-line JSON summary with `transcript_path` (role-labeled "=== USER ===" / "=== ASSISTANT ===" text) and `messages_path` (structured JSON with role/create_time/text) — read the transcript file to get the actual dialogue.
	- if the script exits non-zero, read the stderr message before falling back to anything else (e.g. it may mean OpenAI changed the share-page format, or the link is a login wall) — do not silently proceed on an empty/garbage extraction.
	- the dialogue should be carefully read under these conditions and the users weaknesses evaluated.
	- cards should especially emphasize areas that the user had trouble with
6. When equations are present, the answer should always show the equation, an intuitive explanation of the equation, and the meaning of every symbol
7. There should always be very simple cards just on defining the meaning of acronyms, but only acronyms directly relevant to the topic
	- acronyms used for examples etc should have the acronyms defined within the question or answer
8. There should always be very simple cards giving a very simple, intuitive understanding of the topic
	- there should be at least one card on "why is this used" basically
	- there should be cards that ask for intuitive explanations of simple parts of the process/topic
	- there should be simple cards asking for a basic, simple explanation of steps if it is a process
	- it's ok for there to be multiple cards asking these questions from different angles
	- at least one card should say roughtly  "explain this topic  to an undergrad new to your lab" - roughly
	- at least one card should say "explain why this matters to someone outside of your field"
9. equations should use ANKI approaches to create easily viewed equations in ANKI
10. There should always be cards that emphaize the limitations of the process or topic: like when things don't work well
11. It's ok to ask if certain equations, in particular, should be included.
12. There should always be a focus on the most important ideas/parts of topic/ parts of process as opposed to including everything.
13. If there are multiple examples in the referenced work, only a subset of these should be used for card generation.
	- the focus of card generation must be the main topic, not example side topics
13. After the csv is generated, always read it back in and review all content for accuracy and clarity

 
