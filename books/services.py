import requests
from django.core.cache import cache

# Create a session for connection pooling (reuses TCP connections)
_session = requests.Session()

def search_google_books(query):
    """
    Searches Google Books API with caching to reduce latency.
    Uses connection pooling and caching for better performance.
    """
    # Normalize query for cache key
    query_normalized = query.lower().strip()
    cache_key = f"google_books_search:{query_normalized}"
    
    # Check cache first (cache hits are <50ms vs 500-1000ms for API calls)
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        return cached_results
    
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {'q': query, 'maxResults': 5}
    
    # Add timeout to prevent hanging on slow API responses
    try:
        response = _session.get(url, params=params, timeout=5)
    except requests.exceptions.Timeout:
        return []
    except requests.exceptions.RequestException:
        return []
    
    results = []
    
    if response.status_code == 200:
        data = response.json()
        for item in data.get('items', []):
            volume_info = item.get('volumeInfo', {})
            
            # Extract ISBN-13 if available, otherwise fallback
            identifiers = volume_info.get('industryIdentifiers', [])
            isbn = next((i['identifier'] for i in identifiers if i['type'] == 'ISBN_13'), None)
            
            # Skip books without ISBNs for data quality
            if not isbn:
                continue

            results.append({
                'title': volume_info.get('title'),
                'author': volume_info.get('authors', ['Unknown'])[0], # Just take the first author
                'isbn': isbn,
                'google_id': item.get('id')
            })
    
    # Cache results for 24 hours (86400 seconds)
    # Popular searches will be instant on subsequent requests
    cache.set(cache_key, results, 86400)
    
    return results