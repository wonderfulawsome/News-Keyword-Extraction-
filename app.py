import os
import psycopg2
import pandas as pd
import feedparser
import requests
from collections import Counter
import numpy as np
from flask import Flask, jsonify
from flask_cors import CORS  # CORS 추가
import re

# 전처리 함수: 대괄호 안 내용과 숫자 제거
def preprocess(text):
    text = re.sub(r'\[[^\]]*\]', '', text)  # 대괄호 안의 내용 제거
    text = re.sub(r'\d+', '', text)          # 숫자 제거
    return text.strip()

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

API_KEY = os.environ.get("GEMINI_API_KEY")

def get_db_connection():
    """PostgreSQL 연결."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    conn = psycopg2.connect(db_url)
    return conn

def load_rss_list():
    """feed_specs.csv에서 RSS 목록 불러오기."""
    file_path = "feed_specs.csv"
    rss_specs_df = pd.read_csv(file_path)
    return rss_specs_df[["publisher", "categories", "url"]].rename(columns={"publisher": "언론사", "categories": "카테고리", "url": "rss_url"})

def parse_rss(url):
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        entries.append({
            "제목": entry.title,
            "링크": entry.link,
            "발행일": entry.get("published", None)
        })
    return entries

def update_database():
    """RSS 수집 → 기존 방식의 키워드 추출 → TOPSIS 계산 → DB 업데이트."""
    rss_df = load_rss_list()
    all_news = []
    for _, row in rss_df.iterrows():
        source = row["언론사"]
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
        all_news.extend(news_items)
    return pd.DataFrame(all_news)

@app.route('/update')
def update():
    updated_df = update_database()
    return jsonify(updated_df.to_dict(orient='records'))

@app.route('/data')
def data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM keyword_ranking", conn)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

@app.route('/kr-wordrank')
def kr_wordrank():
    from krwordrank.word import KRWordRank
    beta = 0.85
    max_iter = 10
    rss_df = load_rss_list()
    all_news = []
    for _, row in rss_df.iterrows():
        source = row["언론사"]
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)
    docs = [preprocess(doc) for doc in news_df["제목"].tolist()]
    wordrank_extractor = KRWordRank(min_count=5, max_length=10, verbose=True)
    keywords, _, _ = wordrank_extractor.extract(docs, beta, max_iter)
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}
    return jsonify(keywords)

@app.route('/')
def root():
    return "Flask API Server - No HTML served here. Use /data, /update, or /kr-wordrank."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
