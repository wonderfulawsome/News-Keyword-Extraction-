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

# feed_specs.csv 내용을 하드코딩 (url만 사용)
feed_specs = [
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/total_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/politic_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/economy_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/society_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/kh_world.xml"},
    {"rss_url": "http://www.khan.co.kr/rss/rssdata/kh_sports.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/culture_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/kh_entertainment.xml"},
    {"rss_url": "http://www.khan.co.kr/rss/rssdata/it_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/people_news.xml"},
    {"rss_url": "https://www.khan.co.kr/rss/rssdata/skentertain_news.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibRssAll.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibPolRss.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibEcoRss.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibSocRss.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibIntRss.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibSpoRss.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibCulRss.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibLifRss.xml"},
    {"rss_url": "http://rss.kmib.co.kr/data/kmibColRss.xml"},
    {"rss_url": "https://newsis.com/RSS/international.xml"},
    {"rss_url": "https://newsis.com/RSS/bank.xml"},
    {"rss_url": "https://newsis.com/RSS/society.xml"},
    {"rss_url": "https://newsis.com/RSS/sports.xml"},
    {"rss_url": "https://newsis.com/RSS/culture.xml"},
    {"rss_url": "https://newsis.com/RSS/politics.xml"},
    {"rss_url": "https://newsis.com/RSS/economy.xml"},
    {"rss_url": "https://newsis.com/RSS/industry.xml"},
    {"rss_url": "https://newsis.com/RSS/health.xml"},
    {"rss_url": "https://newsis.com/RSS/entertain.xml"},
    {"rss_url": "https://rss.donga.com/total.xml"},
    {"rss_url": "https://rss.donga.com/politics.xml"},
    {"rss_url": "https://rss.donga.com/national.xml"},
    {"rss_url": "https://rss.donga.com/economy.xml"},
    {"rss_url": "https://rss.donga.com/international.xml"},
    {"rss_url": "https://rss.donga.com/editorials.xml"},
    {"rss_url": "https://rss.donga.com/science.xml"},
    {"rss_url": "https://rss.donga.com/culture.xml"},
    {"rss_url": "https://rss.donga.com/sports.xml"},
    {"rss_url": "https://rss.donga.com/inmul.xml"},
    {"rss_url": "https://rss.donga.com/health.xml"},
    {"rss_url": "https://rss.donga.com/leisure.xml"},
    {"rss_url": "https://rss.donga.com/book.xml"},
    {"rss_url": "https://rss.donga.com/show.xml"},
    {"rss_url": "https://rss.donga.com/woman.xml"},
    {"rss_url": "https://rss.donga.com/travel.xml"},
    {"rss_url": "https://rss.donga.com/lifeinfo.xml"},
    {"rss_url": "https://www.ddanzi.com/rss"},
    {"rss_url": "https://www.labortoday.co.kr/rss/allArticle.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/allArticle.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/S1N2.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/S1N3.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/S1N4.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/S1N5.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/S1N6.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/S1N7.xml"},
    {"rss_url": "https://www.mediatoday.co.kr/rss/S1N8.xml"},
    {"rss_url": "https://www.seoul.co.kr/xml/rss/rss_politics.xml"},
    {"rss_url": "https://www.seoul.co.kr/xml/rss/rss_society.xml"},
    {"rss_url": "https://www.seoul.co.kr/xml/rss/rss_economy.xml"},
    {"rss_url": "https://www.seoul.co.kr/xml/rss/rss_international.xml"},
    {"rss_url": "https://www.seoul.co.kr/xml/rss/rss_life.xml"},
    {"rss_url": "https://www.seoul.co.kr/xml/rss/rss_sports.xml"},
    {"rss_url": "https://www.seoul.co.kr/xml/rss/rss_entertainment.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_recent.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_politic.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_economy.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_society.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_international.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_culture.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_opinion.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_entertainment.xml"},
    {"rss_url": "http://www.segye.com/Articles/RSSList/segye_sports.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/allArticle.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/S1N6.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/S1N7.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/S1N8.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/S1N9.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/S1N10.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/S1N11.xml"},
    {"rss_url": "https://www.sisain.co.kr/rss/S1N12.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/allArticle.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S1N47.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S1N54.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S1N56.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S1N57.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S1N58.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S1N59.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S2N106.xml"},
    {"rss_url": "http://www.sisajournal.com/rss/S2N107.xml"},
    {"rss_url": "https://www.ablenews.co.kr/rss/allArticle.xml"},
    {"rss_url": "https://www.ablenews.co.kr/rss/S1N1.xml"},
    {"rss_url": "https://www.ablenews.co.kr/rss/S1N2.xml"},
    {"rss_url": "https://www.ablenews.co.kr/rss/S1N4.xml"},
    {"rss_url": "https://www.ablenews.co.kr/rss/S1N8.xml"},
    {"rss_url": "https://www.ablenews.co.kr/rss/S1N9.xml"},
    {"rss_url": "https://www.ablenews.co.kr/rss/S1N11.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/allArticle.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N1.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N2.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N3.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N4.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N6.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N7.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N12.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N15.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N16.xml"},
    {"rss_url": "http://www.womennews.co.kr/rss/S1N39.xml"},
    {"rss_url": "https://www.ildaro.com/rss/rss_news.php"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/national/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/international/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/culture-life/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/sports/?outputType=xml"},
    {"rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/entertainments/?outputType=xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_allArticle.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N1.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N2.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N3.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N6.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N14.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N15.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N4.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N5.xml"},
    {"rss_url": "https://cdn.newscj.com/rss/gns_S1N16.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/allArticle.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/S1N4.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/S1N5.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/S1N6.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/S1N7.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/S1N9.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/S1N10.xml"},
    {"rss_url": "https://www.tongilnews.com/rss/S1N18.xml"},
    {"rss_url": "https://www.pressian.com/api/v3/site/rss/news"},
    {"rss_url": "https://www.pressian.com/api/v3/site/rss/section/65"},
    {"rss_url": "https://www.pressian.com/api/v3/site/rss/section/66"},
    {"rss_url": "https://www.pressian.com/api/v3/site/rss/section/67"},
    {"rss_url": "https://www.pressian.com/api/v3/site/rss/section/68"},
    {"rss_url": "https://www.pressian.com/api/v3/site/rss/section/69"},
    {"rss_url": "https://www.pressian.com/api/v3/site/rss/section/70"},
    {"rss_url": "https://www.hani.co.kr/rss/"},
    {"rss_url": "https://www.hani.co.kr/rss/politics/"},
    {"rss_url": "https://www.hani.co.kr/rss/economy/"},
    {"rss_url": "https://www.hani.co.kr/rss/society/"},
    {"rss_url": "https://www.hani.co.kr/rss/international/"},
    {"rss_url": "https://www.hani.co.kr/rss/culture/"},
    {"rss_url": "https://www.hani.co.kr/rss/sports/"},
    {"rss_url": "https://www.hani.co.kr/rss/science/"},
    {"rss_url": "https://www.hani.co.kr/rss/opinion/"},
    {"rss_url": "https://www.hani.co.kr/rss/cartoon/"}
]

# feed_specs의 URL을 기반으로 언론사명을 임의(Publisher1, Publisher2, …)로 할당
def get_rss_list():
    return [{"언론사": f"Publisher{i+1}", "rss_url": spec["rss_url"]}
            for i, spec in enumerate(feed_specs)]

def update_database():
    """RSS 수집 → 기존 방식의 키워드 추출 → TOPSIS 계산 → DB 업데이트."""
    # feed_specs 기반 rss_list 사용
    rss_list = get_rss_list()
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
    # ... TOPSIS 평가 및 DB 업데이트 코드 (생략)
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
    beta = 0.85
    max_iter = 10

    # feed_specs 기반 rss_list 사용
    rss_list = get_rss_list()
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

    # 제목 리스트 생성 및 전처리
    docs = [preprocess(doc) for doc in news_df["제목"].tolist()]

    # KR-WordRank 모델 초기화
    wordrank_extractor = KRWordRank(min_count=5, max_length=10, verbose=True)

    # 키워드 추출
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)

    # 후처리: 숫자나 대괄호가 포함된 키워드는 필터링
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    print("추출된 키워드:", keywords)
    return jsonify(keywords)

@app.route('/')
def root():
    return "Flask API Server - No HTML served here. Use /data, /update, or /kr-wordrank."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
