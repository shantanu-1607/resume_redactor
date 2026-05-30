# redactor.py
import fitz  # PyMuPDF
from pathlib import Path
from typing import List

def extract_entities(path_pdf: str) -> List[str]:
    """
    Placeholder for future extraction logic.
    """
    pass

def redact(path_pdf: str, ktr: List[str] | set) -> None:
    """
    The core engine. Takes a PDF path and strings to redact (ktr).
    Outputs a new PDF with the PII permanently blacked out.
    """
    input_file = Path(path_pdf)
    
    if not input_file.exists():
        print(f"Error: File not found at {path_pdf}")
        return

    output_file = input_file.parent / f"{input_file.stem}_redacted.pdf"

    # Secure the inputs: Drop duplicates, sort longest-first
    unique_keys = set(ktr)
    safe_targets = sorted(unique_keys, key=len, reverse=True)

    try:
        document = fitz.open(str(input_file))
        
        for page_number in range(document.page_count):
            page = document.load_page(page_number)
            boxes_drawn = 0
            
            for target in safe_targets:
                quads = page.search_for(target, quads=True)
                for quad in quads:
                    page.add_redact_annot(quad.rect, fill=(0, 0, 0))
                    boxes_drawn += 1
            
            if boxes_drawn > 0:
                page.apply_redactions()

        document.save(str(output_file), garbage=4, deflate=True)
        print(f"Success! Output PDF generated at: {output_file}")

    except Exception as e:
        print(f"An error occurred during redaction: {e}")
    finally:
        if 'document' in locals():
            document.close()