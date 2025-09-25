import os
import csv
import hashlib
import asyncio
from datetime import datetime
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qs, urlencode
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from models import SearchResult, get_session

MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

def normalize_url(url):
    """Normalize URL by removing query parameters, sorting them, and removing trailing slashes."""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    sorted_query = urlencode(sorted(query_params.items()))  # Sort query parameters

    normalized_url = urlunparse((
        parsed_url.scheme.lower(),
        parsed_url.netloc.lower(),
        parsed_url.path.rstrip('/'),
        '',
        sorted_query,
        ''
    ))
    return normalized_url

def generate_unique_id(url):
    """Generates a consistent unique ID for each URL using MD5."""
    return hashlib.md5(url.encode()).hexdigest()

def save_to_csv(results, filename=None):
    """Saves search results to a CSV file, ensuring no duplicate URLs."""
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bing_results_{ts}.csv"

    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", filename)

    seen_urls = set()  # Local deduplication for CSV

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Query", "Title", "URL", "Snippet", "Unique ID"])

        for query, item in results:
            normalized_url = normalize_url(item['url'])
            if normalized_url not in seen_urls:
                seen_urls.add(normalized_url)
                writer.writerow([query, item['title'], item['url'], item['snippet'], item['unique_id']])
            else:
                print(f"⚠️ Duplicate URL skipped in CSV: {item['url']}")

    print(f"✅ Saved unique results to CSV: {path}")

def is_relevant_result(title, snippet, query):
    """Check if the search result is relevant to the query, e.g., location-based."""
    query_keywords = query.lower().split()
    title = title.lower()
    snippet = snippet.lower()
    return any(k in title for k in query_keywords) or any(k in snippet for k in query_keywords)

async def scrape_query(query, page_number=1, seen_urls=None):
    """Scrapes Bing search results for a single query and page using BeautifulSoup."""
    print(f"🔍 Scraping Bing for query: {query}, Page: {page_number}")
    results_per_page = 10
    first_result = (page_number - 1) * results_per_page
    url = f"https://www.bing.com/search?q={quote_plus(query)}&first={first_result}"
    headers = {
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    crawler = AsyncWebCrawler()
    results = []

    try:
        response = await crawler.arun(url, headers=headers)
        soup = BeautifulSoup(response.html, "html.parser")

        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            snippet_p = li.select_one("div.b_caption p")

            title = a.get_text(strip=True) if a else ""
            result_url = a.get("href") if a else ""
            snippet = snippet_p.get_text(strip=True) if snippet_p else ""

            if title and result_url and is_relevant_result(title, snippet, query):
                normalized_url = normalize_url(result_url)

                # Only add URL if it has not been seen yet
                if normalized_url not in seen_urls:
                    seen_urls.add(normalized_url)
                    unique_id = generate_unique_id(normalized_url)
                    results.append((query, {
                        "title": title,
                        "url": result_url,
                        "snippet": snippet,
                        "unique_id": unique_id
                    }))
                else:
                    print(f"⚠️ Duplicate URL skipped in results: {result_url}")

        if not results:
            print(f"⚠️ No results found for query: {query}, Page: {page_number}")
        return results

    except Exception as e:
        print(f"❌ Error scraping Bing for '{query}', Page {page_number}: {e}")
        return []

async def scrape_page_and_save(url, unique_id, max_retries=3):
    """Fetch full page content and save plain text, with retries and extended timeout."""
    crawler = AsyncWebCrawler()
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🌐 Crawling page: {url} (Attempt {attempt})")
            response = await crawler.arun(url, wait_until="domcontentloaded", timeout=60000)
            html = response.markdown
            if not html or not html.strip():
                print(f"⚠️ Empty HTML content for URL: {url}")
                return

            soup = BeautifulSoup(html, "html.parser")
            text_content = soup.get_text(separator="\n", strip=True)
            if not text_content.strip():
                print(f"⚠️ No extractable text found in page: {url}")
                return

            os.makedirs("scraped_pages", exist_ok=True)
            file_path = os.path.join("scraped_pages", f"{unique_id}.md")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(text_content)

            print(f"✅ Saved plain text to: {file_path}")
            return

        except Exception as e:
            print(f"❌ Error extracting text from URL '{url}' on attempt {attempt}: {e}")
            if attempt < max_retries:
                wait_time = 5 * attempt
                print(f"⏳ Retrying after {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                print(f"❌ Max retries reached for URL: {url}")

async def scrape_multiple_queries(queries):
    """Main orchestrator for multi-query scraping and full-page crawl."""
    seen_urls = set()  # Global seen_urls that persists across all pages and queries
    all_results = []

    # Scrape all pages for all queries
    for query in queries:
        for page_number in range(1, 11):  # Scrape up to 10 pages
            result_set = await scrape_query(query, page_number, seen_urls)
            all_results.extend(result_set)

    # Save to DB
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
            session.merge(search_result)
        session.commit()
        print("✅ Search results saved to DB.")
    except Exception as e:
        print(f"❌ Error saving to DB: {e}")
        session.rollback()
    finally:
        session.close()

    # Save to CSV (deduplication already handled via seen_urls)
    save_to_csv(all_results)

    # Scrape full page content
    tasks = [scrape_page_and_save(item["url"], item["unique_id"]) for _, item in all_results]
    await asyncio.gather(*tasks)