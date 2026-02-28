import sys
import json
import os
import re
import time
from pathlib import Path
import requests
from dotenv import load_dotenv
from google import genai

#main.pyと同じファイルにenvironments.envを置くこと
#ほんで以下の値のkeyvalueを設定すること

#AUTHOR:USER AGENTにつかうよ。あなたのニックネームを入れてね
#EMAIL:USER AGENTにつかうよ。あなたの連絡先を入れてね
#CRED:LOGINにつかうクレデンシャルだよ
#UBI_APP_ID:LOGINにつかうよ。ここは固定値のはずだけど念のため秘匿。openplanetにのってるから知りたきゃ調べてね
#USER AGENT:APIアクセス時の自己紹介だよ
#GOOGLE_API_KEY:Gemini叩くAPIキーだよ
#GOOGLE_API_KEY:Gemini叩くAPIキーだよ
#CLUB_ID:そのまんまだよ。PB取りたいクラブID入れてね
#DISCORD_WEBHOOK_URL:DiscordのWebhook用のURLだよ。投げたいチャンネルのURL発行して入れてね

# --- CONFIGURATION ---
# load_dotoenvはローカル用
#load_dotenv("environments.env")
AUTHOR = os.getenv("AUTHOR")
EMAIL = os.getenv("EMAIL")
CRED = os.getenv("CRED")
UBI_APP_ID = os.getenv("UBI_APP_ID")
USER_AGENT = f"GET CLUB RECORD APP(WIP)/0.1 {AUTHOR} ({EMAIL})"
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
CLUB_ID = os.getenv("CLUB_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# GET Tokens -- トークンとってくるやつ
#週一しか回さないので毎回発行していいと判断
#ほぼ元の関数のまんまだけど、if文とか返り値をシンプルにした

def get_full_authenticate_tokens():
    """Logs into Ubisoft once and gets both Nadeo tokens immediately."""
    print("Performing full authentication for all services...")

    # 1. Login to Ubisoft to get a TICKET (Only do this once!)
    ubi_url = "https://public-ubiservices.ubi.com/v3/profiles/sessions"
    ubi_headers = {
        "Content-Type": "application/json",
        "Ubi-AppId": UBI_APP_ID,
        "Authorization": f"Basic {CRED}",
        "User-Agent": USER_AGENT
    }

    try:
        ubi_res = requests.post(ubi_url, headers=ubi_headers)
        ubi_res.raise_for_status()
        ticket = ubi_res.json().get("ticket")

        # 2. Exchange that same ticket for the LIVE token
        nadeo_url = "https://prod.trackmania.core.nadeo.online/v2/authentication/token/ubiservices"
        nadeo_headers = {"Authorization": f"ubi_v1 t={ticket}", "User-Agent": USER_AGENT}

        live_res = requests.post(nadeo_url, headers=nadeo_headers, json={"audience": "NadeoLiveServices"})
        live_res.raise_for_status()
        live_tokens = live_res.json()
        live_services_token = live_tokens["accessToken"]

        # 3. Use the SAME ticket for the CORE token
        core_res = requests.post(nadeo_url, headers=nadeo_headers, json={"audience": "NadeoServices"})
        core_res.raise_for_status()
        core_tokens = core_res.json()
        services_token = core_tokens["accessToken"]

        return live_services_token,services_token

    except Exception as e:
        print(f"Full Auth failed: {e}")
        return None

# GET WS MAPS -- WSのマップとるやつ、元の関数をそのまま流用
def get_weekly_shorts_maps(access_token, offset=1, length=1):
    """Fetches the weekly shorts and returns a list of map UIDs."""
    url = "https://live-services.trackmania.nadeo.live/api/campaign/weekly-shorts"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    params = {"offset": offset, "length": length}

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        # Get the first campaign in the list
        campaigns = data.get("campaignList", [])
        if not campaigns:
            print("No Weekly Shorts found.")
            return []

        # Extract map UIDs from the playlist
        playlist = campaigns[0].get("playlist", [])
        map_uids = [item.get("mapUid") for item in playlist]
        print(f"Retrieved {len(map_uids)} maps from Weekly Short: {campaigns[0].get('name')}")
        return map_uids
    except Exception as e:
        print(f"Failed to fetch weekly shorts: {e}")
        return []

# GET WS MAPS NAME -- WSのマップの名前とるやつっぽい、よーわかってない、元の関数をそのまま流用
def get_map_names(access_token, map_uids):
    """Fetches map information for a list of UIDs and returns a UID -> Name mapping."""
    if not map_uids: return {}

    # Join UIDs into a comma-separated string
    uid_list_str = ",".join(map_uids)
    url = f"https://prod.trackmania.core.nadeo.online/maps/by-uid/?mapUidList={uid_list_str}"
    headers = {"Authorization": f"nadeo_v1 t={access_token}", "User-Agent": USER_AGENT}
    # params = {"mapUidList": uid_list_str}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        map_data = response.json()

        # Create a dictionary where key is mapUid and value is the map name
        # We strip the Trackmania formatting codes (like $i, $fff, etc.) if desired
        return {m.get('mapUid'): m.get('name') for m in map_data if m.get('mapUid')}
    except Exception as e:
        print(f"Failed to fetch map names: {e}")
        return {}

# GET WS MAPS NAME -- WSのマップの名前をきれいにするやつっぽい、これもよーわかってない、元の関数をそのまま流用
def clean_trackmania_name(name):
    """
    Removes Trackmania color and style codes from a string.
    Example: '$i$s2 - $f90Sovereign' -> '2 - Sovereign'
    """
    if not name:
        return name
    # This regex finds a '$' followed by:
    # 1. Three hex characters (color)
    # 2. Or a single character like i, s, o, w, n, m, g, z, etc.
    # 3. Or a '$' (escaped dollar sign)
    return re.sub(r'\$([0-9a-fA-F]{3}|[iIswntgzjGLS<>]|[oO]|\$)', '', name)

# GET CLUB RECORDS -- 本チャンの関数、以下を追加
# ・プレイヤー名をtrackmania.ioから取得する関数を追加
# 　→for entry in topsの中にプレイヤー名とidを判定するロジックを追加
# ・Geminiに投げるプロンプトを詰め込む配列/ロジックを追加

def get_club_pb(access_token, club_id, map_uid, map_name):
    """
    Fetches the leaderboard for club members on a specific map.
    Using 'Personal_Best' as the groupUid for global PBs.
    """
    # 先にクラブメンバー一覧取得する
    memberlist = get_club_members_io(club_id)

    # Geminiに投げるプロンプト元
    tmp_prompt = []

    # Parameters
    group_uid = "Personal_Best"
    length = 100  # Top 100 members
    offset = 0

    url = f"https://live-services.trackmania.nadeo.live/api/token/leaderboard/group/{group_uid}/map/{map_uid}/club/{club_id}/top"

    headers = {
        "Authorization": f"nadeo_v1 t={access_token}",
        "User-Agent": USER_AGENT
    }

    params = {
        "length": length,
        "offset": offset
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        # 'top' usually returns a list of records
        tops = data.get("top", [])
        if tops:
            print(f"\n--- Club Leaderboard for Map: {map_name} ---")
            tmp_prompt.append(f"\n--- Club Leaderboard for Map: {map_name} ---")
            for entry in tops:
                # Time is usually in milliseconds
                time_ms = entry.get('score')
                seconds = (time_ms / 1000) if time_ms else 0
                userid = entry.get('accountId')
                for i in range(len(memberlist)):
                    if memberlist[i][0] == userid:
                        username = memberlist[i][1]
                        break

                # time.sleep(1)
                print(f"Pos: {entry.get('position')} | {username} | Time: {seconds:.3f}s")
                tmp_prompt.append(f"Pos: {entry.get('position')} | {username} | Time: {seconds:.3f}s")
            return tops,tmp_prompt
        else:
            print("No club records found for this map.")
            return []

    except Exception as e:
        print(f"Failed to fetch leaderboard: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"Response: {e.response.text}")
        return None

# GET CLUB MEMBERS NAME -- ioからメンバーの名前とるよ
def get_club_members_io(club_id):
    """
    Fetches member details from the Trackmania.io API.
    Note: This is a community API, not an official Nadeo one.
    """
    # Trackmania.io prefers a descriptive User-Agent
    memberlist = []

    io_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json"
    }

    url = f"https://trackmania.io/api/club/{club_id}/members/0"
    memberjson = requests.get(url,headers=io_headers)
    memberjson = memberjson.json()
    for i in range(len(memberjson["members"])):
        #デバッグ用
        # print(memberjson["members"][i]["player"])
        # print(memberjson["members"][i]["player"]["name"])
        # print(memberjson["members"][i]["player"]["id"])

        tmp_name_and_id = [memberjson["members"][i]["player"]["id"],memberjson["members"][i]["player"]["name"]]
        memberlist.append(tmp_name_and_id)

    #print(memberlist)
    return(memberlist)

# MAIN APP -- メインの関数だよ。こいつをdiscordbot.pyから叩くよ。
# トークンとる->PBとる->結果をGeminiにレポートさせる、みたいな感じ

def main():
    # This is the token you use for your actual game data requests
    live_services_token,services_token = get_full_authenticate_tokens()
    print(f"Access Token Ready: {live_services_token[:15]}...")
    map_uids = get_weekly_shorts_maps(live_services_token, offset=1, length=1)

    # 2. Bulk fetch map names
    map_names_map = get_map_names(services_token, map_uids)

    #追加 プロンプト詰め込み用の配列
    prompt = []

    # 3. Loop and display PBs with Names
    for uid in map_uids:
        # Use the dictionary to find the name, fall back to UID if not found
        raw_name = map_names_map.get(uid, uid)
        friendly_name = clean_trackmania_name(raw_name)
        tops,tmp_prompt = get_club_pb(live_services_token, CLUB_ID, uid, friendly_name)
        prompt += tmp_prompt
    
    prompt = " ".join(prompt)
    summary_template_md = Path("summary_template.md").read_text(encoding="utf-8")
    client = genai.Client(api_key=GOOGLE_API_KEY)

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview", contents=f"""
            以下は今週開催されたTrackmania Weekly Shortsのクラブ内リザルトと、レポートフォーマットです。
            内容を理解した上で、md形式のレポートのみを出力してください。（出力しました。などの報告は不要です）
            
            出力レポートの具体的な指示は以下です。
            ・GPT_SUMMARY:全体傾向や各プレイヤーに触れた前向きなサマリ
            　→1行20文字~100文字の2行、体言止めかつ勢いのある感じ
            ・GPT_MVP_SUMMARY:MVPプレイヤーとその理由
            　→20文字~50文字で1行、祝福ムード
            ・Overall:プレイヤーが1位を取った回数を集計し記載してください
            　→ひとこと:1~3位のプレイヤーに20文字程度でモチベーションアップのひとことを記載してください

            【リザルト】
            {prompt}
            【ランキングレポート（Markdown）】
            {summary_template_md}
            """)
        
        #Geminiレスポンスの型取得、たまにtextで帰ってこないらしい
        text = getattr(response, "text", None)

        if not text:
            return "Geminiから有効なレスポンスが返らなかったよ。"
        
        print(response.text)
        return response.text
    
    except Exception as e:
        print(f"Failed to kick gemini: {e}")
        return f"Geminiのレポート作成でこけちゃったよ。時間がたったらもう一度試してね: {e}"

#SEND Discord channel
def send_to_discord(message):
    data = {"content": message}
    resp = requests.post(DISCORD_WEBHOOK_URL+"?wait=true", json=data)
    return resp

#直接このPythonファイル実行したとき用の処理だよ。for cron job / WEBHOOK
if __name__ == '__main__':
    try:
        resp = send_to_discord("WSレポート処理中です…⏳")
        msg_id = resp.json()["id"]

        #メイン処理
        result = main()

        # 処理中ですを消す
        requests.delete(f"{DISCORD_WEBHOOK_URL}/messages/{msg_id}")

        #出力
        send_to_discord(result)
        sys.exit(0)

    except Exception as E:
        send_to_discord("なんかエラーでてるので強制終了します")
        sys.exit(0)