import os
import re
import string
import feedparser
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from krwordrank.word import KRWordRank
from konlpy.tag import Komoran
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

app = Flask(__name__)
CORS(app)

komoran = Komoran()

# 불용어 로드: 파일에서 쉼표로 구분된 단어 읽고 공백 제거
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

# /tfidf_keywords 엔드포인트: KR‑WordRank로 상위 20개 기사 선택 후 각 기사에 대해 TF‑IDF로 2~3개 키워드 추출
@app.route('/tfidf_keywords')
def tfidf_keywords_endpoint():
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

    # 각 뉴스 제목 전처리 및 유효 문서 선택
    processed_docs = []
    valid_indices = []
    for i, title in enumerate(news_df["제목"].tolist()):
        processed = preprocess_text(title)
        if processed.strip():
            processed_docs.append(processed)
            valid_indices.append(i)
    if not processed_docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."}), 400
    news_df = news_df.iloc[valid_indices].reset_index(drop=True)

    # KR‑WordRank 적용: 전체 문서에 대해 단어 점수 계산
    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    _, word_scores, _ = wordrank_extractor.extract(processed_docs, beta=0.85, max_iter=10)

    # 각 문서(기사)의 점수: 문서 내 단어들의 점수 합
    doc_scores = []
    for doc in processed_docs:
        words = doc.split()
        score = sum(word_scores.get(word, 0) for word in words)
        doc_scores.append(score)

    # 상위 20개 기사 선택 (점수 기준 내림차순)
    top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:20]
    top_docs = [processed_docs[i] for i in top_indices]
    top_news = news_df.iloc[top_indices].reset_index(drop=True)

    # TF‑IDF 적용: 선택된 20개 기사에 대해 TF‑IDF 계산
    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform(top_docs)
    feature_names = tfidf_vectorizer.get_feature_names_out()

    results = []
    for idx, row in enumerate(tfidf_matrix):
        row_array = row.toarray()[0]
        # TF‑IDF 점수가 높은 단어 순으로 정렬
        sorted_indices = np.argsort(row_array)[::-1]
        keywords = []
        for term_idx in sorted_indices:
            if row_array[term_idx] > 0:
                keywords.append(feature_names[term_idx])
            if len(keywords) == 3:  # 최대 3개 키워드 추출
                break
        results.append({
            "제목": top_news.iloc[idx]["제목"],
            "링크": top_news.iloc[idx]["링크"],
            "TFIDF 키워드": keywords
        })

    return jsonify(results)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
