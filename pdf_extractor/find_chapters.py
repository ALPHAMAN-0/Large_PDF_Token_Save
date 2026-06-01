import re

with open("output.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== ALL CHAPTERS FOUND ===\n")
for i, line in enumerate(lines):
    stripped = line.strip()
    if re.match(r'^CHAPTER\s+\d+', stripped):
        print(f"Line {i:6d}: '{stripped}'")