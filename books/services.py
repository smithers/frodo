import requests
import hashlib
import logging
import time
from django.core.cache import cache
from django.db.models import Q
from books.models import Book, Author

logger = logging.getLogger(__name__)

# Create a session for connection pooling (reuses TCP connections)
_session = requests.Session()

def sanitize_cache_key(query):
    """
    Sanitize a query string for use in cache keys.
    Replaces spaces and other problematic characters with safe alternatives.
    """
    # Normalize: lowercase and strip
    normalized = query.lower().strip()
    # Replace spaces and other problematic characters with underscores
    # This ensures memcached compatibility
    sanitized = normalized.replace(' ', '_').replace(':', '_').replace(';', '_')
    # For very long queries, use a hash to keep keys manageable
    if len(sanitized) > 200:
        return hashlib.md5(sanitized.encode('utf-8')).hexdigest()
    return sanitized

def search_database_books(query):
    """
    Search for books in the local database (popular books only, for speed).
    Returns results in the same format as search_google_books.
    """
    if not query.strip():
        return []
    
    # Search in popular books only (fast local search)
    # Use case-insensitive search on title and author name
    popular_books = Book.objects.filter(
        is_popular=True
    ).filter(
        Q(title__icontains=query) | 
        Q(author__name__icontains=query)
    ).select_related('author')[:5]  # Limit to 5 results like Google API
    
    results = []
    for book in popular_books:
        if book.isbn:  # Only include books with ISBN for consistency
            results.append({
                'title': book.title,
                'author': book.author.name,
                'isbn': book.isbn,
                'google_id': None  # Not from Google
            })
    
    return results


def search_books(query):
    """
    Unified search function that checks database first, then Google API.
    This replaces direct calls to search_google_books.
    """
    logger.debug(f"Searching for: {query}")
    
    # First, search the local database (popular books)
    db_results = search_database_books(query)
    logger.debug(f"Database search returned {len(db_results)} results")
    
    # Always search Google API to ensure we have comprehensive results
    # (even if we have 5 DB results, Google might have better/exact matches)
    google_results = search_google_books(query)
    logger.debug(f"Google Books search returned {len(google_results)} results")
    
    # Combine results, avoiding duplicates by ISBN (or by title+author when no ISBN)
    seen_isbns = {r['isbn'] for r in db_results if r.get('isbn')}
    seen_title_author = {(r['title'].lower(), r['author'].lower()) for r in db_results}
    combined_results = db_results.copy()

    # Add Google results, prioritizing them if we have fewer than 5 total
    for result in google_results:
        if len(combined_results) >= 10:  # Increased limit since we fetch 10 from Google
            break
        isbn = result.get('isbn') or ''
        key = (result.get('title', '').lower(), result.get('author', '').lower())
        if isbn and isbn in seen_isbns:
            logger.debug(f"Skipping duplicate by ISBN: {result.get('title')}")
            continue
        if key in seen_title_author:
            logger.debug(f"Skipping duplicate by title/author: {result.get('title')}")
            continue
        combined_results.append(result)
        if isbn:
            seen_isbns.add(isbn)
        seen_title_author.add(key)

    logger.debug(f"Combined search returning {len(combined_results[:5])} results")
    
    # Return top 5 results (prioritize Google results if we have both)
    # If we have DB results, keep them but add Google results up to 5 total
    return combined_results[:5]


def search_google_books(query):
    """
    Searches Google Books API with caching to reduce latency.
    Uses connection pooling and caching for better performance.
    """
    # Sanitize query for cache key to avoid memcached issues
    query_sanitized = sanitize_cache_key(query)
    cache_key = f"google_books_search:{query_sanitized}"
    
    # Check cache first (cache hits are <50ms vs 500-1000ms for API calls)
    cached_results = cache.get(cache_key)
    if cached_results is not None:
        logger.debug(f"Google Books cache hit for query: {query}")
        return cached_results
    
    url = "https://www.googleapis.com/books/v1/volumes"
    # Increase maxResults to get more options, then we'll limit to 5 after filtering
    params = {'q': query, 'maxResults': 10}
    
    logger.debug(f"Calling Google Books API for query: {query}")
    
    # Retry logic for rate limiting (429) - try up to 2 times with exponential backoff
    max_retries = 2
    retry_delay = 1  # Start with 1 second delay
    
    for attempt in range(max_retries + 1):
        # Add timeout to prevent hanging on slow API responses
        try:
            response = _session.get(url, params=params, timeout=5)
        except requests.exceptions.Timeout:
            logger.warning(f"Google Books API timeout for query: {query}")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Google Books API request error for query {query}: {e}")
            return []
        
        # Handle rate limiting (429) - retry with exponential backoff
        if response.status_code == 429:
            if attempt < max_retries:
                wait_time = retry_delay * (2 ** attempt)
                logger.warning(f"Google Books API rate limited (429) for query: {query}. Retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"Google Books API rate limited (429) for query: {query} after {max_retries + 1} attempts. Please wait before trying again.")
                return []  # Don't cache rate limit errors
        
        # If we got here, we have a response (either 200 or other error)
        break
    
    results = []
    
    if response.status_code == 200:
        data = response.json()
        total_items = data.get('totalItems', 0)
        items = data.get('items', [])
        logger.debug(f"Google Books API returned {len(items)} items (total: {total_items}) for query: {query}")
        
        for item in items:
            volume_info = item.get('volumeInfo', {})
            
            # Extract title and author - skip if missing
            title = volume_info.get('title', '').strip()
            authors = volume_info.get('authors', [])
            if not title or not authors:
                logger.debug(f"Skipping item without title or author: {volume_info.get('title', 'No title')}")
                continue  # Skip books without title or author
            
            author = authors[0].strip() if authors else 'Unknown'
            if not author:
                logger.debug(f"Skipping item without author: {title}")
                continue
            
            # Extract ISBN - prefer ISBN_13, fall back to ISBN_10, allow no ISBN
            identifiers = volume_info.get('industryIdentifiers', [])
            isbn = next((i['identifier'] for i in identifiers if i['type'] == 'ISBN_13'), None)
            if not isbn:
                isbn = next((i['identifier'] for i in identifiers if i['type'] == 'ISBN_10'), None)
            # Include books even without ISBN so autocomplete shows them (use empty string for dedupe)
            if not isbn:
                isbn = ''

            results.append({
                'title': title,
                'author': author,
                'isbn': isbn,
                'google_id': item.get('id')
            })
            logger.debug(f"Added result: {title} by {author} (ISBN: {isbn or 'none'})")
    else:
        logger.error(f"Google Books API returned status {response.status_code} for query: {query}")
        # Don't cache error responses
        return []
    
    logger.debug(f"Google Books API returning {len(results)} results for query: {query}")
    
    # Cache results for 24 hours (86400 seconds)
    # Popular searches will be instant on subsequent requests
    # Only cache successful results
    if results:
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
    # Sanitize query for cache key to avoid memcached issues
    query_sanitized = sanitize_cache_key(query)
    cache_key = f"google_books_details:{query_sanitized}"
    
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