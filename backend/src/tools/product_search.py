import os
import re
import unicodedata
import logging

logger = logging.getLogger(__name__)

DOCS_DIR = os.getenv("DOCS_DIR", "/app/dataset")
if not os.path.exists(DOCS_DIR):
    DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "dataset")


def _normalize(text: str) -> str:
    """Lowercase, strip accents/apostrophes, collapse whitespace."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"['\"`''']", "", text)   # remove apostrophes
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_STOPWORDS = {
    "expensive", "cheap", "cheapest", "most", "highest", "lowest",
    "find", "show", "me", "best", "buy", "want", "to", "the", "a",
    "an", "and", "or", "for", "in", "of", "on", "with",
}


def search_products(query: str) -> str:
    """
    Search the local product catalog (flat .txt files) for a query.
    Returns a formatted list of matching products with prices.
    """
    try:
        if not os.path.exists(DOCS_DIR):
            return "Product catalog is currently offline (directory not found)."

        norm_query = _normalize(query)
        find_expensive = any(w in norm_query for w in ("expensive", "high", "top", "premium"))
        find_cheap = any(w in norm_query for w in ("cheap", "budget", "low", "affordable"))

        # Extract meaningful keywords, drop stopwords and very short tokens
        keywords = [kw for kw in norm_query.split() if kw not in _STOPWORDS and len(kw) > 2]
        if not keywords:
            keywords = norm_query.split()

        files = sorted(f for f in os.listdir(DOCS_DIR) if f.endswith(".txt"))[:500]
        results = []

        for filename in files:
            file_path = os.path.join(DOCS_DIR, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw = f.read()
            except Exception:
                continue

            norm_content = _normalize(raw)

            # Count how many keywords appear in the normalised content
            match_count = sum(1 for kw in keywords if kw in norm_content)
            if match_count < max(1, len(keywords) * 0.6):
                continue

            title_match = re.search(r"Title:\s*(.*)", raw, re.IGNORECASE)
            price_match = re.search(r"Deal Alert:.*?for\s*([\d,]+\s*PKR)", raw, re.IGNORECASE)
            if not price_match:
                price_match = re.search(r"Base Price:\s*(.*)", raw, re.IGNORECASE)

            title     = title_match.group(1).strip() if title_match else filename
            price_str = price_match.group(1).strip() if price_match else ""

            price_val = 0
            if price_str:
                numeric = re.sub(r"[^\d]", "", price_str)
                if numeric:
                    price_val = int(numeric)

            results.append({"title": title, "price_str": price_str or "Price on request", "price_val": price_val})

        if not results:
            return f"No products found matching '{query}' in the catalog. Try shorter keywords like a brand name."

        if find_expensive:
            results.sort(key=lambda x: x["price_val"], reverse=True)
        elif find_cheap:
            results.sort(key=lambda x: x["price_val"])

        top = results[:8]
        formatted = [f"- {r['title']} ({r['price_str']})" for r in top]
        return f"Found {len(results)} product(s) (showing top {len(formatted)}):\n" + "\n".join(formatted)

    except Exception as e:
        logger.error(f"[product_search] Error: {e}")
        return "I'm having trouble searching the catalog right now."
