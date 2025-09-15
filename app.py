import asyncio
from flask import Flask, request, render_template
from scraper import scrape_multiple_queries
from models import get_session, SearchResult

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    results_by_query = {}

    if request.method == 'POST':
        raw_input = request.form.get('query', '')
        queries = [q.strip().lower() for q in raw_input.split(',') if q.strip()]
        print(f" Received queries: {queries}")

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(scrape_multiple_queries(queries))

        session = get_session()
        try:
            for q in queries:
                results = session.query(SearchResult).filter_by(query=q).all()
                results_by_query[q] = results
        finally:
            session.close()

    return render_template('index.html', results_by_query=results_by_query)

if __name__ == '__main__':
    app.run(debug=True)
