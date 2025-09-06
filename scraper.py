from urllib.parse import quote_plus
from crawl4ai import AsyncWebCrawler
from models import SearchResult, get_session
import asyncio
import csv
from datetime import datetime
import os

def save_to_csv(results, filename=None):
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bing_results_{timestamp}.csv"

    os.makedirs("exports", exist_ok=True)
    filepath = os.path.join("exports", filename)

    with open(filepath, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(["Query", "Title", "URL", "Snippet"])
        for query, item in results:
            writer.writerow([
                query,
                getattr(item, "title", "").strip(),
                getattr(item, "url", "").strip(),
                getattr(item, "snippet", "").strip()
            ])
    print(f"✅ Saved results to {filepath}")

async def scrape_query(query):
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    crawler = AsyncWebCrawler()
    try:
        result = await crawler.arun(url, selectors={
            "_": "li.b_algo",
            "title": "h2 a",
            "url": "h2 a@href",
            "snippet": ".b_algo p"
        })
    except Exception as e:
        print(f"Scraping failed for '{query}': {e}")
        return []

    return [(query, item) for item in result]

async def scrape_multiple_queries(queries):
    tasks = [scrape_query(q) for q in queries]
    all_results = await asyncio.gather(*tasks)
    flat_results = [item for sublist in all_results for item in sublist]

    session = get_session()
    try:
        for query, item in flat_results:
            search_result = SearchResult(
                query=query,
                title=getattr(item, "title", ""),
                url=getattr(item, "url", ""),
                snippet=getattr(item, "snippet", "")
            )
            session.add(search_result)
        session.commit()

        # ✅ Save to CSV
        save_to_csv(flat_results)

    except Exception as e:
        print(f"Database insert failed: {e}")
        session.rollback()
    finally:
        session.close()