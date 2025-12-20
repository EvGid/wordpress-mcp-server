import requests
from bs4 import BeautifulSoup
import sys

# Force utf-8 for windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

url = "https://04travel.ru/"
try:
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Try to find the header or navigation area containing these keywords
    # Keywords from image: "Туры", "Маршруты", "Инфо", "Контакты", "Бронирование"
    
    # Search for an element containing "Контакты"
    contact_link = soup.find(lambda tag: tag.name == "a" and "Контакты" in tag.text)
    
    if contact_link:
        # Get the parent container (likely the menu wrapper)
        # We go up a few levels to capture the context
        container = contact_link.find_parent('header') or contact_link.find_parent('div', class_=lambda c: c and 'menu' in c) or contact_link.parent.parent
        
        if container:
            print("Found navigation structure:")
            print(container.prettify())
        else:
            print("Found link but couldn't identify container.")
            print(contact_link.parent.prettify())
    else:
        print("Could not find 'Контакты' link on the page.")
        
except Exception as e:
    print(f"Error: {e}")
