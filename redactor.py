# pymupdf is basically used to render, read, manipulate pdfs while pdfplumber is used for
#extracting structured text and tables from pdfs

# blocks = page.get_text("blocks") this part extracts the coordinates of the specified text and will black them out

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable

import fitz  # PyMuPDF
import pdfplumber
import spacy    #spacy converts raw text into structured linguistic objects
from spacy.language import Language

## spacy basically extracts the words and tries to form something meaningful by identifying nouns, verbs, subject
# basically it is built on the basic grammer of that language


SUPPORTED_ENTITIES = {"NAME", "EMAIL", "PHONE"}
SPACY_MODEL = "en_core_web_sm"

# Practical email matcher for ordinary resume text. It intentionally returns the
# exact matched string so PyMuPDF can later search for the same value.
EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)

# Phone numbers vary widely across resumes. This pattern accepts optional
# country codes, punctuation, spaces, and common parenthesized area codes while
# requiring enough digits to avoid most dates and short IDs.
PHONE_CANDIDATE_PATTERN = re.compile(
    r"""
    (?<!\w)
    (?:\+?\d{1,3}[\s.\-]*)?
    (?:\(?\d{2,5}\)?[\s.\-]*){1,4}
    \d{2,5}
    (?!\w)
    """,
    re.VERBOSE,
)

NAME_TOKEN_PATTERN = re.compile(r"^[A-Z][A-Za-z'.-]*$")

# Conservative deny-list for terms that en_core_web_sm commonly mislabels as
# PERSON in technical resumes. These are not used for coordinate mapping; they
# only prevent false-positive discovery strings from reaching search_for().
NON_NAME_TERMS = {
    "api",
    "algorithms",
    "bangalore",
    "b.tech",
    "bit",
    "c",
    "c++",
    "css",
    "codeforces",
    "data",
    "development",
    "devices",
    "digital",
    "electrical",
    "electronics",
    "engineering",
    "education",
    "analyst",
    "banking",
    "developer",
    "designer",
    "flask",
    "fpga",
    "full",
    "financial",
    "git",
    "github",
    "graphic",
    "html",
    "human",
    "investment",
    "javascript",
    "leetcode",
    "machine",
    "manager",
    "matplotlib",
    "max",
    "mesra",
    "m.tech",
    "mysql",
    "numpy",
    "oop",
    "pandas",
    "playbook",
    "pps",
    "professional",
    "python",
    "rating",
    "ransomware",
    "research",
    "resources",
    "rest",
    "scikit-learn",
    "seaborn",
    "software",
    "sql",
    "senior",
    "stack",
    "stl",
    "streamlit",
    "summary",
    "technology",
    "vscode",
    "vlsi",
}

SECTION_TERMS = {
    "achievement",
    "achievements",
    "certificate",
    "certificates",
    "contact",
    "course",
    "courses",
    "education",
    "experience",
    "project",
    "projects",
    "publication",
    "publications",
    "professional",
    "research",
    "skills",
    "summary",
    "technical",
}

# error handling
class RedactionError(RuntimeError):
    """Raised when a redaction job cannot be completed safely."""
    # makes debugging easier
    


#validates user input
def normalize_entity_flags(entities_to_redact: Iterable[str]) -> set[str]:
    """Validate and normalize requested entity flags."""
    
    ## it loops through every item in entities_to_redact and entity.strip().upper() removes any leading or trailig spaces
    
    requested = {entity.strip().upper() for entity in entities_to_redact if entity}
    unsupported = requested - SUPPORTED_ENTITIES
    
    # unsuported checks if the user has asked for any unknow entity to be removed like address
    #then the code does not know how to redact that unsupported and raises redaction error
    

    if unsupported:
        supported = ", ".join(sorted(SUPPORTED_ENTITIES))
        bad_values = ", ".join(sorted(unsupported))
        raise RedactionError(
            f"Unsupported entity flag(s): {bad_values}. Supported flags: {supported}."
        )

