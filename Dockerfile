FROM python:3.9-slim

# 시스템 업데이트 및 OpenJDK 17 (headless) 설치
RUN apt-get update && \
    apt-get install -y openjdk-17-jdk-headless && \
    apt-get clean

# JAVA_HOME 환경변수 설정 (Debian Bookworm의 경우)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$PATH:$JAVA_HOME/bin

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
