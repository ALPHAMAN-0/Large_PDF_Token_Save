import re
import os
import tiktoken

encoder = tiktoken.get_encoding("cl100k_base")

def count_tokens(text):
    return len(encoder.encode(text))

def optimize_chapter(text):
    lines = text.split('\n')
    cleaned_lines = []
    skip_mode = False

    for line in lines:
        stripped = line.strip()

        # Always skip page markers
        if re.match(r'^--- Page \d+ ---$', stripped):
            continue

        # Always skip standalone page numbers
        if re.match(r'^\d{1,4}$', stripped):
            continue

        # EXIT skip mode when new LEARNING OBJECTIVE starts
        if re.match(r'^LEARNING OBJECTIVE', stripped):
            skip_mode = False
            cleaned_lines.append(line)
            continue

        # ENTER skip mode when exercise/problem codes appear
        # Matches: E2.3 (LO 2,4) / P4.4 (LO 3) / CA1.5 (LO 3) / BE3.2 (LO 1)
        if re.match(r'^(BE|CA|E|P)\d+\.\d+\s*\(LO', stripped, re.IGNORECASE):
            skip_mode = True
            continue

        # While in skip mode skip everything
        if skip_mode:
            continue

        # Skip purely numeric/financial rows
        if re.match(r'^[\d\s,.\-\(\)$€£%R]+$', stripped) and len(stripped) > 2:
            continue

        # Skip multiple choice options (a) (b) (c) (d)
        if re.match(r'^\([a-d]\)\s+', stripped):
            continue

        cleaned_lines.append(line)

    text = '\n'.join(cleaned_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


input_dir  = "chapters"
output_dir = "chapters_optimized"
os.makedirs(output_dir, exist_ok=True)

chapter_files = sorted([f for f in os.listdir(input_dir) if f.endswith(".txt")])

total_before = 0
total_after  = 0

print(f"{'Chapter':<12} {'Before':>10} {'After':>10} {'Saved':>10} {'Reduction':>10}")
print("-" * 58)

for filename in chapter_files:
    match = re.match(r'chapter_(\d+)', filename)
    if not match:
        continue

    chapter_num = int(match.group(1))
    filepath = os.path.join(input_dir, filename)

    with open(filepath, "r", encoding="utf-8") as f:
        original = f.read()

    optimized = optimize_chapter(original)

    before    = count_tokens(original)
    after     = count_tokens(optimized)
    saved     = before - after
    reduction = (saved / before * 100) if before > 0 else 0

    total_before += before
    total_after  += after

    out_path = os.path.join(output_dir, filename)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(optimized)

    print(f"Chapter {chapter_num:<4} {before:>10,} {after:>10,} {saved:>10,} {reduction:>9.1f}%")

total_saved     = total_before - total_after
total_reduction = (total_saved / total_before * 100) if total_before > 0 else 0

print("-" * 58)
print(f"{'TOTAL':<12} {total_before:>10,} {total_after:>10,} {total_saved:>10,} {total_reduction:>9.1f}%")
print(f"\n✅ Saved to /chapters_optimized")