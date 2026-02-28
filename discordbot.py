# インストールした discord.py を読み込む
import discord
from main import main
import time
import asyncio
import os
from dotenv import load_dotenv
from flask import Flask
import threading

###マニュアル
#サーバー管理者が「/run_wsr」とチャットするとレポートを作成してくれます
#定時処理はホスト側で実施するつもり

# アクセストークンを読み込む
# load_dotoenvはローカル用
#load_dotenv("environments.env")
TOKEN = os.getenv("DISCORDBOT_API_KEY")

# 接続に必要なオブジェクトを生成
intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

# 起動時に動作する処理
@client.event
async def on_ready():
    # 起動したらターミナルにログイン通知が表示される
    print('ログインしました')

# メッセージ受信時に動作する処理
@client.event
async def on_message(message):
    # メッセージ送信者が管理者か判定
    if message.author.guild_permissions.administrator:
        # 「/run_wsr」と発言したらレポートを発行
        if message.content == '/run_wsr':
            await message.channel.send("処理中です…⏳")
            resp = await asyncio.to_thread(main)
            await message.channel.send(resp)
    else:
        return
    
# -------------------
# Ping 用 Flask サーバー Renderのスリープ防ぐ用のエンドポイント
# -------------------
app = Flask(__name__)

@app.route("/ping")
def ping():
    return "alive", 200  # Ping用エンドポイント

# Flask を別スレッドで起動
def run_flask():
    port = int(os.getenv("PORT", 10000))  # Render が割り当てる PORT 環境変数を使う
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()

# -------------------
# Discord Bot 起動
# -------------------

# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)