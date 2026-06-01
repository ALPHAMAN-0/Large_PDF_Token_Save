import fitz

doc = fitz.open("Accounting.doc.pdf")
total_pages = len(doc)

with open("output.txt", "w", encoding="utf-8") as f:
    for page_num in range(total_pages):
        page = doc[page_num]
        text = page.get_text()
        f.write(f"\n--- Page {page_num + 1} ---\n")
        f.write(text)

doc.close()
print(f"Done! Extracted {total_pages} pages to output.txt")