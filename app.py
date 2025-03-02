import os
import psycopg2
import pandas as pd
import feedparser
import requests
from collections import Counter
import numpy as np
from flask import Flask, jsonify
from flask_cors import CORS  # CORS 추가
import re

# 전처리 함수: 대괄호 안 내용과 숫자 제거
def preprocess(text):
    text = re.sub(r'\[[^\]]*\]', '', text)  # 대괄호 안의 내용 제거
    text = re.sub(r'\d+', '', text)          # 숫자 제거
    return text.strip()

app = Flask(__name__)
CORS(app)  # 모든 도메인 허용

API_KEY = os.environ.get("GEMINI_API_KEY")

def get_db_connection():
    """PostgreSQL 연결."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    conn = psycopg2.connect(db_url)
    return conn

# feed_specs.csv 파일의 모든 항목을 코드 내에 직접 포함
feed_specs = [
    {"publisher": "寃쏀뼢?좊Ц", "title": "?꾩껜?댁뒪", "categories": "_all_", "url": "https://www.khan.co.kr/rss/rssdata/total_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "?뺤튂", "categories": "politics", "url": "https://www.khan.co.kr/rss/rssdata/politic_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "寃쎌젣", "categories": "economy", "url": "https://www.khan.co.kr/rss/rssdata/economy_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "?ы쉶", "categories": "society", "url": "https://www.khan.co.kr/rss/rssdata/society_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "援?젣", "categories": "international", "url": "https://www.khan.co.kr/rss/rssdata/kh_world.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "?ㅽ룷痢?sports", "categories": "", "url": "http://www.khan.co.kr/rss/rssdata/kh_sports.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "臾명솕", "categories": "culture", "url": "https://www.khan.co.kr/rss/rssdata/culture_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "?곗삁", "categories": "entertainment", "url": "https://www.khan.co.kr/rss/rssdata/kh_entertainment.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "IT", "categories": "tech|science", "url": "http://www.khan.co.kr/rss/rssdata/it_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "?ㅽ뵾?덉뼵", "categories": "column", "url": "https://www.khan.co.kr/rss/rssdata/opinion_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "?몃Ъ", "categories": "people", "url": "https://www.khan.co.kr/rss/rssdata/people_news.xml"},
    {"publisher": "寃쏀뼢?좊Ц", "title": "?앺솢/?덉?", "categories": "culture", "url": "https://www.khan.co.kr/rss/rssdata/skentertain_news.xml"},
    {"publisher": "援???쇰낫", "title": "?꾩껜湲곗궗", "categories": "_all_", "url": "http://rss.kmib.co.kr/data/kmibRssAll.xml"},
    {"publisher": "援???쇰낫", "title": "?뺤튂", "categories": "politics", "url": "http://rss.kmib.co.kr/data/kmibPolRss.xml"},
    {"publisher": "援???쇰낫", "title": "寃쎌젣", "categories": "economy", "url": "http://rss.kmib.co.kr/data/kmibEcoRss.xml"},
    {"publisher": "援???쇰낫", "title": "?ы쉶", "categories": "society", "url": "http://rss.kmib.co.kr/data/kmibSocRss.xml"},
    {"publisher": "援???쇰낫", "title": "援?젣", "categories": "international", "url": "http://rss.kmib.co.kr/data/kmibIntRss.xml"},
    {"publisher": "援???쇰낫", "title": "?ㅽ룷痢?sports", "categories": "", "url": "http://rss.kmib.co.kr/data/kmibSpoRss.xml"},
    {"publisher": "援???쇰낫", "title": "臾명솕", "categories": "culture", "url": "http://rss.kmib.co.kr/data/kmibCulRss.xml"},
    {"publisher": "援???쇰낫", "title": "?앺솢", "categories": "culture", "url": "http://rss.kmib.co.kr/data/kmibLifRss.xml"},
    {"publisher": "援???쇰낫", "title": "?ъ꽕/移쇰읆", "categories": "column", "url": "http://rss.kmib.co.kr/data/kmibColRss.xml"},
    {"publisher": "?댁떆??援?젣", "title": "international", "categories": "", "url": "https://newsis.com/RSS/international.xml"},
    {"publisher": "?댁떆??湲덉쑖", "title": "economy", "categories": "", "url": "https://newsis.com/RSS/bank.xml"},
    {"publisher": "?댁떆???ы쉶", "title": "society", "categories": "", "url": "https://newsis.com/RSS/society.xml"},
    {"publisher": "?댁떆???ㅽ룷痢?sports", "title": "", "categories": "", "url": "https://newsis.com/RSS/sports.xml"},
    {"publisher": "?댁떆??臾명솕", "title": "culture", "categories": "", "url": "https://newsis.com/RSS/culture.xml"},
    {"publisher": "?댁떆???뺤튂", "title": "politics", "categories": "", "url": "https://newsis.com/RSS/politics.xml"},
    {"publisher": "?댁떆??寃쎌젣", "title": "economy", "categories": "", "url": "https://newsis.com/RSS/economy.xml"},
    {"publisher": "?댁떆???곗뾽", "title": "economy", "categories": "", "url": "https://newsis.com/RSS/industry.xml"},
    {"publisher": "?댁떆??IT/諛붿씠??tech|science", "title": "", "categories": "", "url": "https://newsis.com/RSS/health.xml"},
    {"publisher": "?댁떆???곗삁", "title": "entertainment", "categories": "", "url": "https://newsis.com/RSS/entertain.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?꾩껜湲곗궗", "categories": "_all_", "url": "https://rss.donga.com/total.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?뺤튂", "categories": "politics", "url": "https://rss.donga.com/politics.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?ы쉶", "categories": "society", "url": "https://rss.donga.com/national.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "寃쎌젣", "categories": "economy", "url": "https://rss.donga.com/economy.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "援?젣", "categories": "international", "url": "https://rss.donga.com/international.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?ъ꽕移쇰읆", "categories": "column", "url": "https://rss.donga.com/editorials.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?섑븰怨쇳븰", "categories": "medical|science", "url": "https://rss.donga.com/science.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "臾명솕?곗삁", "categories": "culture|entertainment", "url": "https://rss.donga.com/culture.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?ㅽ룷痢?sports", "categories": "", "url": "https://rss.donga.com/sports.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?щ엺?띿쑝濡?people", "categories": "", "url": "https://rss.donga.com/inmul.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "嫄닿컯", "categories": "health", "url": "https://rss.donga.com/health.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?덉졇", "categories": "culture", "url": "https://rss.donga.com/leisure.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?꾩꽌", "categories": "culture", "url": "https://rss.donga.com/book.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "怨듭뿰", "categories": "culture", "url": "https://rss.donga.com/show.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?ъ꽦", "categories": "women", "url": "https://rss.donga.com/woman.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?ы뻾", "categories": "culture", "url": "https://rss.donga.com/travel.xml"},
    {"publisher": "?숈븘?쇰낫", "title": "?앺솢?뺣낫", "categories": "culture", "url": "https://rss.donga.com/lifeinfo.xml"},
    {"publisher": "?댁??쇰낫", "title": "?꾩껜", "categories": "_all_", "url": "https://www.ddanzi.com/rss"},
    {"publisher": "留ㅼ씪?몃룞?댁뒪", "title": "?꾩껜", "categories": "_all_", "url": "https://www.labortoday.co.kr/rss/allArticle.xml"},
    {"publisher": "誘몃뵒?댁삤???꾩껜湲곗궗", "title": "_all_", "categories": "", "url": "https://www.mediatoday.co.kr/rss/allArticle.xml"},
    {"publisher": "誘몃뵒?댁삤???뺤튂", "title": "politics", "categories": "", "url": "https://www.mediatoday.co.kr/rss/S1N2.xml"},
    {"publisher": "誘몃뵒?댁삤??寃쎌젣", "title": "economy", "categories": "", "url": "https://www.mediatoday.co.kr/rss/S1N3.xml"},
    {"publisher": "誘몃뵒?댁삤???ы쉶", "title": "society", "categories": "", "url": "https://www.mediatoday.co.kr/rss/S1N4.xml"},
    {"publisher": "誘몃뵒?댁삤??臾명솕", "title": "culture", "categories": "", "url": "https://www.mediatoday.co.kr/rss/S1N5.xml"},
    {"publisher": "誘몃뵒?댁삤??援?젣", "title": "international", "categories": "", "url": "https://www.mediatoday.co.kr/rss/S1N6.xml"},
    {"publisher": "誘몃뵒?댁삤??IT", "title": "tech|science", "categories": "", "url": "https://www.mediatoday.co.kr/rss/S1N7.xml"},
    {"publisher": "誘몃뵒?댁삤???ㅽ뵾?덉뼵", "title": "column", "categories": "", "url": "https://www.mediatoday.co.kr/rss/S1N8.xml"},
    {"publisher": "?쒖슱?좊Ц", "title": "?뺤튂", "categories": "politics", "url": "https://www.seoul.co.kr/xml/rss/rss_politics.xml"},
    {"publisher": "?쒖슱?좊Ц", "title": "?ы쉶", "categories": "society", "url": "https://www.seoul.co.kr/xml/rss/rss_society.xml"},
    {"publisher": "?쒖슱?좊Ц", "title": "寃쎌젣", "categories": "economy", "url": "https://www.seoul.co.kr/xml/rss/rss_economy.xml"},
    {"publisher": "?쒖슱?좊Ц", "title": "援?젣", "categories": "international", "url": "https://www.seoul.co.kr/xml/rss/rss_international.xml"},
    {"publisher": "?쒖슱?좊Ц", "title": "臾명솕/嫄닿컯", "categories": "culture|health", "url": "https://www.seoul.co.kr/xml/rss/rss_life.xml"},
    {"publisher": "?쒖슱?좊Ц", "title": "?ㅽ룷痢?sports", "categories": "", "url": "https://www.seoul.co.kr/xml/rss/rss_sports.xml"},
    {"publisher": "?쒖슱?좊Ц", "title": "?곗삁", "categories": "entertainment", "url": "https://www.seoul.co.kr/xml/rss/rss_entertainment.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "?꾩껜?댁뒪", "categories": "_all_", "url": "http://www.segye.com/Articles/RSSList/segye_recent.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "?뺤튂", "categories": "politics", "url": "http://www.segye.com/Articles/RSSList/segye_politic.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "寃쎌젣", "categories": "economy", "url": "http://www.segye.com/Articles/RSSList/segye_economy.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "?ы쉶", "categories": "society", "url": "http://www.segye.com/Articles/RSSList/segye_society.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "援?젣", "categories": "international", "url": "http://www.segye.com/Articles/RSSList/segye_international.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "臾명솕", "categories": "culture", "url": "http://www.segye.com/Articles/RSSList/segye_culture.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "?ㅽ뵾?덉뼵", "categories": "column", "url": "http://www.segye.com/Articles/RSSList/segye_opinion.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "?곗삁", "categories": "entertainment", "url": "http://www.segye.com/Articles/RSSList/segye_entertainment.xml"},
    {"publisher": "?멸퀎?쇰낫", "title": "?ㅽ룷痢?sports", "categories": "politics", "url": "http://www.segye.com/Articles/RSSList/segye_sports.xml"},
    {"publisher": "?쒖궗???꾩껜湲곗궗", "title": "_all_", "categories": "", "url": "https://www.sisain.co.kr/rss/allArticle.xml"},
    {"publisher": "?쒖궗???뺤튂", "title": "politics", "categories": "", "url": "https://www.sisain.co.kr/rss/S1N6.xml"},
    {"publisher": "?쒖궗??寃쎌젣", "title": "economy", "categories": "", "url": "https://www.sisain.co.kr/rss/S1N7.xml"},
    {"publisher": "?쒖궗???ы쉶", "title": "society", "categories": "", "url": "https://www.sisain.co.kr/rss/S1N8.xml"},
    {"publisher": "?쒖궗??臾명솕", "title": "culture", "categories": "", "url": "https://www.sisain.co.kr/rss/S1N9.xml"},
    {"publisher": "?쒖궗???쇱씠??culture", "title": "", "categories": "", "url": "https://www.sisain.co.kr/rss/S1N10.xml"},
    {"publisher": "?쒖궗??援?젣/?쒕컲??international", "title": "", "categories": "", "url": "https://www.sisain.co.kr/rss/S1N11.xml"},
    {"publisher": "?쒖궗???명꽣酉??ㅽ뵾?덉뼵", "title": "column", "categories": "", "url": "https://www.sisain.co.kr/rss/S1N12.xml"},
    {"publisher": "?쒖궗????꾩껜湲곗궗", "title": "_all_", "categories": "", "url": "http://www.sisajournal.com/rss/allArticle.xml"},
    {"publisher": "?쒖궗????ы쉶", "title": "society", "categories": "", "url": "http://www.sisajournal.com/rss/S1N47.xml"},
    {"publisher": "?쒖궗???寃쎌젣", "title": "economy", "categories": "", "url": "http://www.sisajournal.com/rss/S1N54.xml"},
    {"publisher": "?쒖궗???LIFE", "title": "culture", "categories": "", "url": "http://www.sisajournal.com/rss/S1N56.xml"},
    {"publisher": "?쒖궗???OPINION", "title": "column", "categories": "", "url": "http://www.sisajournal.com/rss/S1N57.xml"},
    {"publisher": "?쒖궗????뺤튂", "title": "politics", "categories": "", "url": "http://www.sisajournal.com/rss/S1N58.xml"},
    {"publisher": "?쒖궗???援?젣", "title": "international", "categories": "", "url": "http://www.sisajournal.com/rss/S1N59.xml"},
    {"publisher": "?쒖궗???Health", "title": "health", "categories": "", "url": "http://www.sisajournal.com/rss/S2N106.xml"},
    {"publisher": "?쒖궗???Culture", "title": "culture", "categories": "", "url": "http://www.sisajournal.com/rss/S2N107.xml"},
    {"publisher": "?먯씠釉붾돱???꾩껜湲곗궗", "title": "_all_", "categories": "", "url": "https://www.ablenews.co.kr/rss/allArticle.xml"},
    {"publisher": "?먯씠釉붾돱???뺣낫?몄긽", "title": "tech|science", "categories": "", "url": "https://www.ablenews.co.kr/rss/S1N1.xml"},
    {"publisher": "?먯씠釉붾돱???ㅽ뵾?덉뼵", "title": "column", "categories": "", "url": "https://www.ablenews.co.kr/rss/S1N2.xml"},
    {"publisher": "?먯씠釉붾돱???몃룞/寃쎌젣", "title": "economy", "categories": "", "url": "https://www.ablenews.co.kr/rss/S1N4.xml"},
    {"publisher": "?먯씠釉붾돱??臾명솕/泥댁쑁", "title": "culture|sports", "categories": "", "url": "https://www.ablenews.co.kr/rss/S1N8.xml"},
    {"publisher": "?먯씠釉붾돱???몃Ъ/?⑥껜", "title": "people", "categories": "", "url": "https://www.ablenews.co.kr/rss/S1N9.xml"},
    {"publisher": "?먯씠釉붾돱???뺤튂/?뺤콉", "title": "politics", "categories": "", "url": "https://www.ablenews.co.kr/rss/S1N11.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?꾩껜湲곗궗", "categories": "_all_", "url": "http://www.womennews.co.kr/rss/allArticle.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?뺤튂", "categories": "politics", "url": "http://www.womennews.co.kr/rss/S1N1.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?ы쉶", "categories": "society", "url": "http://www.womennews.co.kr/rss/S1N2.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?멸퀎", "categories": "international", "url": "http://www.womennews.co.kr/rss/S1N3.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "寃쎌젣", "categories": "economy", "url": "http://www.womennews.co.kr/rss/S1N4.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "臾명솕", "categories": "culture", "url": "http://www.womennews.co.kr/rss/S1N6.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?앺솢", "categories": "culture", "url": "http://www.womennews.co.kr/rss/S1N7.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?ㅽ뵾?덉뼵", "categories": "column", "url": "http://www.womennews.co.kr/rss/S1N12.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?ㅽ룷痢?sports", "categories": "", "url": "http://www.womennews.co.kr/rss/S1N15.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "?곗삁", "categories": "entertainment", "url": "http://www.womennews.co.kr/rss/S1N16.xml"},
    {"publisher": "?ъ꽦?좊Ц", "title": "IT/怨쇳븰", "categories": "tech|science", "url": "http://www.womennews.co.kr/rss/S1N39.xml"},
    {"publisher": "?쇰떎", "title": "?꾩껜", "categories": "_all_", "url": "https://www.ildaro.com/rss/rss_news.php"},
    {"publisher": "議곗꽑?쇰낫", "title": "?꾩껜湲곗궗", "categories": "_all_", "url": "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "?뺤튂", "categories": "politics", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "寃쎌젣", "categories": "economy", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "?ы쉶", "categories": "society", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/national/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "援?젣", "categories": "international", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/international/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "臾명솕/?쇱씠??culture", "categories": "", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/culture-life/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "?ㅽ뵾?덉뼵", "categories": "column", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "?ㅽ룷痢?sports", "categories": "", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/sports/?outputType=xml"},
    {"publisher": "議곗꽑?쇰낫", "title": "?곗삁", "categories": "entertainment", "url": "https://www.chosun.com/arc/outboundfeeds/rss/category/entertainments/?outputType=xml"},
    {"publisher": "泥쒖??쇰낫", "title": "?꾩껜湲곗궗", "categories": "_all_", "url": "https://cdn.newscj.com/rss/gns_allArticle.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "?뺤튂", "categories": "politics", "url": "https://cdn.newscj.com/rss/gns_S1N1.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "寃쎌젣", "categories": "economy", "url": "https://cdn.newscj.com/rss/gns_S1N2.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "?ы쉶", "categories": "society", "url": "https://cdn.newscj.com/rss/gns_S1N3.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "臾명솕", "categories": "culture", "url": "https://cdn.newscj.com/rss/gns_S1N6.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "?ㅽ룷痢?sports", "categories": "", "url": "https://cdn.newscj.com/rss/gns_S1N14.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "?곗삁", "categories": "entertainment", "url": "https://cdn.newscj.com/rss/gns_S1N15.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "援?젣", "categories": "international", "url": "https://cdn.newscj.com/rss/gns_S1N4.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "?ㅽ뵾?덉뼵", "categories": "column", "url": "https://cdn.newscj.com/rss/gns_S1N5.xml"},
    {"publisher": "泥쒖??쇰낫", "title": "?곕튃嫄닿컯", "categories": "health", "url": "https://cdn.newscj.com/rss/gns_S1N16.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "?꾩껜湲곗궗", "categories": "_all_", "url": "https://www.tongilnews.com/rss/allArticle.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "?⑤턿愿怨?politics|international", "categories": "", "url": "https://www.tongilnews.com/rss/S1N4.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "遺곷?愿怨?politics|international", "categories": "", "url": "https://www.tongilnews.com/rss/S1N5.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "?뺣??뺣떦", "categories": "politics", "url": "https://www.tongilnews.com/rss/S1N6.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "?댁쇅?숉룷", "categories": "international", "url": "https://www.tongilnews.com/rss/S1N7.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "?ㅽ뵾?덉뼵", "categories": "column", "url": "https://www.tongilnews.com/rss/S1N9.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "?듭씪臾명솕", "categories": "culture", "url": "https://www.tongilnews.com/rss/S1N10.xml"},
    {"publisher": "?듭씪?댁뒪", "title": "?숇턿?꾩쇅??international", "categories": "", "url": "https://www.tongilnews.com/rss/S1N18.xml"},
    {"publisher": "?꾨젅?쒖븞", "title": "理쒖떊 湲곗궗", "categories": "_all_", "url": "https://www.pressian.com/api/v3/site/rss/news"},
    {"publisher": "?꾨젅?쒖븞", "title": "?멸퀎", "categories": "international", "url": "https://www.pressian.com/api/v3/site/rss/section/65"},
    {"publisher": "?꾨젅?쒖븞", "title": "?뺤튂", "categories": "politics", "url": "https://www.pressian.com/api/v3/site/rss/section/66"},
    {"publisher": "?꾨젅?쒖븞", "title": "寃쎌젣", "categories": "economy", "url": "https://www.pressian.com/api/v3/site/rss/section/67"},
    {"publisher": "?꾨젅?쒖븞", "title": "?ы쉶", "categories": "society", "url": "https://www.pressian.com/api/v3/site/rss/section/68"},
    {"publisher": "?꾨젅?쒖븞", "title": "臾명솕", "categories": "culture", "url": "https://www.pressian.com/api/v3/site/rss/section/69"},
    {"publisher": "?꾨젅?쒖븞", "title": "?ㅽ룷痢?sports", "categories": "", "url": "https://www.pressian.com/api/v3/site/rss/section/70"},
    {"publisher": "?쒓꺼?덉떊臾??꾩껜湲곗궗", "title": "_all_", "categories": "", "url": "https://www.hani.co.kr/rss/"},
    {"publisher": "?쒓꺼?덉떊臾??뺤튂", "title": "politics", "categories": "", "url": "https://www.hani.co.kr/rss/politics/"},
    {"publisher": "?쒓꺼?덉떊臾?寃쎌젣", "title": "economy", "categories": "", "url": "https://www.hani.co.kr/rss/economy/"},
    {"publisher": "?쒓꺼?덉떊臾??ы쉶", "title": "society", "categories": "", "url": "https://www.hani.co.kr/rss/society/"},
    {"publisher": "?쒓꺼?덉떊臾?援?젣", "title": "international", "categories": "", "url": "https://www.hani.co.kr/rss/international/"},
    {"publisher": "?쒓꺼?덉떊臾??以묐Ц??entertainment|culture", "title": "", "categories": "", "url": "https://www.hani.co.kr/rss/culture/"},
    {"publisher": "?쒓꺼?덉떊臾??ㅽ룷痢?sports", "title": "", "categories": "", "url": "https://www.hani.co.kr/rss/sports/"},
    {"publisher": "?쒓꺼?덉떊臾?怨쇳븰", "title": "science", "categories": "", "url": "https://www.hani.co.kr/rss/science/"},
    {"publisher": "?쒓꺼?덉떊臾??ъ꽕/移쇰읆", "title": "column", "categories": "", "url": "https://www.hani.co.kr/rss/opinion/"},
    {"publisher": "?쒓꺼?덉떊臾?留뚰솕留뚰룊", "title": "cartoon", "categories": "", "url": "https://www.hani.co.kr/rss/cartoon/"}
]

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

def update_database():
    """RSS 수집 → 기존 방식의 키워드 추출 → TOPSIS 계산 → DB 업데이트."""
    all_news = []
    for feed in feed_specs:
        source = feed["publisher"]
        feed_url = feed["url"]
        news_items = parse_rss(feed_url)
        for item in news_items:
            item["publisher"] = source
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)

    # (여기서 Gemini API를 통한 키워드 추출 및 TOPSIS 평가 후 DB 업데이트 로직 삽입)
    # 이 함수는 TOPSIS 평가 결과를 DB에 업데이트하고, 그 결과(kw_df)를 반환합니다.
    # (관련 코드는 생략)
    return pd.DataFrame()  # placeholder

@app.route('/update')
def update():
    updated_df = update_database()
    return jsonify(updated_df.to_dict(orient='records'))

@app.route('/data')
def data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM keyword_ranking", conn)
    conn.close()
    return jsonify(df.to_dict(orient='records'))

# KR-WordRank를 사용하여 키워드 추출하는 엔드포인트
@app.route('/kr-wordrank')
def kr_wordrank():
    from krwordrank.word import KRWordRank

    beta = 0.85
    max_iter = 10

    all_news = []
    for feed in feed_specs:
        source = feed["publisher"]
        feed_url = feed["url"]
        news_items = parse_rss(feed_url)
        for item in news_items:
            item["publisher"] = source
        all_news.extend(news_items)
    news_df = pd.DataFrame(all_news)

    # 뉴스 제목 리스트 생성 후 전처리 적용
    docs = [preprocess(doc) for doc in news_df["제목"].tolist()]

    wordrank_extractor = KRWordRank(
        min_count=5,
        max_length=10,
        verbose=True
    )

    keywords, word_scores, graph = wordrank_extractor.extract(docs, beta, max_iter)

    # 후처리: 불필요한 패턴(숫자, 대괄호) 제거
    keywords = {k: v for k, v in keywords.items() if not re.search(r'\d|\[', k)}

    print("추출된 키워드:", keywords)
    return jsonify(keywords)

@app.route('/')
def root():
    return "Flask API Server - No HTML served here. Use /data, /update, or /kr-wordrank."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
