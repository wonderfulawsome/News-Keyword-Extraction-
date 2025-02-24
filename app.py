import os
import psycopg2
import pandas as pd
import feedparser
import requests
from collections import Counter
import numpy as np
from flask import Flask, jsonify
from flask_cors import CORS  # CORS 추가

app = Flask(__name__)
CORS(app)  # CORS 활성화 (모든 도메인 허용)

API_KEY = os.environ.get("GEMINI_API_KEY")

def get_db_connection():
    """PostgreSQL 연결."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    conn = psycopg2.connect(db_url)
    return conn

def update_database():
    """RSS 수집 → 키워드 추출 → TOPSIS 계산 → DB 업데이트."""
    # 1. RSS 목록
    rss_list = [
        {"언론사": "mk뉴스", "rss_url": "https://www.mk.co.kr/rss/30000001/"},
        {"언론사": "한경", "rss_url": "https://www.hankyung.com/feed/economy"},
        {"언론사": "연합뉴스", "rss_url": "https://www.yonhapnewseconomytv.com/rss/clickTop.xml"},
        {"언론사": "jtbc", "rss_url": "https://news-ex.jtbc.co.kr/v1/get/rss/section/20"},
        {"언론사": "조선일보", "rss_url": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml"},
        {"언론사": "경향신문", "rss_url": "https://www.khan.co.kr/rss/rssdata/economy_news.xml"},
        {"언론사": "아시아경제", "rss_url": "https://www.asiae.co.kr/rss/stock.htm"}
    ]
    rss_df = pd.DataFrame(rss_list)

    def parse_rss(url):
        feed = feedparser.parse(url)
        entries = []
        for entry in feed.entries:
            entries.append({
                "제목": entry.title,
                "링크": entry.link,
                "발행일": entry.get("published", None)
            })
        return entries

    all_news = []
    for _, row in rss_df.iterrows():
        source = row["언론사"]
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)

    # 2. 뉴스 키워드 추출 (예: 첫 번째 뉴스만)
    def extract_keywords(title, api_key):
        """Gemini API 활용해 키워드 추출."""
        if not api_key:
            # API 키가 없으면 None 반환
            return None

        prompt = f"다음 뉴스 제목에서 핵심 키워드를 100개 추출해줘. 키워드 추출후, 어떠한 말도 하지마.: {title}"
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ]
        }
        response = requests.post(api_url, headers=headers, json=payload)
        if response.status_code == 200:
            result = response.json()
            try:
                keywords = result["candidates"][0]["content"]["parts"][0]["text"]
                return keywords.strip()
            except (KeyError, IndexError) as e:
                print("응답 파싱 오류:", e, result)
                return None
        else:
            print("API 호출 실패:", response.status_code, response.text)
            return None

    if not news_df.empty:
        sample_title = news_df.iloc[0]["제목"]
        extracted_keywords = extract_keywords(sample_title, API_KEY)
        news_df.loc[0, '추출키워드'] = extracted_keywords

    # 3. 키워드 빈도 집계
    frequency_counter = Counter()
    for _, row in news_df.iterrows():
        kws = row.get("추출키워드")
        if isinstance(kws, str):
            keywords = [k.strip() for k in kws.split(',')]
            for kw in keywords:
                frequency_counter[kw] += 1

    # 4. TOPSIS 평가 (frequency만)
    kw_df = pd.DataFrame(list(frequency_counter.items()), columns=['keyword', 'frequency'])
    if kw_df.empty:
        return kw_df

    norm_matrix = kw_df[['frequency']].apply(lambda x: x / np.sqrt((x**2).sum()))
    ideal_best = norm_matrix.max()
    ideal_worst = norm_matrix.min()
    d_best = np.sqrt(((norm_matrix - ideal_best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((norm_matrix - ideal_worst) ** 2).sum(axis=1))
    epsilon = 1e-10
    kw_df['closeness'] = d_worst / (d_best + d_worst + epsilon)
    kw_df.sort_values(by='closeness', ascending=False, inplace=True)
    kw_df.reset_index(drop=True, inplace=True)

    # 5. DB 업데이트
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keyword_ranking (
            id SERIAL PRIMARY KEY,
            keyword TEXT,
            frequency INTEGER,
            closeness REAL
        )
    ''')
    conn.commit()

    cursor.execute("DELETE FROM keyword_ranking")
    conn.commit()

    for _, row in kw_df.iterrows():
        cursor.execute('''
            INSERT INTO keyword_ranking (keyword, frequency, closeness)
            VALUES (%s, %s, %s)
        ''', (row['keyword'], row['frequency'], row['closeness']))
    conn.commit()
    cursor.close()
    conn.close()

    return kw_df

@app.route('/update')
def update():
    """수동으로 DB 갱신"""
    updated_df = update_database()
    return jsonify(updated_df.to_dict(orient='records'))

@app.route('/data')
def data():
    """DB에서 랭킹 정보 조회"""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM keyword_ranking", conn)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

@app.route('/')
def root():
    """루트에 접근했을 때 - HTML 서빙 없이 간단한 안내만 표시"""
    update_database()  # 데이터 업데이트
    return "Flask API Server - No HTML served here."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
