FROM python:3.9-slim

# 시스템 업데이트 및 OpenJDK 11 설치
RUN apt-get update && \
    apt-get install -y openjdk-11-jdk && \
    apt-get clean

# JAVA_HOME 환경변수 설정
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH=$PATH:$JAVA_HOME/bin

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
