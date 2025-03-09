import os
import re
import string
import feedparser
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from konlpy.tag import Komoran
from krwordrank.word import KRWordRank
import yake

app = Flask(__name__)
CORS(app)

komoran = Komoran()

# 불용어 로드: 파일에서 쉼표로 구분된 단어 읽고 strip()
with open('불용어.txt', 'r', encoding='utf-8') as f:
    raw_text = f.read()
raw_stopwords = raw_text.split(',')
stopwords = [w.strip() for w in raw_stopwords if w.strip()]

# 추가 제거할 불용어
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

# Komoran을 이용한 명사 추출 후 불용어 제거
def extract_keywords(text):
    words = komoran.nouns(text)
    words = [w for w in words if len(w) > 1 and w not in stopwords]
    return " ".join(words)

def preprocess_text(text):
    return extract_keywords(preprocess(text))

# /kowordrank 엔드포인트: 
# 1. 모든 기사 제목을 전처리하여 docs 리스트 생성
# 2. KR‑WordRank로 전체 문서에서 키워드 점수 산출
# 3. 각 기사별로 전처리된 텍스트에 포함된 토큰의 점수를 합산하여 기사 점수 산출
# 4. 점수 내림차순 상위 20개 기사 선택 후, 각 기사에 대해 YAKE로 2개 키워드 추출
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

    # 전처리된 기사 제목 리스트 (docs)와 각 기사의 원문 저장
    docs = []
    for title in news_df["제목"].tolist():
        proc = preprocess_text(title)
        docs.append(proc)
    
    # KR‑WordRank 적용: 전체 문서에서 키워드와 점수 산출
    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    global_keywords, _, _ = wordrank_extractor.extract(docs, beta=0.85, max_iter=10)
    # 불필요한 패턴 필터링
    global_keywords = {k: v for k, v in global_keywords.items() if not re.search(r'\d|\[', k)}

    # 각 기사별로 KR‑WordRank 점수(전처리된 텍스트에 포함된 토큰의 합산) 계산
    article_scores = []
    for doc in docs:
        score = 0
        tokens = doc.split()
        for token in tokens:
            if token in global_keywords:
                score += global_keywords[token]
        article_scores.append(score)
    news_df['score'] = article_scores

    # 점수 내림차순 정렬 후 상위 20개 기사 선택
    top20 = news_df.sort_values(by='score', ascending=False).head(20)

    # YAKE 설정: 한국어, n-gram 최대 2, 상위 2개 키워드 추출
    kw_extractor = yake.KeywordExtractor(lan="ko", n=2, top=2)
    result = []
    for _, row in top20.iterrows():
        title = row["제목"]
        link = row["링크"]
        score = row["score"]
        # 각 기사에 대해 전처리된 텍스트 생성
        proc_text = preprocess_text(title)
        # YAKE 키워드 추출 (리스트: [(키워드, 점수), ...])
        yake_keywords = kw_extractor.extract_keywords(proc_text)
        # 키워드만 리스트로 추출 (필요시 점수도 포함 가능)
        keywords = [kw for kw, _ in yake_keywords]
        result.append({
            "제목": title,
            "링크": link,
            "score": score,
            "키워드": keywords
        })

    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
