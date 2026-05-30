# PDF Resume Redactor

A robust Python utility designed to securely extract and permanently redact Personally Identifiable Information (PII) from PDF documents. 

This repository contains two different architectural approaches to solving the redaction problem, isolated across two separate Git branches.

## 🔀 Branch Architecture

### 1. The `simple-redactor` Branch (Recommended/Active)
**Approach:** Hardcoded Batch Processing & Exact String Matching  
**Best for:** 100% accuracy and bulk processing of PDFs where the target PII is known.

This branch features a highly modular, 3-file architecture built on the principle of Separation of Concerns:
* `config.py` (The Data): A dictionary mapping specific PDFs to their target PII strings. Supports multi-word fallbacks to handle complex graphic design edge cases (e.g., line-breaks or heavy font kerning like "S A M I R A").
* `redactor.py` (The Engine): Securely processes the document using PyMuPDF. It automatically sorts target strings by length (longest-first) to prevent partial redaction bugs, maps the exact X/Y visual coordinates of the text, and burns solid black boxes into the page.
* `main.py` (The Runner): Iterates through the batch jobs in the configuration file, automatically routing files from the `templates/` directory through the redaction engine.

**Quick Start for this branch:**
1. Switch to the branch: `git checkout simple-redactor`
2. Add your target PDFs to the `templates/` folder.
3. Update `config.py` with your file names and target strings.
4. Run `python main.py`. Clean `_redacted.pdf` files will automatically generate.

---

### 2. The `master` Branch
**Approach:** Dynamic Pattern Matching & NLP  
**Best for:** Processing completely unknown formats where the PII strings cannot be provided beforehand.

This branch relies on Regular Expressions (Regex) and the `spaCy` Natural Language Processing model to dynamically hunt for patterns that resemble phone numbers, emails, and names without hardcoded inputs.
* **Pros:** Requires no manual data entry or configuration prior to running.
* **Cons:** More susceptible to missing heavily stylized resume fonts, invisible graphic design line-breaks, or highly unique international formatting.

## 🛠 Tech Stack
* **Language:** Python 3
* **Core PDF Engine:** PyMuPDF (`fitz`)
* **NLP Engine:** `spaCy` (utilized exclusively on the `master` branch)