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

with open('불용어.txt', 'r', encoding = 'UTF-8') as f:
  list_file = f.readlines() 
stopwords = list_file[0].split(",")
stopwords.append('종합')
stopwords.append('포토')
stopwords.append('영상')
stopwords.append('게시판')
stopwords.append('책마을')
stopwords.append('속보')

# 정규화
def preprocess(text):
    text=text.strip()  
    text=re.compile('<.*?>').sub('', text) 
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)  
    text = re.sub('\s+', ' ', text)  
    text = re.sub(r'\[[0-9]*\]',' ',text) 
    text=re.sub(r'[^\w\s]', ' ', str(text).strip())
    text = re.sub(r'\d',' ',text) 
    text = re.sub(r'\s+',' ',text) 
    return text


# 명사/영단어 추출, 한글자 제외, 불용어 제거
def remove_stopwords(text):
    n = []
    word = komoran.nouns(text)
    p = komoran.pos(text)
    for pos in p:
      if pos[1] in ['SL']:
        word.append(pos[0])
    for w in word:
      if len(w)>1 and w not in stopwords:
        n.append(w)
    return " ".join(n)

# 최종 전처리
def finalpreprocess(text):
  return remove_stopwords(preprocess(text))

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

# 전처리 함수 (HTML 태그, 구두점, 공백, 숫자 제거) – KR-WordRank용
def preprocess(text):
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)  # HTML 태그 제거
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)  # 구두점 제거
    text = re.sub(r'\s+', ' ', text)  # 연속 공백 제거
    text = re.sub(r'\d', ' ', text)     # 숫자 제거
    return text

# Gemini 전용 전처리 함수: HTML 태그, 구두점, 공백만 제거 (숫자는 그대로 유지)
def preprocess_for_gemini(text):
    text = text.strip()
    text = re.compile('<.*?>').sub('', text)
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

# 키워드 추출 함수: Komoran 명사 추출 후 불용어 제거 진행 (KR-WordRank용)
def extract_keywords(text):
    words = komoran.nouns(text)
    words = [w for w in words if len(w) > 1 and w not in stopwords]
    return " ".join(words)

# KR-WordRank용 전처리 함수 (불용어 제거 포함)
def preprocess_text(text):
    return extract_keywords(preprocess(text))

# Gemini API를 호출하여 기사 제목을 요약하는 함수
def get_gemini_summary(text):
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        return " ".join(text.split()[:2])
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-pro:generateContent?key={gemini_api_key}"
    
    # 프롬프트 개선
    payload = {
        "contents": [{
            "parts": [{
                "text": f"""
                "아래 기사 제목들을 문맥적으로 이해하고, 각각을 한국어로 2-3 단어로만 요약해. "
                "다른 문장은 절대 쓰지 말고, 오직 요약만 해줘. "
                "추가 설명이나 부연 문구, 문장부호는 사용하지 마."
                f" : {text}"
                """
            }]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 10,
            "topP": 0.8
        }
    }
    
    headers = {"Content-Type": "application/json"}
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            # 응답 처리 부분 수정
            response_data = response.json()
            if 'candidates' in response_data and len(response_data['candidates']) > 0:
                candidate = response_data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content'] and len(candidate['content']['parts']) > 0:
                    summary = candidate['content']['parts'][0]['text'].strip()
                    return summary
            # 응답 형식이 예상과 다를 경우 기본값 반환
            return " ".join(text.split()[:2])
        else:
            print(f"API 오류: {response.status_code}, {response.text}")
            return " ".join(text.split()[:2])
    except Exception as e:
        print("Gemini API 오류:", e)
        return " ".join(text.split()[:2])


# /kowordrank 엔드포인트: KR-WordRank 적용 후 Gemini API 요약으로 상위 20개 결과 반환
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

    # KR-WordRank에는 숫자 제거 포함 전처리 진행
    docs = [finalpreprocess(title) for title in news_df["제목"].tolist()]
    docs = [d for d in docs if d.strip()]
    if not docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."})

    wordrank_extractor = KRWordRank(min_count=1, max_length=10, verbose=True)
    keywords, word_scores, _ = wordrank_extractor.extract(docs, beta=0.85, max_iter=10)
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    sorted_keywords = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:20]

    result = {}
    for keyword, score in sorted_keywords:
        matched_df = news_df[news_df["제목"].str.contains(keyword, na=False)]
        if not matched_df.empty:
            article_title = matched_df.iloc[0]["제목"]
            # Gemini에는 숫자 제거 없이 HTML, 구두점, 공백만 제거된 텍스트 전달
            processed_title_for_gemini = finalpreprocess(article_title)
            gemini_summary = get_gemini_summary(processed_title_for_gemini)
            link = matched_df.iloc[0]["링크"]
            result[gemini_summary] = {"score": score, "link": link}
        else:
            result[keyword] = {"score": score, "link": ""}
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
