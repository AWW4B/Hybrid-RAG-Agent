import os
import logging
import re

logger = logging.getLogger(__name__)

DOCS_DIR = os.getenv("DOCS_DIR", "/app/dataset")
# On host (Windows) during dev, it might be different, but in Docker it's /app/dataset
# For the script to work during development, let's try a relative path if the absolute one fails
if not os.path.exists(DOCS_DIR):
    # Try a relative path for local testing
    DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "dataset")

def search_products(query: str) -> str:
    """
    Simulates a database search for products matching a query (title, brand, category).
    Also supports price-based sorting for 'expensive' or 'cheap' queries.
    """
    try:
        if not os.path.exists(DOCS_DIR):
            return "Product catalog is currently offline (directory not found)."

        query_lower = query.lower().strip()
        results = []
        
        # Increase scan limit to 500 files for better coverage
        files = [f for f in os.listdir(DOCS_DIR) if f.endswith(".txt")][:500]
        
        # Keywords to trigger sorting
        find_expensive = "expensive" in query_lower or "high" in query_lower or "top" in query_lower
        find_cheap = "cheap" in query_lower or "budget" in query_lower or "low" in query_lower
        
        # Clean query for text matching
        search_term = re.sub(r"\b(expensive|cheap|cheapest|most|highest|lowest|find|show|me|best|buy|want|to)\b", "", query_lower).strip()
        if not search_term:
            search_term = query_lower

        for filename in files:
            file_path = os.path.join(DOCS_DIR, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                # Search across the full file content
                if search_term in content.lower():
                    # Extract Title and Price
                    title_match = re.search(r"Title:\s*(.*)", content, re.IGNORECASE)
                    price_match = re.search(r"Deal Alert:.*?for\s*([\d,]+\s*PKR)", content, re.IGNORECASE)
                    if not price_match:
                        price_match = re.search(r"Base Price:\s*(.*)", content, re.IGNORECASE)
                    
                    title = title_match.group(1).strip() if title_match else filename
                    price_str = price_match.group(1).strip() if price_match else ""
                    
                    # Parse numeric price for sorting
                    price_val = 0
                    if price_str:
                        numeric_part = re.sub(r"[^\d]", "", price_str)
                        if numeric_part:
                            price_val = int(numeric_part)
                    
                    results.append({
                        "title": title,
                        "price_str": price_str or "Price on request",
                        "price_val": price_val
                    })
        
        if not results:
            return f"I couldn't find any products matching '{query}' in our local catalog."

        # Sort results if requested
        if find_expensive:
            results.sort(key=lambda x: x["price_val"], reverse=True)
        elif find_cheap:
            results.sort(key=lambda x: x["price_val"])
        
        # Format output
        top_results = results[:8] # Return up to 8 matching items
        formatted = [f"- {r['title']} ({r['price_str']})" for r in top_results]
            
        return f"I found {len(results)} matching products (showing top {len(formatted)}):\n" + "\n".join(formatted)

    except Exception as e:
        logger.error(f"Product search tool error: {e}")
        return "I'm having trouble searching the catalog right now."
