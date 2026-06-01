#!/usr/bin/env python3
"""
Generate structured chapter summaries using Claude API, then render to PDF.

Usage:
    python generate_summaries_pdf.py              # all 24 chapters
    python generate_summaries_pdf.py --chapters 1          # chapter 1 only
    python generate_summaries_pdf.py --chapters 1,3,5      # specific chapters
    python generate_summaries_pdf.py --pdf-only            # render cached summaries only
"""

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import tiktoken
import anthropic
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

# ─── Unicode-capable TTF fonts ────────────────────────────────────────────────
_SUPP = "/System/Library/Fonts/Supplemental"
pdfmetrics.registerFont(TTFont("Arial",           f"{_SUPP}/Arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold",      f"{_SUPP}/Arial Bold.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Italic",    f"{_SUPP}/Arial Italic.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BoldItalic",f"{_SUPP}/Arial Bold Italic.ttf"))
pdfmetrics.registerFont(TTFont("CourierNew",      f"{_SUPP}/Courier New.ttf"))
addMapping("Arial", 0, 0, "Arial")
addMapping("Arial", 1, 0, "Arial-Bold")
addMapping("Arial", 0, 1, "Arial-Italic")
addMapping("Arial", 1, 1, "Arial-BoldItalic")

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
CHAPTER_DIR  = SCRIPT_DIR / "chapters_optimized"
SUMMARIES_DIR = SCRIPT_DIR / "summaries"
OUTPUT_PDF   = SCRIPT_DIR / "Accounting_Chapter_Summaries.pdf"

# Full titles from the original Table of Contents
CHAPTER_TITLES = {
    1:  "Financial Reporting and Accounting Standards",
    2:  "Conceptual Framework for Financial Reporting",
    3:  "The Accounting Information System",
    4:  "Income Statement and Related Information",
    5:  "Statement of Financial Position",
    6:  "Accounting and the Time Value of Money",
    7:  "Cash and Receivables",
    8:  "Valuation of Inventories: A Cost-Basis Approach",
    9:  "Inventories: Additional Valuation Issues",
    10: "Acquisition and Disposition of Property, Plant & Equipment",
    11: "Depreciation, Impairments and Depletion",
    12: "Intangible Assets",
    13: "Current Liabilities and Provisions",
    14: "Non-Current Liabilities",
    15: "Equity",
    16: "Dilutive Securities and Earnings per Share",
    17: "Investments",
    18: "Revenue Recognition",
    19: "Accounting for Income Taxes",
    20: "Accounting for Pensions and Postretirement Benefits",
    21: "Accounting for Leases",
    22: "Accounting Changes and Error Analysis",
    23: "Statement of Cash Flows",
    24: "Presentation and Disclosure in Financial Reporting",
}

# ─── API settings ─────────────────────────────────────────────────────────────
MODEL           = "claude-sonnet-4-6"
MAX_CHUNK_TOKENS = 6000
MAX_RETRIES     = 3

SYSTEM_PROMPT = (
    "You are an expert accounting instructor and technical writer. "
    "Produce clear, precise, and pedagogically-structured summaries. "
    "Prioritize accuracy of definitions, recognition/measurement rules, and examples. "
    "When uncertain about numbers or dates, mark them with [VERIFY]."
)

JSON_SCHEMA = """{
  "executiveSummary": "1-3 sentences on the chapter's core focus and conclusion",
  "keyTopics": ["ordered list of 4-8 items, each 1-2 sentences"],
  "importantDefinitions": {"Term": "Definition (6-10 pairs)"},
  "accountingTreatments": ["3-6 bullet strings on recognition/measurement/journal entries"],
  "criticalFormulas": ["formulae with variable definitions and a 1-line example each"],
  "illustrativeExample": "2-6 line worked example with numbers from source",
  "disclosurePresentationNotes": ["2-4 bullet strings on required disclosures"],
  "potentialPitfalls": ["exactly 3 bullet strings on common misunderstandings"],
  "notesLimitations": "note if text was truncated or ambiguous",
  "sources": ["up to 3 short chunk/page references"]
}"""

# ─── Tokenizer ────────────────────────────────────────────────────────────────
_encoder = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(_encoder.encode(text))

def chunk_text(text, max_tokens=MAX_CHUNK_TOKENS):
    paragraphs = re.split(r'\n{2,}', text)
    chunks, current, current_tokens = [], [], 0
    for para in paragraphs:
        t = count_tokens(para)
        if current_tokens + t > max_tokens and current:
            chunks.append('\n\n'.join(current))
            current, current_tokens = [para], t
        else:
            current.append(para)
            current_tokens += t
    if current:
        chunks.append('\n\n'.join(current))
    return chunks

