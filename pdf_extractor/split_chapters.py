import re

# Chapter titles from Table of Contents
chapter_titles = {
    1: "Financial Reporting and Accounting Standards",
    2: "Conceptual Framework for Financial Reporting",
    3: "The Accounting Information System",
    4: "Income Statement and Related Information",
    5: "Statement of Financial Position",
    6: "Accounting and the Time Value of Money",
    7: "Cash and Receivables",
    8: "Valuation of Inventories A Cost-Basis Approach",
    9: "Inventories Additional Valuation Issues",
    10: "Acquisition and Disposition of Property Plant",
    11: "Depreciation Impairments and Depletion",
    12: "Intangible Assets",
    13: "Current Liabilities Provisions",
    14: "Non-Current Liabilities",
    15: "Equity",
    16: "Dilutive Securities and Earnings per Share",
    17: "Investments",
    18: "Revenue Recognition",
    19: "Accounting for Income Taxes",
    20: "Accounting for Pensions and Postretirement",
    21: "Accounting for Leases",
    22: "Accounting Changes and Error Analysis",
    23: "Statement of Cash Flows",
    24: "Presentation and Disclosure in Financial"
}

with open("output.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Only look for real chapters after line 1000 (skip TOC)
real_chapter_starts = []
for i, line in enumerate(lines):
    if i < 1000:
        continue
    stripped = line.strip()
    match = re.match(r'^CHAPTER\s+(\d+)$', stripped)
    if match:
        chapter_num = int(match.group(1))
        real_chapter_starts.append((i, chapter_num))

print(f"Found {len(real_chapter_starts)} real chapters:\n")
for line_num, ch_num in real_chapter_starts:
    print(f"  Chapter {ch_num:2d} → starts at line {line_num}")

# Split and save each chapter
import os
os.makedirs("chapters", exist_ok=True)

for idx, (start_line, ch_num) in enumerate(real_chapter_starts):
    # End of chapter = start of next chapter (or end of file)
    if idx + 1 < len(real_chapter_starts):
        end_line = real_chapter_starts[idx + 1][0]
    else:
        end_line = len(lines)

    chapter_content = "".join(lines[start_line:end_line])
    title = chapter_titles.get(ch_num, f"Chapter {ch_num}")
    filename = f"chapters/chapter_{ch_num:02d}_{title[:30].replace(' ', '_')}.txt"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(chapter_content)

    word_count = len(chapter_content.split())
    print(f"✅ Chapter {ch_num:2d} saved → {word_count:,} words")

print(f"\n✅ All chapters saved in /chapters folder!")