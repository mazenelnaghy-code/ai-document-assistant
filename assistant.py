"""Ask questions about a folder of PDFs and get answers that cite the file and page.

Usage:
    python assistant.py docs "How many days of annual leave do I get?"
    python assistant.py docs "Can I return opened electronics?" --search    # no API key needed

How it works:
    1. Every page of every PDF is read and indexed (BM25 keyword search, no external service).
    2. The pages that best match the question are sent to Claude as documents with citations on.
    3. Claude answers only from those pages, and every claim comes back with the page it came from.

Only the best-matching pages are sent, never the whole folder, so each question stays fast and cheap.
Answers need an Anthropic API key in ANTHROPIC_API_KEY. --search shows the matching pages without one.
"""
import argparse
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

MODEL = "claude-opus-5-5"
TOP_PAGES = 4
WORD = re.compile(r"[a-z0-9]+")
STOPWORDS = set("a an and are as at be by can do does for from how i if in is it its me my of on or our "
                "the their there this to was we what when where which who will with you your".split())
SYSTEM = ("You answer questions about a company's internal documents. Use only the documents provided. "
          "If they don't contain the answer, say so plainly instead of guessing. Keep answers short and "
          "practical, and quote exact numbers, limits and deadlines from the documents.")


@dataclass
class Page:
    file: str
    number: int
    text: str
    words: Counter = field(default_factory=Counter, repr=False)

    @property
    def title(self):
        return f"{self.file}, page {self.number}"


@dataclass
class Answer:
    text: str
    sources: list  # (page title, quoted text)
    refused: bool = False


def stem(word):
    """Crude stemming so 'meals' finds 'meal' and 'travelling' finds 'travel'."""
    for suffix in ("ing", "ed", "s"):
        if word.endswith(suffix) and not word.endswith("ss") and len(word) - len(suffix) >= 3:
            word = word[:-len(suffix)]
            if len(word) > 3 and word[-1] == word[-2] and word[-1] not in "aeiou":
                word = word[:-1]  # travell -> travel
            break
    return word


def tokens(text):
    return [stem(w) for w in WORD.findall(text.lower()) if w not in STOPWORDS]


def load_pages(folder):
    """Every page with text, from every PDF in the folder. Pages without a text layer are skipped."""
    pages = []
    for pdf_path in sorted(Path(folder).glob("*.pdf")):
        with pdfplumber.open(pdf_path) as pdf:
            for number, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append(Page(pdf_path.name, number, text, Counter(tokens(text))))
    return pages


def search(pages, question, k=TOP_PAGES, k1=1.5, b=0.75, keep=0.5):
    """Up to k pages that best match the question, best first, scored with BM25.

    Pages scoring below `keep` x the best score only share a common word with the question, so they are
    dropped rather than sent to the model."""
    terms = set(tokens(question))
    if not pages or not terms:
        return []
    avg_len = sum(sum(p.words.values()) for p in pages) / len(pages)
    scored = []
    for page in pages:
        length = sum(page.words.values())
        score = 0.0
        for term in terms:
            tf = page.words[term]
            if tf:
                df = sum(1 for p in pages if p.words[term])
                idf = math.log(1 + (len(pages) - df + 0.5) / (df + 0.5))
                score += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg_len))
        if score > 0:
            scored.append((score, page))
    scored.sort(key=lambda s: -s[0])
    return [page for score, page in scored[:k] if score >= keep * scored[0][0]]


def build_request(question, pages, model=MODEL):
    """Keyword arguments for client.beta.messages.create: one cited document per page, then the question."""
    documents = [{
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": page.text},
        "title": page.title,
        "citations": {"enabled": True},
    } for page in pages]
    return {
        "model": model,
        "max_tokens": 16000,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": documents + [{"type": "text", "text": question}]}],
        # If the model declines a request, the API retries it on a fallback model in the same call.
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }


def ask(client, question, pages, model=MODEL):
    """Ask Claude, and return the answer with numbered sources."""
    if not pages:
        return Answer("None of the documents mention that.", [])
    response = client.beta.messages.create(**build_request(question, pages, model))
    if response.stop_reason == "refusal":
        return Answer("The model declined to answer this question.", [], refused=True)

    parts, sources = [], []
    for block in response.content:
        if block.type != "text":  # thinking and fallback blocks carry no answer text
            continue
        parts.append(block.text)
        for citation in block.citations or []:
            source = (citation.document_title, citation.cited_text.strip())
            if source not in sources:
                sources.append(source)
            parts.append(f" [{sources.index(source) + 1}]")
    return Answer("".join(parts).strip(), sources)


def format_answer(answer):
    lines = [answer.text]
    if answer.sources:
        lines += ["", "Sources:"]
        lines += [f"  [{i}] {title}: \"{quote}\"" for i, (title, quote) in enumerate(answer.sources, start=1)]
    return "\n".join(lines)


def format_search(question, hits):
    lines = [f"Pages that best match: {question}", ""]
    for i, page in enumerate(hits, start=1):
        first = " ".join(page.text.split())
        lines.append(f"  {i}. {page.title}")
        lines.append(f"     {first[:110]}{'...' if len(first) > 110 else ''}")
    return "\n".join(lines) if hits else f"No page mentions: {question}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="folder of PDF documents")
    parser.add_argument("question")
    parser.add_argument("--search", action="store_true", help="only show the matching pages (no API key needed)")
    parser.add_argument("--pages", type=int, default=TOP_PAGES, help="how many pages to send with the question")
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args(argv)

    pages = load_pages(args.folder)
    if not pages:
        sys.exit(f"No readable PDF pages in {args.folder}")
    hits = search(pages, args.question, k=args.pages)
    if args.search:
        print(format_search(args.question, hits))
        return

    import anthropic
    try:
        answer = ask(anthropic.Anthropic(), args.question, hits, args.model)
    except anthropic.AuthenticationError:
        sys.exit("The API key was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        sys.exit("Rate limited by the API. Wait a minute and try again.")
    except anthropic.APIStatusError as e:
        sys.exit(f"API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        sys.exit("Could not reach the API. Check your internet connection.")
    except TypeError as e:  # the SDK raises TypeError when it finds no credentials at all
        if "authentication" not in str(e):
            raise
        sys.exit("No API key found. Set ANTHROPIC_API_KEY, or run with --search to see the matching pages.")
    print(format_answer(answer))


if __name__ == "__main__":
    main()
