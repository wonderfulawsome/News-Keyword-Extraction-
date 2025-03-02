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

def update_database():
    """RSS 수집 → 기존 방식의 키워드 추출 → TOPSIS 계산 → DB 업데이트."""
    # (이전 코드와 동일)
    rss_list = [
        {"언론사": "mk뉴스", "rss_url": "https://www.mk.co.kr/rss/30000001/"},
        {"언론사": "한경", "rss_url": "https://www.hankyung.com/feed/economy"},
        {"언론사": "연합뉴스", "rss_url": "https://www.yonhapnewseconomytv.com/rss/clickTop.xml"},
        {"언론사": "jtbc", "rss_url": "https://news-ex.jtbc.co.kr/v1/get/rss/section/20"},
        {"언론사": "조선일보", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml"},
        {"언론사": "경향신문", "rss_url": "https://www.khan.co.kr/rss/rssdata/economy_news.xml"},
        {"언론사": "아시아경제", "rss_url": "https://www.asiae.co.kr/rss/stock.htm"}
    ]
    rss_df = pd.DataFrame(rss_list)

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
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)

    # (기존 KR-WordRank가 아닌 Gemini API를 사용한 방식)
    # ...
    # 이 함수는 TOPSIS 평가 결과를 DB에 업데이트하고, 그 결과(kw_df)를 반환합니다.
    # (코드는 생략)
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

    # RSS 데이터 수집 (키워드 추출을 위한 뉴스 제목 모음)
    rss_list = [
        {"언론사": "mk뉴스", "rss_url": "https://www.mk.co.kr/rss/30000001/"},
        {"언론사": "한경", "rss_url": "https://www.hankyung.com/feed/economy"},
        {"언론사": "연합뉴스", "rss_url": "https://www.yonhapnewseconomytv.com/rss/clickTop.xml"},
        {"언론사": "jtbc", "rss_url": "https://news-ex.jtbc.co.kr/v1/get/rss/section/20"},
        {"언론사": "조선일보", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml"},
        {"언론사": "경향신문", "rss_url": "https://www.khan.co.kr/rss/rssdata/economy_news.xml"},
        {"언론사": "아시아경제", "rss_url": "https://www.asiae.co.kr/rss/stock.htm"}
    ]
    rss_df = pd.DataFrame(rss_list)

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
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)

    # 제목 리스트 생성
    docs = news_df["제목"].tolist()

    # 제목 리스트 생성 후 전처리 적용
    docs = [preprocess(doc) for doc in news_df["제목"].tolist()]

    # KR-WordRank 모델 초기화
    beta = 0.85
    max_iter = 10
    wordrank_extractor = KRWordRank(
    min_count=5,
    max_length=10,
    verbose=True
)

    # 키워드 추출
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)

    # 후처리: 추출된 키워드 중 숫자나 대괄호 등 불필요한 패턴이 포함된 경우 필터링
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    # 키워드 추출: keywords는 딕셔너리 (키워드: 점수)
    print("추출된 키워드:", keywords)
    return jsonify(keywords)

@app.route('/')
def root():
    # 루트 접근 시 간단한 안내문 반환 (HTML 서빙은 하지 않음)
    return "Flask API Server - No HTML served here. Use /data, /update, or /kr-wordrank."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