# if the resulting requested set is empty this gives error for that case
    if not requested:
        raise RedactionError("No entity flags were provided.")

    return requested

# loading the NLP model
def load_spacy_model() -> Language:
    """Load the required spaCy model with a clear remediation message."""
    try:
        return spacy.load(SPACY_MODEL)
    except OSError as exc:
        raise RedactionError(
            f"spaCy model '{SPACY_MODEL}' is not installed. "
            f"Install it with: python -m spacy download {SPACY_MODEL}"
        ) from exc

#extracting text with pymupdf
#first we define a func which takes pymupdf doc and return single string of text
def extract_pdf_text_with_fitz(document: fitz.Document) -> str:
    """Extract raw text from every page with PyMuPDF."""
    pages: list[str] = []

    for page_number in range(document.page_count): #loops over all pages in pdf
        page = document.load_page(page_number)
        pages.append(page.get_text("text")) #extracts all the raw text from a page to new string to the pages list

    return "\n".join(pages) #this takes all the list of string from each pages and joins them

# now uses pdf plumber 
def extract_pdf_text_with_pdfplumber(pdf_path: Path) -> str:
    """Extract raw text with pdfplumber, which can preserve some layouts better."""
    pages: list[str] = []

    with pdfplumber.open(str(pdf_path)) as pdf: #this part ensures that if pdf file is automatically closed 
        for page in pdf.pages:
            pages.append(page.extract_text() or "") ## or "" is exception handling if no text then
 
    return "\n".join(pages)

# this func defines how to get the text
def extract_discovery_text(pdf_path: Path, document: fitz.Document) -> str:
    """Prefer pdfplumber for discovery text, then fall back to PyMuPDF."""
    try:
        text = extract_pdf_text_with_pdfplumber(pdf_path)
        if text.strip(): #checks if pdf plumber has returned anything
            return text
    except Exception as exc:
        print(f"Warning: pdfplumber extraction failed, falling back to PyMuPDF: {exc}")

    return extract_pdf_text_with_fitz(document) #if pdfplumber fails then use pymupdf

#this part discovers emails
def discover_emails(text: str) -> set[str]:
    """Discover exact email strings from raw text."""
    # this grabs the email using the pattern func and removes any white spaces if there is
    return {match.group(0).strip() for match in EMAIL_PATTERN.finditer(text)}


def discover_phones(text: str) -> set[str]:
    """Discover exact phone strings from raw text, filtering weak candidates."""
    phones: set[str] = set()

    for match in PHONE_CANDIDATE_PATTERN.finditer(text):
        candidate = match.group(0).strip()
        #this part indetifies the phone no and removes any white spaces
        digit_count = sum(character.isdigit() for character in candidate)

#this checks if the number extracted is a valid phone or not by comparing its length
        if 10 <= digit_count <= 15:
            phones.add(candidate)

    return phones


# this part does the offset mapping
#this part calculates the exact start char and end points of every line
## Simply splits the massive text block into individual lines, strips them, and removes empty lines. This is used later to quickly check the first 20 lines of a document for names.

def clean_text_lines(text: str) -> list[str]:
    """Return non-empty raw text lines without changing their searchable text."""
    return [line.strip() for line in text.splitlines() if line.strip()]

# this returns the character ranges for each non empty text line
def line_ranges(text: str) -> list[tuple[int, int, str]]:
    """Return character ranges for each non-empty raw text line."""
    ranges: list[tuple[int, int, str]] = []
    offset = 0

    for line in text.splitlines(keepends=True): ## this part split the huge texts into sep lines
        line_without_break = line.rstrip("\r\n")  ## this removes /n and/r only from end
        stripped = line_without_break.strip() # this removes the spaces 
        start = offset + line_without_break.find(stripped) if stripped else offset ## this part combines the offset and spacing and gives the final starting pos of text
        end = start + len(stripped) # this gives the ending position

        if stripped:  ## ignore empty lines
            ranges.append((start, end, stripped))

        offset += len(line) ## moves the document cursor forward

    return ranges

