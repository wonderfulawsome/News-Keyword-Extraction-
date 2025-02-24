FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .  # app.py 등 소스파일을 복사 (index.html은 없어도 됨)

EXPOSE 5000

CMD ["python", "app.py"]