# ─── Claude API ───────────────────────────────────────────────────────────────
def _user_prompt(chapter_text, filename, chunk_id=None):
    chunk_label = f"Chunk: {chunk_id}" if chunk_id else "Single chunk"
    return (
        "Below is text from an accounting textbook chapter. "
        "Return ONLY a valid JSON object matching the schema — no markdown fences, no preamble.\n\n"
        f"Source: {filename} | {chunk_label}\n\n"
        f"CHAPTER TEXT:\n```\n{chapter_text}\n```\n\n"
        f"JSON SCHEMA:\n{JSON_SCHEMA}\n\n"
        "Rules: short declarative sentences; mark uncertain facts with [VERIFY]; return ONLY valid JSON."
    )

_SYNTHESIS_TEMPLATE = (
    "Synthesize {n} partial summaries of consecutive chunks from the SAME chapter into a single "
    "consolidated summary. Prefer synthesis over concatenation — merge related items, remove redundancy. "
    "Return ONLY a valid JSON object matching the schema.\n\n"
    "PARTIAL SUMMARIES:\n{summaries}\n\nJSON SCHEMA:\n{schema}"
)

def _call_api(client, prompt):
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                temperature=0,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return resp.content[0].text
        except Exception as exc:
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                print(f"    [retry {attempt+1}] {exc} — waiting {wait}s…")
                time.sleep(wait)
            else:
                raise

def _parse_json(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text.strip())
    return json.loads(text)

def summarize_chapter(client, filepath):
    cache = SUMMARIES_DIR / (filepath.stem + ".json")
    if cache.exists():
        try:
            data = json.loads(cache.read_text())
            print(f"  [cached]  {filepath.name}")
            return data
        except json.JSONDecodeError:
            pass

    text   = filepath.read_text(encoding="utf-8")
    tokens = count_tokens(text)
    print(f"  {filepath.name} — {tokens:,} tokens", end="", flush=True)

    if tokens <= MAX_CHUNK_TOKENS:
        print(" → 1 chunk", flush=True)
        data = _parse_json(_call_api(client, _user_prompt(text, filepath.name)))
    else:
        chunks = chunk_text(text)
        print(f" → {len(chunks)} chunks", flush=True)
        partials = []
        for i, chunk in enumerate(chunks, 1):
            print(f"    chunk {i}/{len(chunks)}…", end="", flush=True)
            partials.append(_parse_json(_call_api(client, _user_prompt(chunk, filepath.name, i))))
            print(" done")
        print(f"    synthesising…", end="", flush=True)
        synth = _SYNTHESIS_TEMPLATE.format(
            n=len(partials),
            summaries=json.dumps(partials, indent=2),
            schema=JSON_SCHEMA,
        )
        data = _parse_json(_call_api(client, synth))
        print(" done")

    SUMMARIES_DIR.mkdir(exist_ok=True)
    cache.write_text(json.dumps(data, indent=2))
    return data

# ─── PDF helpers ──────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
MARGIN = 2.0 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


def _esc(text):
    if not isinstance(text, str):
        text = str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _make_styles():
    def ps(name, parent="Normal", **kw):
        s = ParagraphStyle(name, parent=getSampleStyleSheet()[parent], **kw)
        # Override base font to Arial so all Unicode chars render correctly
        if "fontName" not in kw:
            s.fontName = "Arial"
        return s

    return {
        "cover_title": ps("CoverTitle", "Title",
            fontName="Arial-Bold",
            fontSize=30, leading=36, spaceAfter=10,
            textColor=colors.HexColor("#1a2744"), alignment=TA_CENTER),
        "cover_sub": ps("CoverSub",
            fontName="Arial",
            fontSize=15, leading=20, spaceAfter=6,
            textColor=colors.HexColor("#4a5568"), alignment=TA_CENTER),
        "cover_date": ps("CoverDate",
            fontName="Arial",
            fontSize=10, textColor=colors.grey, alignment=TA_CENTER),
        "toc_title": ps("TOCTitle", "Heading1",
            fontName="Arial-Bold",
            fontSize=18, textColor=colors.HexColor("#1a2744"), spaceAfter=10),
        "ch_heading": ps("ChapterHeading", "Heading1",
            fontName="Arial-Bold",
            fontSize=20, leading=26, spaceBefore=0, spaceAfter=4,
            textColor=colors.HexColor("#1a2744")),
        "sec_heading": ps("SectionHeading", "Heading2",
            fontName="Arial-Bold",
            fontSize=12, leading=16, spaceBefore=8, spaceAfter=3,
            textColor=colors.HexColor("#2d4a8a")),
        "body": ps("Body",
            fontName="Arial",
            fontSize=10, leading=15, spaceAfter=5, alignment=TA_JUSTIFY),
        "bullet": ps("Bullet",
            fontName="Arial",
            fontSize=10, leading=15, leftIndent=16, spaceAfter=2),
        "example": ps("Example",
            fontName="Arial",
            fontSize=9.5, leading=14, leftIndent=20, rightIndent=8,
            backColor=colors.HexColor("#f4f7fc"), spaceAfter=4, spaceBefore=2),
        "formula": ps("Formula",
            fontName="CourierNew",
            fontSize=9.5, leading=14, leftIndent=20,
            spaceAfter=3, spaceBefore=2),
        "italic_note": ps("ItalicNote",
            fontName="Arial-Italic",
            fontSize=9, leading=13, textColor=colors.grey, spaceAfter=3),
    }


