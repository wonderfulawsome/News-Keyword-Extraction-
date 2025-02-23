from flask import Flask, render_template, jsonify
import sqlite3
import pandas as pd

app = Flask(__name__)

def get_keyword_data():
    # SQLite 데이터베이스(test.db)에 연결하여 데이터 읽기
    conn = sqlite3.connect('test.db')
    df = pd.read_sql_query("SELECT * FROM keyword_ranking", conn)
    conn.close()
    return df

@app.route('/data')
def data():
    # 데이터프레임을 JSON 형식으로 반환 (각 행은 딕셔너리)
    df = get_keyword_data()
    return jsonify(df.to_dict(orient='records'))

@app.route('/')
def index():
    # index.html 템플릿 렌더링
    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True)
