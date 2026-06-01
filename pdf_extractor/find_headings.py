import os
import re

folder = "chapters"
files = sorted([f for f in os.listdir(folder) if f.endswith(".txt")])

# Look at chapter 3 (had good reduction) and chapter 1 (poor reduction)
for filename in files[:4]:
    chapter_num = filename.split("_")[1]
    filepath = os.path.join(folder, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    print(f"\n{'='*60}")
    print(f"CHAPTER {chapter_num} - ALL CAPS LINES (likely headings)")
    print(f"{'='*60}")

    for i, line in enumerate(lines):
        stripped = line.strip()
        # Short-ish ALL CAPS lines = section headings
        if (stripped.isupper() and 
            4 < len(stripped) < 100 and
            not re.match(r'^[\d\s,.\-\(\)$]+$', stripped)):
            print(f"Line {i:6d}: '{stripped}'")