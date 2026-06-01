with open("output.txt", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Total lines: {len(lines)}\n")
print("=== FIRST 100 NON-EMPTY LINES ===\n")

count = 0
for i, line in enumerate(lines):
    if line.strip():
        print(f"Line {i:5d}: '{line.strip()[:120]}'")
        count += 1
    if count >= 100:
        break