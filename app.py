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

# 불용어 로드: 파일에서 쉼표로 구분된 단어 읽고 strip()으로 공백 제거
with open('불용어.txt', 'r', encoding='utf-8') as f:
    raw_text = f.read()
raw_stopwords = raw_text.split(',')
stopwords = [w.strip() for w in raw_stopwords if w.strip()]

# 추가로 반드시 제거할 불용어
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

# /kowordrank 엔드포인트: 전체 기사 중 KR‑WordRank 점수로 상위 20개 기사 선정 및 각 기사별로 키워드 2개 추출
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

    # 전처리된 뉴스 제목 리스트 생성
    docs = [preprocess_text(title) for title in news_df["제목"].tolist()]
    docs = [d for d in docs if d.strip()]
    if not docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."}), 400

    # KR‑WordRank 적용 (min_count=1, max_length=10)
    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    # 전체 문서에 대해 단어 점수 산출 (키워드는 사용하지 않고 word_scores만 활용)
    _, word_scores, _ = wordrank_extractor.extract(docs, beta=0.85, max_iter=10)
    # 숫자나 '[' 포함 단어 제거
    word_scores = {k: v for k, v in word_scores.items() if not re.search(r'\d|\[', k)}

    # 각 문서(기사)의 점수 계산: 문서 내 단어들의 전역 점수 합
    doc_scores = []
    for doc in docs:
        words = doc.split()
        score = sum(word_scores.get(word, 0) for word in words)
        doc_scores.append(score)

    # KR‑WordRank 점수를 기준으로 상위 20개 기사 선택
    top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:20]
    top_news = news_df.iloc[top_indices].reset_index(drop=True)
    top_docs = [docs[i] for i in top_indices]

    # 각 기사에서 단어들의 전역 점수를 참고하여 상위 2개 키워드 추출
    results = []
    for i, doc in enumerate(top_docs):
        words = doc.split()
        # 중복 제거(순서 유지)
        unique_words = list(dict.fromkeys(words))
        # 전역 word_scores에 따른 내림차순 정렬
        sorted_words = sorted(unique_words, key=lambda w: word_scores.get(w, 0), reverse=True)
        top_keywords = sorted_words[:2]
        results.append({
            "제목": top_news.iloc[i]["제목"],
            "링크": top_news.iloc[i]["링크"],
            "KRWordRank 키워드": top_keywords
        })

    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
