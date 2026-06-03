# doc_converter.py
import subprocess
import shutil
from pathlib import Path
from typing import List

from redactor import redact


def _find_libreoffice() -> str:
    """Return the LibreOffice binary path, or raise if not installed."""
    for candidate in [
        'soffice',
        'libreoffice',
        '/Applications/LibreOffice.app/Contents/MacOS/soffice',
    ]:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    raise FileNotFoundError(
        "LibreOffice not found. Install it with: brew install --cask libreoffice"
    )


def redact_docx(path_docx: str, ktr: List[str] | set) -> None:
    """
    Converts a .docx file to PDF using LibreOffice headless (preserves formatting),
    then runs the existing PDF redactor on it.
    The intermediate (unredacted) PDF is deleted after redaction is complete.
    """
    input_file = Path(path_docx)

    if not input_file.exists():
        print(f"Error: File not found at {path_docx}")
        return

    if input_file.suffix.lower() not in (".docx", ".doc"):
        print(f"Error: Expected a .doc or .docx file, got {input_file.suffix}")
        return

    temp_pdf = input_file.with_suffix(".pdf")

    print(f"Converting {input_file.name} → {temp_pdf.name} ...")

    # Step 1: docx → PDF using LibreOffice headless (no GUI, preserves full formatting)
    soffice = _find_libreoffice()
    result = subprocess.run(
        [soffice, '--headless', '--convert-to', 'pdf', '--outdir', str(input_file.parent), str(input_file)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"LibreOffice conversion failed:\n{result.stderr}")
        return

    # Step 2: hand off to the existing PDF redactor
    redact(str(temp_pdf), ktr)

    # Step 3: delete the intermediate unredacted PDF so only the redacted copy remains
    if temp_pdf.exists():
        temp_pdf.unlink()
        print(f"Removed intermediate PDF: {temp_pdf.name}")


if __name__ == "__main__":
    from config import DOCX_JOBS

    for docx_path, keywords_set in DOCX_JOBS.items():
        actual_path = f"templates/{docx_path}"
        print(f"\n--- Processing: {actual_path} ---")
        redact_docx(actual_path, ktr=keywords_set)
