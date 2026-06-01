# Claude Sonnet 4.6 — Chapter Summary Prompt (Ready-to-use)

Purpose
- Use this prompt with Claude Sonnet 4.6 to produce accurate, concise, and well-structured chapter-wise summaries of accounting textbook chapters. It is optimized for clarity, fact preservation, and actionable study notes.

Usage notes
- Send the `System` message once (optional) then the `User` message below with the full chapter text inserted where indicated.
- If your chapter exceeds the model's context window, chunk the text (recommended chunk size: 4–8k tokens) and include the chunk id and source filename. Use retrieval (top-K) with citations where possible.

System message (suggested)
You are an expert accounting instructor and technical writer. Produce clear, precise, and pedagogically-structured summaries. Prioritize accuracy of definitions, recognition/measurement rules, and examples. When uncertain about numbers or dates, mark them as "[VERIFY]".

User message (template)
Below is the full text (or a retrieved chunk) of a single chapter from an accounting textbook. Produce a chapter summary following the specified structured output exactly. If the text appears truncated, note that in the "Notes/Limitations" section.

---
Source: {FILENAME} | Chunk: {CHUNK_ID} (if applicable)

CHAPTER TEXT:
```
{INSERT_CHAPTER_TEXT_HERE}
```
---

OUTPUT SPEC (strictly follow this JSON-like structure; avoid extra commentary):

1) ExecutiveSummary: 1–3 sentences summarizing the chapter's core focus and conclusion.

2) KeyTopics: an ordered list (4–8 items) of the main topics or concepts covered, each 1–2 short sentences.

3) ImportantDefinitions: 6–10 term:definition pairs (short, precise).

4) AccountingTreatments: 3–6 concise bullets detailing primary recognition/measurement/presentation rules and typical journal entries or adjustments.

5) CriticalFormulas/Calculations: list any formulae or TVM calculations used, with variable definitions and a 1-line example if applicable.

6) IllustrativeExample: a short worked example (2–6 lines) showing the concept in practice, include numbers where present in source.

7) Disclosures/PresentationNotes: 2–4 bullets on required disclosures or presentation implications (if discussed).

8) PotentialPitfalls: 3 bullets listing common misunderstandings, accounting traps, or places to verify.

9) NotesLimitations: short note if text was truncated or ambiguous, and whether figures/appendices were missing.

10) Sources: list up to 3 short references to chunk ids or page locations used (e.g., "{FILENAME} chunk 2").

Formatting rules
- Prefer short, declarative sentences. Use plain language suitable for a student or reviewer.
- Return only the specified structured output; do not include additional explanation or preamble.
- Mark uncertain facts with the token `[VERIFY]`.

Parameters (recommended)
- Temperature: 0.0–0.2 (low creativity for factual accuracy).
- Max tokens: set high enough for full structured output (e.g., 800–1500 tokens).
- Response style: neutral, educational, concise.

Batching / multi-chunk strategy
- Summarize each chunk separately using the same prompt, include `Chunk` field. Then run a second-pass synthesis prompt that ingests all chunk summaries and produces a single consolidated chapter summary (follow the same OUTPUT SPEC, prefer synthesis over concatenation).

Example short prompt (single chunk)
"Summarize the following chapter chunk using the specified OUTPUT SPEC. Provide concise, factual, student-ready content. Chapter text: {CHAPTER_TEXT}"

Verification checklist (post-generation)
- Spot-check definitions against the chapter text.
- Confirm numerical examples and formula variables.
- If high accuracy required, run an extraction pass for citations and exact wording.

End of prompt
