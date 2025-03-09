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

# /kowordrank 엔드포인트: 전체 기사에 대해 KR‑WordRank를 적용한 후,
# 각 기사별로 전처리된 텍스트에서 global score 기준 상위 2개 키워드를 추출
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

    # 전체 기사에 대해 전처리된 텍스트 리스트 생성
    docs = [preprocess_text(title) for title in news_df["제목"].tolist()]
    docs = [d for d in docs if d.strip()]
    if not docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."})

    # 전체 문서를 대상으로 KR‑WordRank 적용 (min_count=1, max_length=10)
    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    keywords, word_scores, _ = wordrank_extractor.extract(docs, beta=0.85, max_iter=10)
    # 숫자나 대괄호 포함 키워드 제거
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    # 각 기사별로 전처리된 텍스트에서 global score 기준 키워드 2개 선택
    result = []
    for idx, row in news_df.iterrows():
        title = row["제목"]
        link = row["링크"]
        processed = preprocess_text(title)
        words = processed.split()
        # 해당 기사에서 global KR‑WordRank 결과에 포함된 단어 후보 선별
        candidates = [(w, word_scores[w]) for w in words if w in word_scores]
        # score 기준 내림차순 정렬 후 상위 2개 키워드 선택
        candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
        top_keywords = [w for w, score in candidates][:2]
        result.append({"제목": title, "키워드": top_keywords, "링크": link})
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
