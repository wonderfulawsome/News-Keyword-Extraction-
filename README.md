# 📰 Gemini 뉴스 키워드 요약 시스템

한국경제 RSS를 활용하여 뉴스 제목에서 핵심 키워드를 추출하고,  
Gemini API를 통해 요약된 키워드를 제공하는 Flask 기반 API 프로젝트

## 📁 파일 구성

| 파일명            | 설명 |
|------------------|------|
| `app.py`         | Flask 서버 실행 및 주요 기능 구현 파일 |
| `Dockerfile`     | Docker 이미지 생성을 위한 설정 파일 |
| `requirements.txt` | 필요한 Python 패키지 목록 |
| `불용어.txt`      | 분석 시 제외할 불용어 리스트 파일 |

---

## 🔧 주요 기능

- ✅ 한국경제 RSS 뉴스 크롤링
- ✅ 텍스트 정제 및 명사 추출 (Komoran 사용)
- ✅ 불용어 제거 및 KR-WordRank 기반 키워드 추출
- ✅ Google Gemini API로 뉴스 제목 요약
- ✅ REST API로 결과 반환

---

## 🚀 실행 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
