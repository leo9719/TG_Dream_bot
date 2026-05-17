#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import spacy
import nltk
from nltk.corpus import stopwords

# Загрузка стоп-слов NLTK
nltk.download('stopwords', quiet=True)

# Глобальная переменная для модели spaCy (ленивая загрузка)
nlp = None

def load_spacy():
    """Загружает модель spaCy (один раз)"""
    global nlp
    if nlp is None:
        try:
            nlp = spacy.load("ru_core_news_sm")
        except OSError:
            print("Скачиваем модель spaCy ru_core_news_sm...")
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "ru_core_news_sm"], check=True)
            nlp = spacy.load("ru_core_news_sm")
    return nlp


# Дополнительные русские стоп-слова
russian_stopwords = stopwords.words('russian') + [
    'я', 'ты', 'он', 'она', 'мы', 'вы', 'они', 'это', 'весь', 'свой',
    'быть', 'что', 'который', 'тот', 'такой', 'как', 'по', 'для'
]

def extract_keywords(text: str, top_n: int = 5) -> list:
    """
    Извлекает ключевые слова из текста сна.
    """
    if not text or len(text.strip()) < 3:
        return []

    # Очистка текста
    text = re.sub(r'[^\w\s]', ' ', text.lower())

    # Загружаем модель
    nlp_model = load_spacy()
    doc = nlp_model(text)

    keywords = []
    seen = set()

    for token in doc:
        lemma = token.lemma_.strip()
        if (token.is_alpha and 
            len(lemma) > 2 and 
            not token.is_stop and 
            lemma not in russian_stopwords and
            lemma not in seen):
            
            seen.add(lemma)
            keywords.append(lemma)
            
            if len(keywords) >= top_n:
                break

    return keywords