##

def line_for_entity(entity_start: int, entity_text: str, ranges: list[tuple[int, int, str]]) -> str:
    """Find the original extracted line where a spaCy entity begins."""
    for start, end, line in ranges:
        if start <= entity_start <= end:
            return line

    return " ".join(entity_text.split()) ## if the entity is not found then it defaults to
## returning the cleaned up entity text 


## this detects if the names are possible or not to avoid false positives
def is_plausible_name_line(line: str) -> bool:
    """Reject obvious non-name PERSON false positives from technical resumes."""
    if any(character.isdigit() for character in line): ## finds if any no is in name then return false
        return False

    ## this part checks for symbols
    if any(symbol in line for symbol in ("@", ":", "/", "\\", "+", "#", "§")):
        return False
    ## checks how many words a name contains , if falls outside the range then false
    words = line.split()
    if not 2 <= len(words) <= 4:
        return False

# this removes commas,brackets and puts everything in a set and checks any overlap between 2 sets
    normalized_words = {word.strip(".,()[]{}").lower() for word in words}
    if normalized_words & NON_NAME_TERMS:
        return False

## if no match then returns the name
    return all(NAME_TOKEN_PATTERN.match(word) for word in words)

## this handles when name,email are in the same line
def leading_name_prefix(line: str) -> str | None:
    """Return a plausible leading name from a line that also contains contacts."""
    
    # searches for symbols or phone no or word linkedin if present returns none
    contact_mixed_line = any(marker in line.lower() for marker in ("@", "+", "cid:", "linkedin"))
    if not contact_mixed_line:
        return None

# then we iterate through each for individually to find them while cleaning them using strip
    name_words: list[str] = []

    for word in line.split():
        cleaned = word.strip(".,()[]{}")
        if not NAME_TOKEN_PATTERN.match(cleaned):
            break
        if cleaned.lower() in NON_NAME_TERMS:
            break
        name_words.append(cleaned)

    candidate = " ".join(name_words) ## join the words back if we got any name in the above loop
    
    return candidate if is_plausible_name_line(candidate) else None


## this handles the exceptional case where the ai cant find the name
def discover_header_name_candidates(text: str) -> set[str]:
    """
    Find likely name lines near the beginning of the resume.

    This is a fallback for cases where small spaCy models miss stylized names.
    It still returns exact text strings and leaves all coordinate work to fitz.
    """
    candidates: set[str] = set()
    lines = clean_text_lines(text)

    for line in lines[:20]: ## checks only for the first 20 lines of the resume as we are scanning near the header
        normalized_words = {
            word.strip(".,()[]{}").lower()
            for word in line.split()
        }
        
        # this checks if the normalized words sets has any common with sections terms then break
        if normalized_words & SECTION_TERMS:
            break

        prefix = leading_name_prefix(line)
        if prefix:
            candidates.add(prefix)
        elif is_plausible_name_line(line):
            candidates.add(line)

    return candidates


# uses nlp to detect names

def discover_names(text: str, nlp: Language) -> set[str]:
    """Discover exact human-name strings from spaCy PERSON entities."""
    doc = nlp(text)
    ranges = line_ranges(text)
    names: set[str] = set()

    for entity in doc.ents:
        if entity.label_ != "PERSON" or not entity.text.strip(): ## ai detects it as ORG ya city
            continue

        candidate = line_for_entity(entity.start_char, entity.text.strip(), ranges)

        if is_plausible_name_line(candidate): ## checks if the candidate is valid then adds it to set
            names.add(candidate)

    names.update(discover_header_name_candidates(text)) ## also gives the header guesses to ai comibing the list
    return names

## creating url blockers

def name_search_variants(names: set[str]) -> set[str]:
    """Create exact searchable variants for names embedded in profile URLs."""
    variants: set[str] = set()

    for name in names:
        words = name.split()
        if len(words) >= 2:
            variants.add("-".join(word.lower() for word in words))

    return variants

