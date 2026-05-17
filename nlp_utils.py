#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import spacy
from nltk.corpus import stopwords
import nltk

# Загрузка необходимых ресурсов NLTK (для стоп-слов)
nltk.download('stopwords')

# Загрузка модели spaCy для русского языка
try:
    nlp = spacy.load("ru_core_news_sm")
except OSError:
    raise RuntimeError(
        "Модель 'ru_core_news_sm' не найдена. Установите её командой: "
        "python -m spacy download ru_core_news_sm"
    )

# Дополнительные стоп-слова
russian_stopwords = stopwords.words('russian') + [
    'я', 'ты', 'он', 'она', 'мы', 'вы', 'они', 'это', 'весь', 'свой'
]

def extract_keywords(text: str, top_n: int = 5) -> list:
    """
    Извлекает ключевые слова из текста с использованием spaCy.
    Возвращает список лемм (нормальных форм слов).

    Параметры:
        text (str): Текст для анализа.
        top_n (int): Количество возвращаемых ключевых слов.

    Возвращает:
        list: Список ключевых слов (лемм).
    """
    # Предварительная очистка текста
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    
    # Обработка текста spaCy
    doc = nlp(text)
    
    keywords = []
    seen_lemmas = set()
    
    for token in doc:
        # Пропускаем стоп-слова, знаки препинания и короткие слова
        if (token.is_alpha 
            and not token.is_stop 
            and len(token.text) > 2
            and token.lemma_ not in russian_stopwords):
            
            lemma = token.lemma_
            if lemma not in seen_lemmas:
                seen_lemmas.add(lemma)
                keywords.append(lemma)
                
                if len(keywords) >= top_n:
                    break
    
    return keywords

# Пример использования (для тестировани
