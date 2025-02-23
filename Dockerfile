# Python 3.9 slim 이미지 사용
FROM python:3.9-slim

# 작업 디렉토리 설정
WORKDIR /app

# 패키지 설치를 위한 requirements.txt 복사 및 설치
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 소스 코드 전체 복사
COPY . .

# 컨테이너에서 Flask 앱 실행 (5000번 포트)
CMD ["python", "api/app.py"]