from urllib.parse import quote_plus
from crawl4ai import AsyncWebCrawler
from models import SearchResult, get_session
import asyncio

async def scrape_query(query):
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    crawler = AsyncWebCrawler()
    try:
        result = await crawler.arun(url, selectors={
            "_": "li.b_algo",
            "title": "h2",
            "url": "h2 a@href",
            "snippet": "p"
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
            # Use dot notation or getattr to access CrawlResult attributes
            search_result = SearchResult(
                query=query,
                title=getattr(item, "title", ""),
                url=getattr(item, "url", ""),
                snippet=getattr(item, "snippet", "")
            )
            session.add(search_result)
        session.commit()
    except Exception as e:
        print(f"Database insert failed: {e}")
        session.rollback()
    finally:
        session.close()