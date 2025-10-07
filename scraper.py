import os
import csv
import hashlib
import asyncio
import requests
from datetime import datetime
from urllib.parse import quote_plus, urlparse, urlunparse, parse_qs, urlencode
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from models import SearchResult, get_session
import re
# Utility Functions

def normalize_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    sorted_query = urlencode(sorted(query.items()))
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        parsed.path.rstrip('/'),
        '',  # params
        sorted_query,
        ''   # fragment
    ))

def generate_unique_id(url):
    return hashlib.md5(url.encode()).hexdigest()

def save_to_csv(results, filename=None):
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"bing_results_{ts}.csv"

    os.makedirs("exports", exist_ok=True)
    path = os.path.join("exports", filename)
    seen = set()

    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Query", "Title", "URL", "Snippet", "Unique ID"])
        for query, item in results:
            norm_url = normalize_url(item['url'])
            if norm_url not in seen:
                seen.add(norm_url)
                writer.writerow([query, item['title'], item['url'], item['snippet'], item['unique_id']])
    print(f"✅ CSV saved: {path}")

def is_relevant_result(title, snippet, query):
    keywords = query.lower().split()
    return any(k in title.lower() or k in snippet.lower() for k in keywords)

# Step 1: Bing Search Scraping

async def scrape_search_results(query, page_number=1, seen_urls=None):
    if seen_urls is None:
        seen_urls = set()
    count = 10
    offset = (page_number - 1) * count
    url = f"https://www.bing.com/search?q={quote_plus(query)}&count={count}&offset={offset}"
   
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = await asyncio.to_thread(requests.get, url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        results = []

        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            p = li.select_one("div.b_caption p")
            title = a.get_text(strip=True) if a else ""
            link = a.get("href") if a else ""
            snippet = p.get_text(strip=True) if p else ""

            if link and title:
                norm_url = normalize_url(link)
                if norm_url in seen_urls:
                    continue  # skip duplicates
                seen_urls.add(norm_url)

                unique_id = generate_unique_id(norm_url)
                results.append((query, {
                    "title": title,
                    "url": link,
                    "snippet": snippet,
                    "unique_id": unique_id
                }))

        return results

    except Exception as e:
        print(f"❌ Error fetching search results: {e}")
        return []
def sanitize_folder_name(query):
    return re.sub(r'[^a-zA-Z0-9_-]', '_', query).lower()

# Step 2: Full Page Scraping

async def scrape_full_page(url, unique_id, query, max_retries=2):
    crawler = AsyncWebCrawler()
    for attempt in range(1, max_retries + 1):
        try:
            print(f"🌍 Crawling: {url} (Try {attempt})")
            response = await crawler.arun(url, wait_until="domcontentloaded", timeout=60000)
            soup = BeautifulSoup(response.markdown, "html.parser")
            text = soup.get_text(separator="\n", strip=True)

            if text:
                query_folder = sanitize_folder_name(query)
                os.makedirs(f"scraped_pages/{query_folder}", exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{unique_id}_{timestamp}.md"
                path = os.path.join("scraped_pages", query_folder, filename)
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"✅ Page saved: {path}")
                return
            else:
                print("⚠️ No content found.")

        except Exception as e:
            print(f"❌ Error crawling {url}: {e}")
            await asyncio.sleep(5 * attempt)

# Main Orchestrator

async def scrape_multiple_queries(queries):
    all_results = []

    for query in queries:
        seen_urls = set()  
        for page in range(1, 10):  
            results = await scrape_search_results(query, page, seen_urls=seen_urls)
            if not results:
                break  
            all_results.extend(results)
   
    # Save to DB
    session = get_session()
    try:
        for query, item in all_results:
            sr = SearchResult(
                query=query,
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"],
                unique_id=item["unique_id"]
            )
            session.merge(sr)
        session.commit()
        print("✅ Saved to database.")
    except Exception as e:
        print(f"❌ DB error: {e}")
        session.rollback()
    finally:
        session.close()

    # Save to CSV
    save_to_csv(all_results)

    # Crawl each full page
    tasks = [scrape_full_page(item["url"], item["unique_id"],query) for query, item in all_results]
    await asyncio.gather(*tasks)