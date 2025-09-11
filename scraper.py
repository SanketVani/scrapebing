from urllib.parse import quote_plus
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy, HTTPCrawlerConfig
from models import SearchResult, get_session
import os
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import asyncio

def save_to_csv(results, filename=None):
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bing_results_{ts}.csv"
    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", filename)

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Query", "Title", "URL", "Snippet"])
        for query, item in results:
            writer.writerow([query, item['title'], item['url'], item['snippet']])
    print(f"Saved results to {path}")


async def scrape_query(query):
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    crawler = AsyncWebCrawler()

    try:
        # Run crawler - this returns the rendered HTML page as a string
        response = await crawler.arun(url)

        # response.html is the full HTML content rendered by the browser
        html = response.html
        
        # Use BeautifulSoup to parse the html and extract search results
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            snippet_p = li.select_one("div.b_caption p")
            
            title = a.get_text(strip=True) if a else ""
            url = a.get("href") if a else ""
            snippet = snippet_p.get_text(strip=True) if snippet_p else ""
            
            if title and url:
                results.append((query, {"title": title, "url": url, "snippet": snippet}))

        if not results:
            print(f"No results found for query: {query}")

        return results

    except Exception as e:
        print(f"Error scraping query '{query}': {e}")
        return []

async def scrape_multiple_queries(queries):
    all_results = []
    for q in queries:
        res = await scrape_query(q)
        all_results.extend(res)

    # Store to DB or CSV 
    session = get_session()
    try:
        for query, item in all_results:
            search_result = SearchResult(
                query=query,
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"]
            )
            session.add(search_result)
        session.commit()
        save_to_csv(all_results)
    except Exception as e:
        print(f"Database insert failed: {e}")
        session.rollback()
    finally:
        session.close()
