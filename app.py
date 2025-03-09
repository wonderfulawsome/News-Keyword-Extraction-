import os
import re
import string
import feedparser
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from konlpy.tag import Komoran
from krwordrank.word import KRWordRank

app = Flask(__name__)
CORS(app)

komoran = Komoran()

# 불용어 로드: 파일에서 쉼표로 구분된 단어 읽기
with open('불용어.txt', 'r', encoding='utf-8') as f:
    raw_text = f.read()
raw_stopwords = raw_text.split(',')
stopwords = [w.strip() for w in raw_stopwords if w.strip()]

# 추가 불용어
extra_stopwords = ["종합", "포토", "영상", "게시판", "속보"]
for word in extra_stopwords:
    if word not in stopwords:
        stopwords.append(word)

# RSS 피드 URL 목록
RSS_FEEDS = {
    "전체": ["https://www.hankyung.com/feed/all-news"],
    "정치": ["https://www.hankyung.com/feed/politics"],
    "경제": ["https://www.hankyung.com/feed/economy"],
    "사회": ["https://www.hankyung.com/feed/society"],
    "세계": ["https://www.hankyung.com/feed/international"],
    "문화": ["https://www.hankyung.com/feed/life"],
    "연예": ["https://www.hankyung.com/feed/entertainment"],
    "스포츠": ["https://www.hankyung.com/feed/sports"]
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

# 클리닝 함수: HTML 태그, 구두점, 숫자, 여분의 공백 제거
def clean_text(text):
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\d', ' ', text)
    return text

# 전처리 함수: 클리닝 후 Komoran으로 명사 추출 및 불용어 제거
def preprocess_text(text):
    cleaned = clean_text(text)
    nouns = komoran.nouns(cleaned)
    nouns = [w for w in nouns if len(w) > 1 and w not in stopwords]
    return " ".join(nouns)

@app.route('/kowordrank')
def kowordrank_endpoint():
    category = request.args.get("category", "전체")
    if category not in RSS_FEEDS:
        return jsonify({"error": f"잘못된 카테고리: {category}"}), 400

    # RSS 피드에서 기사 수집
    all_news = []
    for url in RSS_FEEDS[category]:
        all_news.extend(parse_rss(url))
    
    news_df = pd.DataFrame(all_news)
    if news_df.empty or "제목" not in news_df.columns:
        return jsonify({"error": "RSS에서 제목을 가져오지 못했습니다."}), 400

    # 각 기사마다 KR‑WordRank를 적용해 2개 키워드 추출
    results = []
    for _, row in news_df.iterrows():
        title = row["제목"]
        link = row["링크"]
        # 전처리: Komoran을 이용한 명사 추출 (KR‑WordRank 입력용)
        processed = preprocess_text(title)
        # 문서가 비어있으면 fallback: 클리닝된 제목 사용
        if not processed.strip():
            processed = clean_text(title)
        # 단일 문서(리스트 한 요소)로 KRWordRank 실행
        extractor = KRWordRank(min_count=1, max_length=10, verbose=False)
        keywords_dict, _, _ = extractor.extract([processed], beta=0.85, max_iter=10)
        sorted_keywords = sorted(keywords_dict.items(), key=lambda x: x[1], reverse=True)
        top_keywords = [kw for kw, score in sorted_keywords][:2]
        results.append({
            "제목": title,
            "링크": link,
            "키워드": top_keywords
        })

    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
