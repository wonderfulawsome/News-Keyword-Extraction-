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
    return psycopg2.connect(db_url)

# feed_specs.csv의 모든 정보를 하드코딩 (각 항목에 '언론사'와 'rss_url' 포함)
feed_specs = [
    # Khan 그룹 (1~12)
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/total_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/politic_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/economy_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/society_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/kh_world.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "http://www.khan.co.kr/rss/rssdata/kh_sports.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/culture_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/kh_entertainment.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "http://www.khan.co.kr/rss/rssdata/it_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/people_news.xml"},
    {"언론사": "寃쏀뼢?좊Ц", "rss_url": "https://www.khan.co.kr/rss/rssdata/skentertain_news.xml"},

    # KMIB 그룹 (13~21)
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibRssAll.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibPolRss.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibEcoRss.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibSocRss.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibIntRss.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibSpoRss.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibCulRss.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibLifRss.xml"},
    {"언론사": "援???쇰낫", "rss_url": "http://rss.kmib.co.kr/data/kmibColRss.xml"},

    # Newsis 그룹 (22~31)
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/international.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/bank.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/society.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/sports.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/culture.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/politics.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/economy.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/industry.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/health.xml"},
    {"언론사": "Newsis", "rss_url": "https://newsis.com/RSS/entertain.xml"},

    # Donga 그룹 (32~48)
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/total.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/politics.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/national.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/economy.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/international.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/editorials.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/science.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/culture.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/sports.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/inmul.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/health.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/leisure.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/book.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/show.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/woman.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/travel.xml"},
    {"언론사": "Donga", "rss_url": "https://rss.donga.com/lifeinfo.xml"},

    # 단지, Labortoday
    {"언론사": "Ddanzi", "rss_url": "https://www.ddanzi.com/rss"},
    {"언론사": "Labortoday", "rss_url": "https://www.labortoday.co.kr/rss/allArticle.xml"},

    # Mediatoday 그룹 (51~58)
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/allArticle.xml"},
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/S1N2.xml"},
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/S1N3.xml"},
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/S1N4.xml"},
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/S1N5.xml"},
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/S1N6.xml"},
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/S1N7.xml"},
    {"언론사": "Mediatoday", "rss_url": "https://www.mediatoday.co.kr/rss/S1N8.xml"},

    # Seoul 그룹 (59~65)
    {"언론사": "Seoul", "rss_url": "https://www.seoul.co.kr/xml/rss/rss_politics.xml"},
    {"언론사": "Seoul", "rss_url": "https://www.seoul.co.kr/xml/rss/rss_society.xml"},
    {"언론사": "Seoul", "rss_url": "https://www.seoul.co.kr/xml/rss/rss_economy.xml"},
    {"언론사": "Seoul", "rss_url": "https://www.seoul.co.kr/xml/rss/rss_international.xml"},
    {"언론사": "Seoul", "rss_url": "https://www.seoul.co.kr/xml/rss/rss_life.xml"},
    {"언론사": "Seoul", "rss_url": "https://www.seoul.co.kr/xml/rss/rss_sports.xml"},
    {"언론사": "Seoul", "rss_url": "https://www.seoul.co.kr/xml/rss/rss_entertainment.xml"},

    # Segye 그룹 (66~74)
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_recent.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_politic.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_economy.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_society.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_international.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_culture.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_opinion.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_entertainment.xml"},
    {"언론사": "Segye", "rss_url": "http://www.segye.com/Articles/RSSList/segye_sports.xml"},

    # Sisain 그룹 (75~82)
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/allArticle.xml"},
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/S1N6.xml"},
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/S1N7.xml"},
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/S1N8.xml"},
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/S1N9.xml"},
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/S1N10.xml"},
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/S1N11.xml"},
    {"언론사": "Sisain", "rss_url": "https://www.sisain.co.kr/rss/S1N12.xml"},

    # Sisajournal 그룹 (83~91)
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/allArticle.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S1N47.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S1N54.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S1N56.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S1N57.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S1N58.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S1N59.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S2N106.xml"},
    {"언론사": "Sisajournal", "rss_url": "http://www.sisajournal.com/rss/S2N107.xml"},

    # Ablenews 그룹 (92~98)
    {"언론사": "Ablenews", "rss_url": "https://www.ablenews.co.kr/rss/allArticle.xml"},
    {"언론사": "Ablenews", "rss_url": "https://www.ablenews.co.kr/rss/S1N1.xml"},
    {"언론사": "Ablenews", "rss_url": "https://www.ablenews.co.kr/rss/S1N2.xml"},
    {"언론사": "Ablenews", "rss_url": "https://www.ablenews.co.kr/rss/S1N4.xml"},
    {"언론사": "Ablenews", "rss_url": "https://www.ablenews.co.kr/rss/S1N8.xml"},
    {"언론사": "Ablenews", "rss_url": "https://www.ablenews.co.kr/rss/S1N9.xml"},
    {"언론사": "Ablenews", "rss_url": "https://www.ablenews.co.kr/rss/S1N11.xml"},

    # Womennews 그룹 (99~109)
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/allArticle.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N1.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N2.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N3.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N4.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N6.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N7.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N12.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N15.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N16.xml"},
    {"언론사": "Womennews", "rss_url": "http://www.womennews.co.kr/rss/S1N39.xml"},

    # Ildaro
    {"언론사": "Ildaro", "rss_url": "https://www.ildaro.com/rss/rss_news.php"},

    # Chosun 그룹 (111~119)
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/national/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/international/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/culture-life/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/sports/?outputType=xml"},
    {"언론사": "Chosun", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/entertainments/?outputType=xml"},

    # Newscj 그룹 (120~129)
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_allArticle.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N1.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N2.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N3.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N6.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N14.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N15.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N4.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N5.xml"},
    {"언론사": "Newscj", "rss_url": "https://cdn.newscj.com/rss/gns_S1N16.xml"},

    # Tongilnews 그룹 (130~137)
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/allArticle.xml"},
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/S1N4.xml"},
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/S1N5.xml"},
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/S1N6.xml"},
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/S1N7.xml"},
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/S1N9.xml"},
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/S1N10.xml"},
    {"언론사": "Tongilnews", "rss_url": "https://www.tongilnews.com/rss/S1N18.xml"},

    # Pressian 그룹 (138~144)
    {"언론사": "Pressian", "rss_url": "https://www.pressian.com/api/v3/site/rss/news"},
    {"언론사": "Pressian", "rss_url": "https://www.pressian.com/api/v3/site/rss/section/65"},
    {"언론사": "Pressian", "rss_url": "https://www.pressian.com/api/v3/site/rss/section/66"},
    {"언론사": "Pressian", "rss_url": "https://www.pressian.com/api/v3/site/rss/section/67"},
    {"언론사": "Pressian", "rss_url": "https://www.pressian.com/api/v3/site/rss/section/68"},
    {"언론사": "Pressian", "rss_url": "https://www.pressian.com/api/v3/site/rss/section/69"},
    {"언론사": "Pressian", "rss_url": "https://www.pressian.com/api/v3/site/rss/section/70"},

    # Hani 그룹 (145~154)
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/politics/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/economy/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/society/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/international/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/culture/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/sports/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/science/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/opinion/"},
    {"언론사": "Hani", "rss_url": "https://www.hani.co.kr/rss/cartoon/"}
]

# feed_specs의 정보를 그대로 반환 (이미 '언론사'와 'rss_url' 키가 있음)
def get_rss_list():
    return feed_specs

def update_database():
    """RSS 수집 → 기존 방식의 키워드 추출 → TOPSIS 계산 → DB 업데이트."""
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

    # (키워드 추출, TOPSIS 평가 및 DB 업데이트 관련 코드는 생략)
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

    # 뉴스 제목 전처리
    docs = [preprocess(doc) for doc in news_df["제목"].tolist()]

    # KR-WordRank 모델 초기화 및 키워드 추출
    wordrank_extractor = KRWordRank(min_count=5, max_length=10, verbose=True)
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)

    # 후처리: 숫자나 대괄호가 포함된 키워드 필터링
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    print("추출된 키워드:", keywords)
    return jsonify(keywords)

@app.route('/')
def root():
    return "Flask API Server - No HTML served here. Use /data, /update, or /kr-wordrank."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