class _SummaryDoc(BaseDocTemplate):
    def __init__(self, filename, **kw):
        super().__init__(filename, **kw)
        self._current_chapter = ""
        self.toc = TableOfContents()
        self.toc.levelStyles = [
            ParagraphStyle("TOCLevel0",
                fontName="Arial",
                fontSize=11, leading=17, leftIndent=0, firstLineIndent=0,
                textColor=colors.HexColor("#1a2744")),
        ]

    def afterFlowable(self, flowable):
        if isinstance(flowable, Paragraph) and flowable.style.name == "ChapterHeading":
            text = flowable.getPlainText()
            self._current_chapter = text
            self.notify("TOCEntry", (0, text, self.page))


def _draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Arial", 8)
    canvas.setFillColor(colors.HexColor("#888888"))
    canvas.drawString(MARGIN, 1.1 * cm, doc._current_chapter)
    canvas.drawRightString(PAGE_W - MARGIN, 1.1 * cm, str(canvas.getPageNumber()))
    canvas.restoreState()


def build_pdf(chapter_data, output_path):
    S = _make_styles()
    doc = _SummaryDoc(
        str(output_path),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN,  bottomMargin=2.2 * cm,
    )
    frame = Frame(MARGIN, 2.2 * cm, CONTENT_W, PAGE_H - MARGIN - 2.2 * cm)
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_draw_footer)])

    story = []

    # Cover ───────────────────────────────────────────────────────────────────
    story += [
        Spacer(1, 5 * cm),
        Paragraph("Accounting Textbook", S["cover_title"]),
        Paragraph("Chapter Summaries", S["cover_sub"]),
        Spacer(1, 0.4 * cm),
        HRFlowable(width="55%", thickness=2, color=colors.HexColor("#2d4a8a"), hAlign="CENTER"),
        Spacer(1, 0.4 * cm),
        Paragraph(f"{len(chapter_data)} Chapters  ·  Generated with Claude Sonnet 4.6", S["cover_date"]),
        PageBreak(),
    ]

    # Table of Contents ───────────────────────────────────────────────────────
    story += [
        Paragraph("Table of Contents", S["toc_title"]),
        doc.toc,
        PageBreak(),
    ]

    # Chapters ────────────────────────────────────────────────────────────────
    for ch_num, ch_title, summary in chapter_data:
        story.append(Paragraph(_esc(f"Chapter {ch_num}: {ch_title}"), S["ch_heading"]))
        story.append(HRFlowable(width="100%", thickness=1,
                                color=colors.HexColor("#2d4a8a"), spaceAfter=6))

        def sec(label, items_fn):
            story.append(Paragraph(label, S["sec_heading"]))
            items_fn()
            story.append(Spacer(1, 0.15 * cm))

        # Executive Summary
        def _exec(s=summary):
            story.append(Paragraph(_esc(s.get("executiveSummary", "")), S["body"]))
        sec("Executive Summary", _exec)

        # Key Topics
        def _topics(s=summary):
            for i, t in enumerate(s.get("keyTopics", []), 1):
                story.append(Paragraph(f"{i}. {_esc(t)}", S["bullet"]))
        sec("Key Topics", _topics)

        # Important Definitions
        def _defs(s=summary):
            raw = s.get("importantDefinitions", {})
            if isinstance(raw, list):
                pairs = []
                for item in raw:
                    if ":" in str(item):
                        k, _, v = str(item).partition(":")
                        pairs.append((k.strip(), v.strip()))
                    else:
                        pairs.append((str(item), ""))
            else:
                pairs = list(raw.items())
            if not pairs:
                return

            # Paragraph styles for table cells — controls word-wrap inside columns
            _hdr = ParagraphStyle("TblHdr", fontName="Arial-Bold",
                                  fontSize=9.5, leading=14, textColor=colors.white)
            _term = ParagraphStyle("TblTerm", fontName="Arial-Bold",
                                   fontSize=9.5, leading=14)
            _def  = ParagraphStyle("TblDef",  fontName="Arial",
                                   fontSize=9.5, leading=14)

            col_term = 4.5 * cm
            col_def  = CONTENT_W - col_term - 0.1 * cm
            data = [
                [Paragraph("Term", _hdr), Paragraph("Definition", _hdr)],
            ] + [
                [Paragraph(_esc(k), _term), Paragraph(_esc(v), _def)]
                for k, v in pairs
            ]
            tbl = Table(data, colWidths=[col_term, col_def], repeatRows=1)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#2d4a8a")),
                ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f0f4ff"), colors.white]),
                ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#c0c8d8")),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ]))
            story.append(tbl)
        sec("Important Definitions", _defs)

        # Accounting Treatments
        def _treatments(s=summary):
            for item in s.get("accountingTreatments", []):
                story.append(Paragraph(f"&#x2022; {_esc(item)}", S["bullet"]))
        sec("Accounting Treatments", _treatments)

        # Critical Formulas
        formulas = summary.get("criticalFormulas", [])
        if formulas:
            def _formulas(s=summary):
                for f in s.get("criticalFormulas", []):
                    story.append(Paragraph(_esc(f), S["formula"]))
            sec("Critical Formulas / Calculations", _formulas)

        # Illustrative Example
        example = summary.get("illustrativeExample", "")
        if example and example.strip():
            def _example(s=summary):
                story.append(Paragraph(_esc(s.get("illustrativeExample", "")), S["example"]))
            sec("Illustrative Example", _example)

        # Disclosures
        def _disclosures(s=summary):
            for item in s.get("disclosurePresentationNotes", []):
                story.append(Paragraph(f"&#x2022; {_esc(item)}", S["bullet"]))
        sec("Disclosures / Presentation Notes", _disclosures)

        # Potential Pitfalls
        def _pitfalls(s=summary):
            for item in s.get("potentialPitfalls", []):
                story.append(Paragraph(f"&#x26A0; {_esc(item)}", S["bullet"]))
        sec("Potential Pitfalls", _pitfalls)

        # Notes / Limitations
        notes = summary.get("notesLimitations", "")
        if notes and notes.strip() and notes.strip().lower() not in ("none", "n/a", ""):
            story.append(Paragraph(f"Notes: {_esc(notes)}", S["italic_note"]))

        story.append(PageBreak())

    doc.multiBuild(story)
    print(f"\nPDF saved → {output_path}")


