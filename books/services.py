import requests

def search_google_books(query):
    """
    Searches Google Books API and returns a simplified list of results.
    """
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {'q': query, 'maxResults': 5}
    response = requests.get(url, params=params)
    
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
            
    return results