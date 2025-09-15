import os
import csv
import hashlib
import asyncio
from datetime import datetime
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler
from models import SearchResult, get_session


def generate_unique_id(url):
    """Generates a consistent unique ID for each URL using MD5."""
    return hashlib.md5(url.encode()).hexdigest()


def save_to_csv(results, filename=None):
    """Saves search results to a CSV file."""
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bing_results_{ts}.csv"
    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", filename)

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Query", "Title", "URL", "Snippet", "Unique ID"])
        for query, item in results:
            writer.writerow([query, item['title'], item['url'], item['snippet'], item['unique_id']])
    print(f"✅ Saved CSV to: {path}")


async def scrape_query(query):
    """Scrapes Bing search results for a single query using BeautifulSoup."""
    print(f"🔍 Scraping Bing for query: {query}")
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    crawler = AsyncWebCrawler()

    try:
        response = await crawler.arun(url)
        html = response.html
        soup = BeautifulSoup(html, "html.parser")
        results = []

        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            snippet_p = li.select_one("div.b_caption p")

            title = a.get_text(strip=True) if a else ""
            result_url = a.get("href") if a else ""
            snippet = snippet_p.get_text(strip=True) if snippet_p else ""

            if title and result_url:
                unique_id = generate_unique_id(result_url)
                results.append((
                    query,
                    {
                        "title": title,
                        "url": result_url,
                        "snippet": snippet,
                        "unique_id": unique_id
                    }
                ))

        if not results:
            print(f"⚠️ No results found for query: {query}")
        return results

    except Exception as e:
        print(f"❌ Error scraping Bing for '{query}': {e}")
        return []

async def scrape_page_and_save(url, unique_id):
    """Uses crawl4ai to fetch full page content and save plain text to file."""
    try:
        print(f"🌐 Crawling page: {url}")
        crawler = AsyncWebCrawler()
        response = await crawler.arun(url)
        html = response.html

        if not html.strip():
            print(f"⚠️ Empty HTML content for URL: {url}")
            return

        # Extract plain text using BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        text_content = soup.get_text(separator="\n", strip=True)

        if not text_content.strip():
            print(f"⚠️ No extractable text found in page: {url}")
            return
        os.makedirs("scraped_pages", exist_ok=True)
        file_path = os.path.join("scraped_pages", f"{unique_id}.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        print(f"✅ Saved plain text to: {file_path}")

    except Exception as e:
        print(f"❌ Error extracting text from URL '{url}': {e}")


       
async def scrape_multiple_queries(queries):
    """Main orchestrator for multi-query scraping and full-page crawl."""
    all_results = []

    # Step 1: Scrape Bing for each query
    for query in queries:
        result_set = await scrape_query(query)
        all_results.extend(result_set)

    # Step 2: Store in DB
    session = get_session()
    try:
        for query, item in all_results:
            search_result = SearchResult(
                query=query,
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"],
                unique_id=item["unique_id"]
            )
            session.merge(search_result)  # insert or update based on unique_id
        session.commit()
        print("✅ Search results saved to DB.")
    except Exception as e:
        print(f"❌ Error saving to DB: {e}")
        session.rollback()
    finally:
        session.close()

    # Step 3: Save CSV
    save_to_csv(all_results)

    # Step 4: Scrape each URL's full page content
    tasks = [scrape_page_and_save(item["url"], item["unique_id"]) for _, item in all_results]
    await asyncio.gather(*tasks)  