# ─── CLI ──────────────────────────────────────────────────────────────────────
def _parse_args():
    p = argparse.ArgumentParser(description="Summarise accounting chapters and render to PDF.")
    p.add_argument("--chapters", default="all",
                   help='"all", a single number like "5", or comma-list "1,3,5"')
    p.add_argument("--pdf-only", action="store_true",
                   help="Skip API calls; build PDF from cached summaries only")
    return p.parse_args()


def _chapter_files(chapter_filter):
    files = sorted(CHAPTER_DIR.glob("chapter_*.txt"))
    if chapter_filter == "all":
        return files
    nums = {int(n.strip()) for n in chapter_filter.split(",")}
    return [f for f in files if (m := re.match(r"chapter_(\d+)", f.name)) and int(m.group(1)) in nums]


def main():
    args = _parse_args()
    SUMMARIES_DIR.mkdir(exist_ok=True)

    files = _chapter_files(args.chapters)
    if not files:
        sys.exit(f"No chapter files found for: --chapters {args.chapters}")

    client = None if args.pdf_only else anthropic.Anthropic()

    chapter_data = []
    for fp in files:
        m = re.match(r"chapter_(\d+)", fp.name)
        ch_num = int(m.group(1)) if m else 0
        ch_title = CHAPTER_TITLES.get(ch_num, fp.stem.replace("_", " "))

        if args.pdf_only:
            cache = SUMMARIES_DIR / (fp.stem + ".json")
            if not cache.exists():
                print(f"  [skip — no cache] {fp.name}")
                continue
            summary = json.loads(cache.read_text())
            print(f"  [loaded] {fp.name}")
        else:
            print(f"\nChapter {ch_num}: {ch_title}")
            summary = summarize_chapter(client, fp)

        chapter_data.append((ch_num, ch_title, summary))

    if not chapter_data:
        sys.exit("No summaries available to render.")

    print(f"\nBuilding PDF — {len(chapter_data)} chapter(s)…")
    build_pdf(chapter_data, OUTPUT_PDF)


if __name__ == "__main__":
    main()
