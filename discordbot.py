# インストールした discord.py を読み込む
import discord
from main import main
import time
import asyncio
import os
from dotenv import load_dotenv

###マニュアル
#サーバー管理者が「/run_wsr」とチャットするとレポートを作成してくれます
#定時処理はホスト側で実施するつもり

# アクセストークンを読み込む
load_dotenv("environments.env")
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

# Botの起動とDiscordサーバーへの接続
client.run(TOKEN)