# this function  looks at what the user wants to redact and dispatches the specific tools we built earlier to find them.
def discover_redaction_targets(
    text: str,
    requested_entities: set[str],
    nlp: Language | None,
) -> dict[str, set[str]]:
    """Run all requested discovery methods and return exact strings by entity."""
    targets: dict[str, set[str]] = {}

    if "EMAIL" in requested_entities:
        targets["EMAIL"] = discover_emails(text)

    if "PHONE" in requested_entities:
        targets["PHONE"] = discover_phones(text)

    if "NAME" in requested_entities:
        if nlp is None:
            raise RedactionError("NAME redaction requires a loaded spaCy model.")
        names = discover_names(text, nlp)
        targets["NAME"] = names | name_search_variants(names)

    return targets


def unique_targets(targets_by_entity: dict[str, set[str]]) -> list[str]:
    """Flatten discovered strings into a stable, longest-first search list."""
    all_targets = {
        target
        for targets in targets_by_entity.values()
        for target in targets
        if target
    }

    # Searching longer strings first helps when names or phones overlap.
    return sorted(all_targets, key=lambda value: (-len(value), value.lower()))


def apply_pdf_redactions(document: fitz.Document, targets: list[str]) -> int:
    """
    Apply black-box redactions for every discovered target.

    This intentionally uses PyMuPDF's text search instead of custom geometry.
    """
    annotation_count = 0

    for page_number in range(document.page_count):
        page = document.load_page(page_number)
        page_annotation_count = 0

        for target in targets:
            quads = page.search_for(target, quads=True)

            for quad in quads:
                page.add_redact_annot(quad.rect, fill=(0, 0, 0))
                annotation_count += 1
                page_annotation_count += 1

        if page_annotation_count:
            page.apply_redactions()

    return annotation_count


def print_discovery_report(targets_by_entity: dict[str, set[str]]) -> None:
    """Print clean terminal output describing exactly what was found."""
    print("Identified strings for redaction:")

    for entity in sorted(targets_by_entity):
        targets = sorted(targets_by_entity[entity], key=str.lower)
        print(f"  {entity}: {len(targets)}")

        for target in targets:
            print(f"    - {target}")


def redact_resume(pdf_path: str, output_path: str, entities_to_redact: list[str]):
    """
    Redact requested PII entities from a digital resume PDF.

    Args:
        pdf_path: Path to the input PDF.
        output_path: Path where the redacted PDF should be saved.
        entities_to_redact: Flags such as ["NAME", "EMAIL", "PHONE"].
    """
    requested_entities = normalize_entity_flags(entities_to_redact)
    input_file = Path(pdf_path)
    output_file = Path(output_path)

    if not input_file.exists():
        raise RedactionError(f"Input PDF does not exist: {input_file}")

    if input_file.resolve() == output_file.resolve():
        raise RedactionError("Input and output paths must be different.")

    nlp = load_spacy_model() if "NAME" in requested_entities else None

    try:
        document = fitz.open(str(input_file))
    except Exception as exc:
        raise RedactionError(f"Failed to load PDF '{input_file}': {exc}") from exc

    try:
        if document.is_encrypted:
            raise RedactionError("Encrypted PDFs are not supported by this script.")

        text = extract_discovery_text(input_file, document)
        targets_by_entity = discover_redaction_targets(text, requested_entities, nlp)
        targets = unique_targets(targets_by_entity)

        print_discovery_report(targets_by_entity)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if not targets:
            print("Black boxes applied: 0")
            document.save(str(output_file), garbage=4, deflate=True)
            print(f"Saved redacted PDF to: {output_file}")
            return

        black_boxes_applied = apply_pdf_redactions(document, targets)

        document.save(str(output_file), garbage=4, deflate=True)

        print(f"Black boxes applied: {black_boxes_applied}")
        print(f"Saved redacted PDF to: {output_file}")
    except RedactionError:
        raise
    except Exception as exc:
        raise RedactionError(f"Redaction failed: {exc}") from exc
    finally:
        document.close()


