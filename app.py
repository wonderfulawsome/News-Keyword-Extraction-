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

def load_feed_specs():
    """
    프로젝트 루트에 업로드된 feed_specs.csv 파일 읽기.
    CSV는 publisher, title, categories, url 컬럼을 가짐.
    'publisher'와 'url'을 각각 '언론사', 'rss_url'로 재명명.
    """
    df = pd.read_csv("feed_specs.csv")
    df = df.rename(columns={"publisher": "언론사", "url": "rss_url"})
    return df

def update_database():
    """RSS 수집 → 기존 방식의 키워드 추출 → TOPSIS 계산 → DB 업데이트."""
    # feed_specs.csv 파일 읽기
    rss_df = load_feed_specs()

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

    all_news = []
    for _, row in rss_df.iterrows():
        source = row["언론사"]
        feed_title = row.get("title", None)
        feed_categories = row.get("categories", None)
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
            item["feed_title"] = feed_title
            item["feed_categories"] = feed_categories
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)

    # (기존 KR-WordRank가 아닌 Gemini API를 사용한 방식)
    # ... TOPSIS 계산 및 DB 업데이트 코드 (생략) ...
    return pd.DataFrame()  # placeholder

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

# 새로운 엔드포인트: KR-WordRank를 사용하여 키워드 추출
@app.route('/kr-wordrank')
def kr_wordrank():
    from krwordrank.word import KRWordRank
    # 파라미터 설정
    beta = 0.85
    max_iter = 10

    # feed_specs.csv 파일 읽기
    rss_df = load_feed_specs()

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

    all_news = []
    for _, row in rss_df.iterrows():
        source = row["언론사"]
        feed_title = row.get("title", None)
        feed_categories = row.get("categories", None)
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
            item["feed_title"] = feed_title
            item["feed_categories"] = feed_categories
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)

    # 제목 리스트 생성 후 전처리 적용
    docs = [preprocess(doc) for doc in news_df["제목"].tolist()]

    # KR-WordRank 모델 초기화 및 키워드 추출
    wordrank_extractor = KRWordRank(
        min_count=5,
        max_length=10,
        verbose=True
    )
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)

    # 후처리: 숫자나 대괄호 포함 키워드 필터링
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    print("추출된 키워드:", keywords)
    return jsonify(keywords)

@app.route('/')
def root():
    # 루트 접근 시 간단한 안내문 반환 (HTML 서빙은 하지 않음)
    return "Flask API Server - No HTML served here. Use /data, /update, or /kr-wordrank."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
