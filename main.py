# 1. Import the dictionary of jobs
from config import PDF_JOBS

# 2. Import the engine
from redactor import redact

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