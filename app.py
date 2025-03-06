import os
import re
import string
import feedparser
import pandas as pd
import psycopg2
from flask import Flask, jsonify, request
from flask_cors import CORS

# --- Konlpy 및 전처리 관련 코드 ---
from konlpy.tag import Komoran, Hannanum

komoran = Komoran()
hannanum = Hannanum()

with open('불용어.txt', 'r', encoding='utf-8') as f:
    list_file = f.readlines()
stopwords = list_file[0].split(",")

def preprocess(text):
    text = text.strip()
    # HTML 태그 제거
    text = re.compile('<.*?>').sub('', text)
    # 모든 구두점 이스케이프
    text = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text)
    # 연속 공백 하나로 축소
    text = re.sub(r'\s+', ' ', text)
    # 대괄호, 숫자 등 제거
    text = re.sub(r'\[[0-9]*\]', ' ', text)
    text = re.sub(r'[^\w\s]', ' ', str(text).strip())
    text = re.sub(r'\d', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def final(text):
    """Komoran 명사 추출 + 불용어 제거"""
    n = []
    word = komoran.nouns(text)
    p = komoran.pos(text)
    # 영어(외래어) SL 태그도 추가
    for pos_item in p:
        if pos_item[1] == 'SL':
            word.append(pos_item[0])
    for w in word:
        if len(w) > 1 and w not in stopwords:
            n.append(w)
    return " ".join(n)

def finalpreprocess(text):
    return final(preprocess(text))
# --- 끝 ---

app = Flask(__name__)
CORS(app)

# ----------------- DB 연결 및 갱신 로직 (예시) ------------------
def get_db_connection():
    """PostgreSQL DB 연결 (Render 등에서 DATABASE_URL 환경 변수를 사용)"""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    conn = psycopg2.connect(db_url)
    return conn

def update_database():
    """예시용: RSS 몇 개를 파싱 후, DB의 keyword_ranking 테이블을 생성/갱신하는 함수."""
    rss_list = [
        {"언론사": "mk뉴스", "rss_url": "https://www.mk.co.kr/rss/30000001/"},
        {"언론사": "한경", "rss_url": "https://www.hankyung.com/feed/economy"}
    ]
    all_news = []

    def parse_rss(url):
        feed = feedparser.parse(url)
        entries = []
        for entry in feed.entries:
            entries.append({
                "제목": entry.title if hasattr(entry, 'title') else '',
                "링크": entry.link if hasattr(entry, 'link') else '',
                "발행일": entry.get("published", None)
            })
        return entries

    # RSS 파싱
    for item in rss_list:
        parsed = parse_rss(item["rss_url"])
        all_news.extend(parsed)

    news_df = pd.DataFrame(all_news)
    if news_df.empty:
        return pd.DataFrame()

    # DB에 연결, 테이블이 없으면 생성
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS keyword_ranking (
            id SERIAL PRIMARY KEY,
            keyword TEXT,
            frequency INTEGER,
            closeness REAL
        )
    """)
    conn.commit()

    # 테이블 비우기 (예시)
    cur.execute("DELETE FROM keyword_ranking")
    conn.commit()

    # 예시로 첫 번째 행의 제목을 삽입
    if not news_df.empty:
        first_title = news_df.iloc[0]["제목"]
        cur.execute("""
            INSERT INTO keyword_ranking (keyword, frequency, closeness)
            VALUES (%s, %s, %s)
        """, (first_title, 1, 0.5))
        conn.commit()

    cur.close()
    conn.close()
    return news_df

@app.route('/update')
def update():
    """DB 업데이트 후, 갱신 결과(뉴스 목록)를 JSON으로 반환"""
    updated_df = update_database()
    return jsonify(updated_df.to_dict(orient='records'))

@app.route('/data')
def data():
    """DB의 keyword_ranking 테이블을 JSON으로 반환"""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM keyword_ranking", conn)
    conn.close()
    return jsonify(df.to_dict(orient='records'))
# --------------------------------------------------------


# ----------------- KoWordRank RSS 분석 -------------------
RSS_FEEDS = {
    "전체": [
        "https://news.sbs.co.kr/news/headlineRssFeed.do?plink=RSSREADER"
    ],
    "정치": [
        "https://www.yna.co.kr/rss/politics.xml"
    ],
    "경제": [
        "https://www.yna.co.kr/rss/economy.xml"
    ],
    "사회": [
        "https://www.yna.co.kr/rss/society.xml"
    ],
    "세계": [
        "https://www.yna.co.kr/rss/international.xml"
    ],
    "문화": [
        "https://www.yna.co.kr/rss/culture.xml"
    ],
    "연예": [
        "https://www.yna.co.kr/rss/entertainment.xml"
    ],
    "스포츠": [
        "https://www.yna.co.kr/rss/sports.xml"
    ]
}

def parse_rss(url):
    feed = feedparser.parse(url)
    entries = []
    for entry in feed.entries:
        entries.append({
            "제목": entry.title if hasattr(entry, 'title') else '',
            "링크": entry.link if hasattr(entry, 'link') else '',
            "발행일": entry.get("published", None)
        })
    return entries

@app.route('/kowordrank')
def kowordrank_endpoint():
    """ KoWordRank로 카테고리별 키워드 추출: min_count=1, max_length=5 """
    from krwordrank.word import KRWordRank

    category = request.args.get("category", "전체")
    if category not in RSS_FEEDS:
        return jsonify({"error": f"잘못된 카테고리: {category}"}), 400

    # 카테고리의 RSS URL 파싱
    rss_urls = RSS_FEEDS[category]
    all_news = []
    for url in rss_urls:
        all_news.extend(parse_rss(url))

    news_df = pd.DataFrame(all_news)
    if news_df.empty or "제목" not in news_df.columns:
        return jsonify({"error": "RSS에서 제목을 가져오지 못했습니다."}), 400

    # 전처리 후 문서 리스트
    docs = [finalpreprocess(t) for t in news_df["제목"].tolist()]
    docs = [d for d in docs if d.strip() != ""]
    if not docs:
        return jsonify({"error": "전처리 후 문서가 없습니다."})

    # KoWordRank 파라미터 변경: min_count=1, max_length=5
    beta = 0.85
    max_iter = 10
    wordrank_extractor = KRWordRank(min_count=1, max_length=5, verbose=True)

    # 키워드 추출
    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)

    # 숫자나 '[' 같은 특수문자 키워드는 제외 (필요 시)
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    # 기사 링크 매핑
    result = {}
    for k, score in keywords.items():
        matched_df = news_df[news_df["제목"].str.contains(k, na=False)]
        link = matched_df.iloc[0]["링크"] if not matched_df.empty else ""
        result[k] = {"score": score, "link": link}

    print(f"[KoWordRank: {category}] 추출된 키워드:", result)
    return jsonify(result)
# --------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
