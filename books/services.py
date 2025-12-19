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

def get_book_details(title, author):
    """
    Gets detailed information about a specific book from Google Books API,
    including description/summary.
    Uses caching to reduce latency.
    """
    # Create a search query from title and author
    query = f"{title} {author}"
    query_normalized = query.lower().strip()
    cache_key = f"google_books_details:{query_normalized}"
    
    # Check cache first
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result
    
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {'q': f'intitle:"{title}"+inauthor:"{author}"', 'maxResults': 1}
    
    try:
        response = _session.get(url, params=params, timeout=5)
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException:
        return None
    
    if response.status_code == 200:
        data = response.json()
        items = data.get('items', [])
        if items:
            volume_info = items[0].get('volumeInfo', {})
            description = volume_info.get('description', '')
            # Sometimes description is HTML, sometimes plain text
            # Return as-is, frontend can handle it
            
            result = {
                'title': volume_info.get('title', title),
                'author': ', '.join(volume_info.get('authors', [author])),
                'description': description,
                'published_date': volume_info.get('publishedDate', ''),
                'page_count': volume_info.get('pageCount', ''),
                'categories': volume_info.get('categories', []),
                'image_links': volume_info.get('imageLinks', {}),
                'preview_link': volume_info.get('previewLink', ''),
                'info_link': volume_info.get('infoLink', ''),
            }
            
            # Cache for 24 hours
            cache.set(cache_key, result, 86400)
            return result
    
    return None