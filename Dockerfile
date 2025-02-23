# Python 3.9 slim 이미지 사용
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

CMD ["python", "app.py"]