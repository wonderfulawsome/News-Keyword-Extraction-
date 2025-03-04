import os
import psycopg2
import pandas as pd
import feedparser
import requests
from collections import Counter
import numpy as np
from flask import Flask, jsonify
from flask_cors import CORS  # CORS 추가
import re, string

# --- Konlpy 전처리 코드 추가 ---
from konlpy.tag import Komoran, Hannanum

komoran = Komoran()
hannanum = Hannanum()

with open('불용어.txt', 'r', encoding='utf-8') as f:
    list_file = f.readlines()
stopwords = list_file[0].split(",")

# 정규화 함수
def preprocess(text):
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)
    text = re.sub('\s+', ' ', text)
    text = re.sub(r'\[[0-9]*\]', ' ', text)
    text = re.sub(r'[^\w\s]', ' ', str(text).strip())
    text = re.sub(r'\d', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

# 명사/영단어 추출, 한글자 제외, 불용어 제거
def final(text):
    n = []
    word = komoran.nouns(text)
    p = komoran.pos(text)
    for pos in p:
        if pos[1] in ['SL']:
            word.append(pos[0])
    for w in word:
        if len(w) > 1 and w not in stopwords:
            n.append(w)
    return " ".join(n)

# 최종 전처리 함수
def finalpreprocess(text):
    return final(preprocess(text))
# --- 전처리 코드 끝 ---

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

    # 이 부분은 Gemini LLM을 위한 기존 코드로 placeholder 처리됨
    return pd.DataFrame()

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

# /kr-wordrank 엔드포인트: KR-WordRank로 키워드 추출 후, 해당 키워드와 관련 기사 링크 반환
@app.route('/kr-wordrank')
def kr_wordrank():
    from krwordrank.word import KRWordRank
    beta = 0.85
    max_iter = 10

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

    # 제목 리스트 생성 및 전처리 (최종 전처리 함수 사용)
    docs = [finalpreprocess(doc) for doc in news_df["제목"].tolist()]

    wordrank_extractor = KRWordRank(min_count=5, max_length=10, verbose=True)
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)

    # 후처리: 숫자나 대괄호 포함 키워드 제거
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    # 각 키워드에 대해, 해당 키워드가 포함된 첫 번째 기사 링크 찾기
    result = {}
    for k, score in keywords.items():
        matched = news_df[news_df["제목"].str.contains(k, na=False)]
        if not matched.empty:
            link = matched.iloc[0]["링크"]
        else:
            link = ""
        result[k] = {"score": score, "link": link}

    print("추출된 키워드:", result)
    return jsonify(result)

@app.route('/')
def root():
    return "Flask API Server - No HTML served here. Use /data, /update, or /kr-wordrank."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
