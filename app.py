import os
import re
import string
import feedparser
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from krwordrank.word import KRWordRank
from konlpy.tag import Komoran

app = Flask(__name__)
CORS(app)

komoran = Komoran()

# 불용어 로드
with open('불용어.txt', 'r', encoding='utf-8') as f:
    stopwords = [w.strip() for w in f.read().split(',') if w.strip()]

extra_stopwords = ["종합", "포토", "영상", "게시판"]
stopwords.extend(extra_stopwords)

# RSS 피드 URL 목록
RSS_FEEDS = {
    "전체": ["https://news.sbs.co.kr/news/headlineRssFeed.do?plink=RSSREADER"],
    "정치": ["https://www.yna.co.kr/rss/politics.xml"],
    "경제": ["https://www.yna.co.kr/rss/economy.xml"],
    "사회": ["https://www.yna.co.kr/rss/society.xml"],
    "세계": ["https://www.yna.co.kr/rss/international.xml"],
    "문화": ["https://www.yna.co.kr/rss/culture.xml"],
    "연예": ["https://www.yna.co.kr/rss/entertainment.xml"],
    "스포츠": ["https://www.yna.co.kr/rss/sports.xml"]
}

# 뉴스 데이터 수집 함수
def parse_rss(url):
    """RSS에서 뉴스 데이터 수집"""
    feed = feedparser.parse(url)
    return [
        {
            "제목": entry.title if hasattr(entry, 'title') else '',
            "링크": entry.link if hasattr(entry, 'link') else '',
            "발행일": entry.get("published", None)
        }
        for entry in feed.entries
    ]

# 텍스트 전처리
def preprocess(text):
    """텍스트 정제"""
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)  # HTML 태그 제거
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)  # 구두점 제거
    text = re.sub(r'\s+', ' ', text)  # 연속 공백 제거
    text = re.sub(r'\d', ' ', text)  # 숫자 제거
    return text

def extract_keywords(text):
    """명사 추출 + 불용어 제거"""
    words = komoran.nouns(text)
    words = [w for w in words if len(w) > 1 and w not in stopwords]
    return " ".join(words)

def preprocess_text(text):
    """전체 전처리 수행"""
    return extract_keywords(preprocess(text))

# KoWordRank를 사용한 키워드 추출 API
@app.route('/kowordrank')
def kowordrank_endpoint():
    category = request.args.get("category", "전체")
    if category not in RSS_FEEDS:
        return jsonify({"error": f"잘못된 카테고리: {category}"}), 400

    # 해당 카테고리의 RSS에서 뉴스 데이터 수집
    rss_urls = RSS_FEEDS[category]
    all_news = []
    for url in rss_urls:
        all_news.extend(parse_rss(url))

    news_df = pd.DataFrame(all_news)
    if news_df.empty or "제목" not in news_df.columns:
        return jsonify({"error": "RSS에서 제목을 가져오지 못했습니다."}), 400

    # 뉴스 제목 전처리 및 KoWordRank 적용
    docs = [preprocess_text(title) for title in news_df["제목"].tolist()]
    docs = [d for d in docs if d.strip()]
    if not docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."})

    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    keywords, word_scores, _ = wordrank_extractor.extract(docs, beta=0.85, max_iter=10)

    # 숫자, 특수문자 키워드 제거
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    # 상위 20개 키워드 선택
    sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:20]

    result = {}
    for keyword, score in sorted_keywords:
        matched_df = news_df[news_df["제목"].str.contains(keyword, na=False)]
        link = matched_df.iloc[0]["링크"] if not matched_df.empty else ""
        result[keyword] = {"score": score, "link": link}

    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
