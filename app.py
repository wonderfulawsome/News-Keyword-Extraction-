import os
import re
import string
import feedparser
import pandas as pd
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from krwordrank.word import KRWordRank
from konlpy.tag import Komoran

app = Flask(__name__)
CORS(app)

komoran = Komoran()

# 불용어 로드: 파일에서 쉼표로 구분된 단어들을 읽고 strip()으로 공백 제거
with open('불용어.txt', 'r', encoding='utf-8') as f:
    raw_text = f.read()
raw_stopwords = raw_text.split(',')
stopwords = [w.strip() for w in raw_stopwords if w.strip()]

# 추가 불용어 (파일에 없더라도 강제로 추가)
extra_stopwords = ["종합", "포토", "영상", "게시판"]
for word in extra_stopwords:
    if word not in stopwords:
        stopwords.append(word)

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

# RSS 데이터 파싱 함수
def parse_rss(url):
    feed = feedparser.parse(url)
    return [
        {
            "제목": entry.title if hasattr(entry, 'title') else '',
            "링크": entry.link if hasattr(entry, 'link') else '',
            "발행일": entry.get("published", None)
        }
        for entry in feed.entries
    ]

# 텍스트 전처리 함수
def preprocess(text):
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)  # HTML 태그 제거
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)  # 구두점 제거
    text = re.sub(r'\s+', ' ', text)  # 연속 공백 제거
    text = re.sub(r'\d', ' ', text)     # 숫자 제거
    return text

def extract_keywords(text):
    words = komoran.nouns(text)
    words = [w for w in words if len(w) > 1 and w not in stopwords]
    return " ".join(words)

def preprocess_text(text):
    return extract_keywords(preprocess(text))

# Gemini API를 호출해서 기사 제목을 요약하는 함수
def get_gemini_summary(text):
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        return " ".join(text.split()[:2])
    # 실제 Gemini API 엔드포인트 (Google Generative Language API)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
    # 요청 payload는 API 문서에 따라 수정 필요. 여기서는 prompt를 보내고, maxOutputTokens를 10으로 지정합니다.
    payload = {
        "prompt": (
        f"Summarize the following Korean news article title into exactly 2 or 3 Korean words. "
        f"STRICT RULES: "
        f"- Output must contain ONLY Korean letters (한글) and spaces. "
        f"- NEVER include punctuation marks, symbols, special characters, or numbers.\n\n"
        f"Title: {text}\n"
        f"Summary:"
    ),
        "maxOutputTokens": 10
    }
    headers = {"Content-Type": "application/json"}
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            summary = response.json().get("summary")
            return summary if summary else " ".join(text.split()[:2])
        else:
            return " ".join(text.split()[:2])
    except Exception as e:
        print("Gemini API error:", e)
        return " ".join(text.split()[:2])

# /kowordrank 엔드포인트: KR-WordRank를 적용한 후 Gemini API로 요약하여 상위 20개 결과 반환
@app.route('/kowordrank')
def kowordrank_endpoint():
    category = request.args.get("category", "전체")
    if category not in RSS_FEEDS:
        return jsonify({"error": f"잘못된 카테고리: {category}"}), 400

    rss_urls = RSS_FEEDS[category]
    all_news = []
    for url in rss_urls:
        all_news.extend(parse_rss(url))

    news_df = pd.DataFrame(all_news)
    if news_df.empty or "제목" not in news_df.columns:
        return jsonify({"error": "RSS에서 제목을 가져오지 못했습니다."}), 400

    docs = [preprocess_text(title) for title in news_df["제목"].tolist()]
    docs = [d for d in docs if d.strip()]
    if not docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."})

    # KR-WordRank 설정: min_count=1, max_length=10, beta=0.85, max_iter=10
    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta=0.85, max_iter=10)
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    # 상위 20개만 선택
    sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:20]

    result = {}
    for keyword, score in sorted_keywords:
        matched_df = news_df[news_df["제목"].str.contains(keyword, na=False)]
        if not matched_df.empty:
            article_title = matched_df.iloc[0]["제목"]
            gemini_summary = get_gemini_summary(article_title)
            link = matched_df.iloc[0]["링크"]
            result[gemini_summary] = {"score": score, "link": link}
        else:
            result[keyword] = {"score": score, "link": ""}
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