def default_output_path(input_path: Path, output_dir: Path | None = None) -> Path:
    """Build a safe default output path beside the input or inside output_dir."""
    base_dir = output_dir if output_dir is not None else input_path.parent
    return base_dir / f"{input_path.stem}_redacted.pdf"


def parse_interactive_flags(raw_flags: str) -> list[str]:
    """Parse interactive entity input, defaulting to all supported flags."""
    if not raw_flags.strip():
        return ["NAME", "EMAIL", "PHONE"]

    return re.split(r"[\s,]+", raw_flags.strip())


def run_interactive() -> None:
    """Prompt the user for a single PDF redaction job."""
    print("Interactive resume redactor")
    print("Press Enter at the flags prompt to redact NAME, EMAIL, and PHONE.")

    input_pdf = Path(input("Input PDF path: ").strip().strip("'\""))
    default_output = default_output_path(input_pdf)
    output_answer = input(f"Output PDF path [{default_output}]: ").strip().strip("'\"")
    flags_answer = input("Redact what? [NAME EMAIL PHONE]: ")

    output_pdf = Path(output_answer) if output_answer else default_output
    flags = parse_interactive_flags(flags_answer)

    redact_resume(str(input_pdf), str(output_pdf), flags)


def run_batch(input_dir: str, output_dir: str | None, flags: list[str]) -> None:
    """Redact every PDF in a folder into an output folder."""
    source_dir = Path(input_dir)

    if not source_dir.is_dir():
        raise RedactionError(f"Batch input folder does not exist: {source_dir}")

    destination_dir = Path(output_dir) if output_dir else source_dir / "redacted"
    pdf_files = sorted(
        path
        for path in source_dir.glob("*.pdf")
        if "_redacted" not in path.stem.lower()
    )

    if not pdf_files:
        raise RedactionError(f"No PDF files found in: {source_dir}")

    print(f"Batch redacting {len(pdf_files)} PDF(s).")
    print(f"Output folder: {destination_dir}")

    for index, input_pdf in enumerate(pdf_files, start=1):
        output_pdf = default_output_path(input_pdf, destination_dir)
        print(f"\n[{index}/{len(pdf_files)}] {input_pdf.name}")
        redact_resume(str(input_pdf), str(output_pdf), flags)


def print_usage() -> None:
    """Show CLI usage."""
    print("Usage:")
    print("  python redactor.py")
    print("  python redactor.py input.pdf output.pdf NAME EMAIL PHONE")
    print("  python redactor.py --batch folder_path [output_folder] [NAME EMAIL PHONE]")
    print("")
    print("Examples:")
    print("  python redactor.py")
    print("  python redactor.py resume.pdf resume_redacted.pdf NAME EMAIL")
    print("  python redactor.py --batch ./resumes ./redacted NAME EMAIL PHONE")


def main(argv: list[str]) -> int:
    """Run the CLI while keeping errors clean for terminal users."""
    try:
        if len(argv) == 1:
            run_interactive()
            return 0

        if argv[1] in {"-h", "--help"}:
            print_usage()
            return 0

        if argv[1] == "--batch":
            if len(argv) < 3:
                print_usage()
                return 2

            input_dir = argv[2]
            output_dir: str | None = None
            flags_start = 3

            if len(argv) >= 4 and argv[3].upper() not in SUPPORTED_ENTITIES:
                output_dir = argv[3]
                flags_start = 4

            flags = argv[flags_start:] or ["NAME", "EMAIL", "PHONE"]
            run_batch(input_dir, output_dir, flags)
            return 0

        if len(argv) < 4:
            print_usage()
            return 2

        input_pdf = argv[1]
        output_pdf = argv[2]
        requested_flags = argv[3:]
        redact_resume(input_pdf, output_pdf, requested_flags)
        return 0
    except RedactionError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
