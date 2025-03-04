import os
import pandas as pd
import feedparser
import requests
from collections import Counter
import numpy as np
from flask import Flask, jsonify
from flask_cors import CORS
import re, string

# --- Konlpy 및 전처리 관련 코드 ---
from konlpy.tag import Komoran, Hannanum
komoran = Komoran()
hannanum = Hannanum()
with open('불용어.txt', 'r', encoding='utf-8') as f:
    list_file = f.readlines()
stopwords = list_file[0].split(",")

def preprocess(text):
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)
    text = re.sub('\s+', ' ', text)
    text = re.sub(r'\[[0-9]*\]', ' ', text)
    text = re.sub(r'[^\w\s]', ' ', str(text).strip())
    text = re.sub(r'\d', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def final(text):
    n = []
    word = komoran.nouns(text)
    p = komoran.pos(text)
    for pos in p:
        if pos[1] in ['SL']:
            word.append(pos[0])
    for w in word:
        if len(w) > 1 and w not in stopwords:
            n.append(w)
    return " ".join(n)

def finalpreprocess(text):
    return final(preprocess(text))
# --- 끝 ---

app = Flask(__name__)
CORS(app)

API_KEY = os.environ.get("GEMINI_API_KEY")

# CSV 파일을 읽어오는 함수 (프로젝트 루트에 news_df.csv가 있어야 함)
def load_news_csv():
    try:
        news_df = pd.read_csv('news_df.csv')
        return news_df
    except Exception as e:
        print("CSV 파일 읽기 오류:", e)
        return pd.DataFrame()

# /update 엔드포인트: CSV 파일 내용을 반환 (필요시 추가 전처리 가능)
@app.route('/update')
def update():
    news_df = load_news_csv()
    return jsonify(news_df.to_dict(orient='records'))

# /data 엔드포인트: CSV 파일 내용을 그대로 반환
@app.route('/data')
def data():
    news_df = load_news_csv()
    return jsonify(news_df.to_dict(orient='records'))

# /kr-wordrank 엔드포인트: CSV 파일에서 뉴스 데이터 읽고 KR-WordRank로 키워드 추출 후 관련 기사 링크 반환
@app.route('/kr-wordrank')
def kr_wordrank():
    from krwordrank.word import KRWordRank
    beta = 0.85
    max_iter = 10

    news_df = load_news_csv()
    # 제목 리스트 생성 및 전처리 적용
    docs = [finalpreprocess(doc) for doc in news_df["제목"].tolist()]
    wordrank_extractor = KRWordRank(min_count=5, max_length=10, verbose=True)
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)
    # 후처리: 숫자나 대괄호 포함 키워드 제거
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}
    
    # 각 키워드에 대해 해당 키워드가 포함된 첫 번째 기사 링크 찾기
    result = {}
    for k, score in keywords.items():
        matched = news_df[news_df["제목"].str.contains(k, na=False)]
        if not matched.empty:
            link = matched.iloc[0]["링크"]
        else:
            link = ""
        result[k] = {"score": score, "link": link}
    
    print("추출된 KR-WordRank 키워드:", result)
    return jsonify(result)

# /yake 엔드포인트: CSV 파일에서 뉴스 데이터 읽고 YAKE로 키워드 추출 후 관련 기사 링크 반환
@app.route('/yake')
def yake_endpoint():
    import yake
    language = "ko"
    max_ngram_size = 1
    numOfKeywords = 20

    news_df = load_news_csv()
    docs = news_df["제목"].tolist()
    combined_text = " ".join(docs)
    kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, top=numOfKeywords, features=None)
    keywords_list = kw_extractor.extract_keywords(combined_text)
    
    result = {}
    for kw, score in keywords_list:
        matched = news_df[news_df["제목"].str.contains(kw, na=False)]
        if not matched.empty:
            link = matched.iloc[0]["링크"]
        else:
            link = ""
        result[kw] = {"score": score, "link": link}
    
    print("추출된 YAKE 키워드:", result)
    return jsonify(result)

@app.route('/')
def root():
    return "Flask API Server - Use /update, /data, /kr-wordrank, or /yake."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
