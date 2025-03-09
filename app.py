import os
import re
import string
import feedparser
import pandas as pd
import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
from konlpy.tag import Komoran
import gensim
from gensim import corpora
from gensim.models import LdaModel

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

def extract_nouns(text):
    words = komoran.nouns(text)
    words = [w for w in words if len(w) > 1 and w not in stopwords]
    return words

def preprocess_text(text):
    return extract_nouns(preprocess(text))

# LDA 모델을 사용하여 토픽 추출
@app.route('/lda_topics')
def lda_topics_endpoint():
    category = request.args.get("category", "전체")
    num_topics = int(request.args.get("num_topics", 5))  # 기본 토픽 수
    
    if category not in RSS_FEEDS:
        return jsonify({"error": f"잘못된 카테고리: {category}"}), 400

    rss_urls = RSS_FEEDS[category]
    all_news = []
    for url in rss_urls:
        all_news.extend(parse_rss(url))

    news_df = pd.DataFrame(all_news)
    if news_df.empty or "제목" not in news_df.columns:
        return jsonify({"error": "RSS에서 제목을 가져오지 못했습니다."}), 400
    
    # 최대 20개 기사만 선택
    news_df = news_df.head(20)
    
    # 각 기사 제목에서 명사 추출
    processed_docs = [preprocess_text(title) for title in news_df["제목"].tolist()]
    
    # 빈 문서 제거
    valid_indices = [i for i, doc in enumerate(processed_docs) if doc]
    valid_docs = [processed_docs[i] for i in valid_indices]
    valid_news = news_df.iloc[valid_indices].reset_index(drop=True)
    
    if not valid_docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."})
    
    # 사전 생성
    dictionary = corpora.Dictionary(valid_docs)
    
    # 문서-단어 행렬 생성
    corpus = [dictionary.doc2bow(doc) for doc in valid_docs]
    
    # LDA 모델 학습
    lda_model = LdaModel(
        corpus=corpus,
        id2word=dictionary,
        num_topics=num_topics,
        random_state=100,
        update_every=1,
        chunksize=10,
        passes=10,
        alpha='auto',
        per_word_topics=True
    )
    
    # 각 기사의 주요 토픽 추출
    result = []
    for i, (doc_bow, news) in enumerate(zip(corpus, valid_news.itertuples())):
        # 문서의 토픽 분포 계산
        doc_topics = lda_model.get_document_topics(doc_bow)
        # 확률이 높은 순으로 정렬
        doc_topics = sorted(doc_topics, key=lambda x: x[1], reverse=True)
        
        # 상위 2개 토픽 선택
        top_topics = doc_topics[:2] if len(doc_topics) >= 2 else doc_topics
        
        # 각 토픽의 주요 키워드 추출
        topic_keywords = []
        for topic_id, prob in top_topics:
            keywords = lda_model.show_topic(topic_id, topn=5)
            topic_keywords.append({
                "topic_id": int(topic_id),
                "probability": float(prob),
                "keywords": [{"word": word, "weight": float(weight)} for word, weight in keywords]
            })
        
        # 결과에 추가
        result.append({
            "id": i,
            "title": news.제목,
            "link": news.링크,
            "topics": topic_keywords
        })
    
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
