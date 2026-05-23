import urllib.request
import xml.etree.ElementTree as ET
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os

# 🤖 新しい公式パッケージから Client を読み込みます
from google import genai
import os

# 🔑 余計な固定を外し、自動で最適な接続先を選ばせます
client = genai.Client()

app = Flask(__name__)

# 🗄️ データベースの初期設定を行う関数
def init_db():
    # puoppo.db というデータベースファイルに接続します（なければ自動作成されます）
    conn = sqlite3.connect('puoppo.db')
    cursor = conn.cursor()
    # 検索履歴を保存する「history」テーブルを作成します
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# アプリ起動時にデータベースを作成
init_db()

# 🏠 メイン画面（履歴の一覧表示）
@app.route('/')
def index():
    # データベースから保存されている検索履歴をすべて取得します
    conn = sqlite3.connect('puoppo.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, keyword FROM history ORDER BY id DESC')
    history_list = cursor.fetchall() # 履歴をリストとして一括取得
    conn.close()
    
    # 取得した履歴を index.html に渡して表示します
    return render_template('index.html', history=history_list)

# 📥 検索窓から送信されたキーワードを処理し、分析結果画面を表示する
@app.route('/search', methods=['POST'])
def search():
    keyword = request.form.get('keyword')
    
    if not keyword:
        return redirect(url_for('index'))
        
    # 1. 🔍 履歴をデータベースに保存
    conn = sqlite3.connect('puoppo.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO history (keyword) VALUES (?)', (keyword,))
    conn.commit()
    conn.close()
    
    # 2. 📰 以前作成したロジックでRSSからニュースを取得
    # 例として、GoogleニュースのRSSからキーワードに関連する記事を最大100件取得します
    news_titles = []
    try:
        # キーワードをURLエンコードしてGoogleニュースRSSのURLを作成
        encoded_keyword = urllib.parse.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ja&gl=JP&ceid=JP:ja"
        
        # RSSのXMLデータをダウンロードして解析
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            
        root = ET.fromstring(xml_data)
        # XMLから記事のタイトル（title）を抽出
        for item in root.findall('.//item')[:100]:  # 直近100件
            title_text = item.find('title').text
            news_titles.append(title_text)
    except Exception as e:
        print(f"RSS取得エラー: {e}")
        news_titles = ["ニュースデータの取得に失敗しました。"]

    # 3. 🤖 ニュース記事を元にGeminiに世論・不満分析を依頼
    analysis_result = ""
    try:
        # ニュースのタイトルを1つの文章にまとめます
        news_context = "\n".join([f"- {t}" for t in news_titles])
        
        # 以前使用した分析用のプロンプト（指示文）を作成
        prompt = f"""
        あなたは世論および不満トレンドの分析AI「Puoppo（ポッポ）」です。
        以下のキーワードに関する最新ニュースのタイトルを元に、現在の世論の動向や、人々が抱いている「不満・課題」を親しみやすい日本語で分析・要約してください。

        キーワード: {keyword}

        対象ニュース:
        {news_context}

        出力は、箇条書きなどを交えて分かりやすくまとめてください。
        """
        
        # 🤖 確実なモデル名に修正します
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        analysis_result = response.text

    except Exception as e:
        print(f"Gemini APIエラー: {e}")
        analysis_result = "AIによる分析中にエラーが発生しました。APIキーや通信環境を確認してください。"

    # 4. 📄 新しく作る結果画面（result.html）にデータを渡して表示！
    return render_template('result.html', keyword=keyword, result=analysis_result, news=news_titles)


# 🗑️ 検索履歴を削除する処理
@app.route('/delete', methods=['POST'])
def delete_history():
    # 画面側から送られてきた削除したい履歴の「id」を取得します
    history_id = request.form.get('id')
    
    if history_id:
        # データベースに接続し、指定されたidのデータだけを削除（Delete）します
        conn = sqlite3.connect('puoppo.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM history WHERE id = ?', (history_id,))
        conn.commit()
        conn.close()
    
    # 削除が終わったら、メイン画面（初期ページ）に自動で戻ります
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)