# 1. Import the dictionary of jobs
from config import PDF_JOBS, DOCX_JOBS

# 2. Import the engines
from redactor import redact
from doc_converter import redact_docx

def function1(keywords, path_pdf):
    """
    Controller function requested by the manager.
    """
    print(f"\n--- Processing: {path_pdf} ---")
    redact(path_pdf, ktr=keywords)

if __name__ == "__main__":

    for pdf_path, keywords_set in PDF_JOBS.items():
        actual_path = f"templates/{pdf_path}"
        function1(keywords=keywords_set, path_pdf=actual_path)

    for docx_path, keywords_set in DOCX_JOBS.items():
        actual_path = f"templates/{docx_path}"
        print(f"\n--- Processing: {actual_path} ---")
        redact_docx(actual_path, ktr=keywords_set)