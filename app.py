import os
import pandas as pd
import feedparser
import requests
from flask import Flask, jsonify, request
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

# /yake 엔드포인트: 쿼리 파라미터 'category'에 따라 해당 CSV 파일에서 뉴스 데이터를 읽고 YAKE로 키워드 추출
@app.route('/yake')
def yake_endpoint():
    import yake
    language = "ko"
    max_ngram_size = 1
    numOfKeywords = 20  # 상위 20개 키워드 추출

    category = request.args.get("category", "전체")
    filename = f"{category}.csv"
    try:
        news_df = pd.read_csv(filename, encoding='utf-8-sig')
    except Exception as e:
        return jsonify({"error": f"{filename} 파일을 읽을 수 없습니다.", "detail": str(e)})

    # 전체 뉴스 제목을 하나의 텍스트로 결합
    docs = news_df["제목"].tolist()
    combined_text = " ".join(docs)
    kw_extractor = yake.KeywordExtractor(lan=language, n=max_ngram_size, top=numOfKeywords, features=None)
    keywords_list = kw_extractor.extract_keywords(combined_text)
    
    result = {}
    for kw, score in keywords_list:
        # re.escape()를 사용해 키워드 내 특수문자를 이스케이프 처리
        try:
            matched = news_df[news_df["제목"].str.contains(re.escape(kw), na=False)]
        except Exception as ex:
            matched = pd.DataFrame()  # 에러 발생 시 빈 DataFrame 처리
        if not matched.empty:
            link = matched.iloc[0]["링크"]
        else:
            link = ""
        result[kw] = {"score": score, "link": link}
    
    print(f"추출된 YAKE 키워드 ({category}):", result)
    return jsonify(result)

@app.route('/')
def root():
    return "Flask API Server - Use /yake?category=전체, 정치, 경제, 사회, 세계, 문화, 연예, 스포츠."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
