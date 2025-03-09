import os
import re
import string
import feedparser
import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from konlpy.tag import Komoran
from krwordrank.word import KRWordRank
from keybert import KeyBERT

app = Flask(__name__)
CORS(app)

komoran = Komoran()
# RoBERTa 기반 KeyBERT 모델 로드
kw_model = KeyBERT(model="roberta-base")

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

# 공통 클리닝 함수: HTML 태그, 구두점, 공백, 숫자 제거 (키워드 추출용)
def clean_text(text):
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\d', ' ', text)
    return text

# Komoran을 이용한 명사 추출 및 불용어 제거 (KR‑WordRank용)
def preprocess_text(text):
    cleaned = clean_text(text)
    words = komoran.nouns(cleaned)
    words = [w for w in words if len(w) > 1 and w not in stopwords]
    return " ".join(words)

# RoBERTa 기반 KeyBERT를 이용한 키워드 추출 함수
def extract_keywords_roberta(text, top_n=2):
    try:
        # keyphrase_ngram_range=(1,2) 옵션으로 1~2그램 키워드를 추출
        keywords = kw_model.extract_keywords(
            text,
            keyphrase_ngram_range=(1, 2),
            stop_words=stopwords,
            top_n=top_n
        )
        keywords = [kw for kw, score in keywords]
        # 만약 추출된 키워드 개수가 top_n 미만이면 fallback으로 Komoran 명사 추출
        if len(keywords) < top_n:
            komoran_keywords = komoran.nouns(text)
            komoran_keywords = [kw for kw in komoran_keywords if len(kw) > 1 and kw not in stopwords]
            keywords = (keywords + komoran_keywords)[:top_n]
        return keywords
    except Exception as e:
        print(f"RoBERTa 키워드 추출 오류: {e}")
        return []

# /kowordrank 엔드포인트:
# 1. 각 기사 제목에 대해 preprocess_text를 이용해 전처리한 후, KR‑WordRank로 전역 단어 점수를 산출
# 2. 각 기사별로 전처리된 텍스트에 포함된 토큰의 점수를 합산하여 기사 점수를 계산
# 3. 점수 내림차순 상위 20개 기사를 선정하고, 각 기사마다 RoBERTa(KeyBERT)로 2개 키워드 추출
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

    # 각 기사에 대해 KR‑WordRank 전용 전처리 진행
    proc_texts = [preprocess_text(title) for title in news_df["제목"].tolist()]
    proc_texts = [doc for doc in proc_texts if doc.strip()]
    if not proc_texts:
        return jsonify({"error": "전처리 후 문서가 없습니다."})

    # KR‑WordRank로 전체 문서에서 단어별 점수 산출
    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    global_keywords, _, _ = wordrank_extractor.extract(proc_texts, beta=0.85, max_iter=10)
    global_keywords = {k: v for k, v in global_keywords.items() if not re.search(r'\d|\[', k)}

    # 각 기사별 점수 계산: 전처리된 텍스트 내 토큰의 global_keywords 점수 합산
    article_scores = []
    for doc in proc_texts:
        score = 0
        for token in doc.split():
            if token in global_keywords:
                score += global_keywords[token]
        article_scores.append(score)
    news_df['score'] = article_scores

    # 점수 내림차순 정렬 후 상위 20개 기사 선택
    top20 = news_df.sort_values(by='score', ascending=False).head(20)

    result = []
    for _, row in top20.iterrows():
        title = row["제목"]
        link = row["링크"]
        score = row["score"]
        # RoBERTa 기반 키워드 추출: 원본 텍스트를 클리닝한 후 사용
        cleaned_title = clean_text(title)
        keywords = extract_keywords_roberta(cleaned_title, top_n=2)
        result.append({
            "제목": title,
            "링크": link,
            "score": float(score),
            "키워드": keywords
        })

    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
