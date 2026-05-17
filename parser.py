import requests
from bs4 import BeautifulSoup
import sqlite3
from time import sleep

def parse_dream_symbol(symbol: str) -> str:
    """Парсит интерпретацию символа сна с juicyworld.org"""
    try:
        url = f"https://juicyworld.org/dream-interpretation-freud/?s={symbol}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        sleep(2) 
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем заголовок <h4> с нужным символом
        for h4 in soup.find_all('h4'):
            if h4.text.strip().lower() == symbol.lower():
                interpretation = h4.find_next('p').text.strip()
                return interpretation
        return "Интерпретация не найдена."
    
    except Exception as e:
        print(f"Ошибка парсинга: {e}")
        return "Ошибка при получении данных."

# Пример использования
