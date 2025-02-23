import os
import sqlite3
import pandas as pd
import feedparser
import requests
from collections import Counter
import numpy as np
from flask import Flask, render_template, jsonify

# 현재 디렉토리의 templates 폴더를 사용 (프로젝트 구조: my-flask-app/ 아래에 app.py와 templates 폴더 존재)
app = Flask(__name__, template_folder="templates")

# API 키: 환경변수에서 가져오거나, 테스트용 기본값 사용 (반드시 실제 API 키로 교체하세요)
API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")

def update_database():
    # 1. RSS 데이터 수집
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
    for idx, row in rss_df.iterrows():
        source = row["언론사"]
        url = row["rss_url"]
        news_items = parse_rss(url)
        for item in news_items:
            item["언론사"] = source
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)
    
    # 2. 뉴스 키워드 추출 (예시: 첫 번째 뉴스 제목에 대해 실행)
    def extract_keywords(title, api_key):
        prompt = f"다음 뉴스 제목에서 핵심 키워드를 100개 추출해줘. 키워드 추출후, 어떠한 말도 하지마.: {title}"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [
                {"parts": [{"text": prompt}]}
            ]
        }
        response = requests.post(url, headers=headers, json=payload)
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

    # 3. 키워드 빈도 집계 (추출키워드 컬럼)
    frequency_counter = Counter()
    for idx, row in news_df.iterrows():
        kws = row.get("추출키워드")
        if isinstance(kws, str):
            keywords = [k.strip() for k in kws.split(',')]
            for kw in keywords:
                frequency_counter[kw] += 1

    # 4. TOPSIS 평가 (빈도수 기준)
    kw_df = pd.DataFrame(list(frequency_counter.items()), columns=['keyword', 'frequency'])
    criteria = ['frequency']
    norm_matrix = kw_df[criteria].apply(lambda x: x / np.sqrt((x**2).sum()))
    ideal_best = norm_matrix.max()
    ideal_worst = norm_matrix.min()
    d_best = np.sqrt(((norm_matrix - ideal_best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((norm_matrix - ideal_worst) ** 2).sum(axis=1))
    epsilon = 1e-10
    kw_df['closeness'] = d_worst / (d_best + d_worst + epsilon)
    kw_df.sort_values(by='closeness', ascending=False, inplace=True)
    kw_df.reset_index(drop=True, inplace=True)
    
    # 5. SQLite DB 업데이트 (test.db)
    conn = sqlite3.connect('test.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS keyword_ranking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT,
        frequency INTEGER,
        closeness REAL
    )
    ''')
    # 기존 데이터 삭제
    cursor.execute("DELETE FROM keyword_ranking")
    conn.commit()
    
    for idx, row in kw_df.iterrows():
        cursor.execute('''
        INSERT INTO keyword_ranking (keyword, frequency, closeness)
        VALUES (?, ?, ?)
        ''', (row['keyword'], row['frequency'], row['closeness']))
    conn.commit()
    conn.close()
    
    return kw_df

@app.route('/update')
def update():
    # 파이프라인 실행 및 DB 업데이트 후 결과를 JSON으로 반환
    updated_df = update_database()
    return jsonify(updated_df.to_dict(orient='records'))

@app.route('/data')
def data():
    # SQLite DB에서 데이터를 읽어 JSON 반환
    conn = sqlite3.connect('test.db')
    df = pd.read_sql_query("SELECT * FROM keyword_ranking", conn)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

@app.route('/')
def index():
    # 웹페이지 접근 시 DB 업데이트 후 index.html 렌더링
    update_database()
    return render_template('index.html')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
