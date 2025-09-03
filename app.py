import asyncio
from flask import Flask, request, render_template
from scraper import scrape_multiple_queries
from models import get_session, SearchResult

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    results_by_query = {}
    if request.method == 'POST':
        queries = request.form['query'].split(',')  # comma-separated queries
        queries = [q.strip().lower() for q in queries if q.strip()]
        
        asyncio.run(scrape_multiple_queries(queries))

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