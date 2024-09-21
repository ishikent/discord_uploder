import discord
import os
import asyncio
from keep_alive import keep_alive
from datetime import datetime
import logging


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = discord.Client(intents=discord.Intents.default())

# スレッド情報を格納するリスト
scheduled_threads = []

# チャンネルIDの設定

SCHEDULE_CHANNEL_ID = os.getenv("YOUR_SCHEDULE_CHANNEL_ID")  # スレッド予約を受け取るチャンネル
THREAD_CHANNEL_ID   = os.getenv("YOUR_THREAD_CHANNEL_ID")    # 非公開スレッドがあるチャンネル

logger.info(f'SCHEDULE_CHANNEL_ID : {SCHEDULE_CHANNEL_ID}')  # メッセージの内容をログ出力
logger.info(f'THREAD_CHANNEL_ID : {THREAD_CHANNEL_ID}')  # メッセージの内容をログ出力

async def process_message(message):
    logger.info(f'Processing message: {message.content}') 

    # メッセージ内容をパース
    content = message.content
    try:
        thread_id, publish_time_str = content.split(',')
        thread_id = int(thread_id.split(':')[1])
        publish_time = datetime.strptime(publish_time_str.split(':')[1].strip(), '%Y-%m-%d %H:%M')

        # リストに追加し、ソート
        scheduled_threads.append((thread_id, publish_time))
        scheduled_threads.sort(key=lambda x: x[1])  # 時刻順にソート
        await message.delete()  # メッセージを削除

        logger.info(f'Scheduled thread: ID={thread_id}, Publish Time={publish_time}')
    except Exception as e:
        logger.error(f'Error processing message: {e}')  # エラーログ

async def check_and_publish_thread():
    await client.wait_until_ready()  # Botが準備完了するまで待つ

    while not client.is_closed():
        now = discord.utils.utcnow()  # UTCタイムゾーンの現在時刻を取得

        if not scheduled_threads:
            continue

        # 予定時刻を過ぎた最初のスレッドを公開
        thread_id, publish_time = scheduled_threads[0]
        if now >= publish_time:
            channel = client.get_channel(THREAD_CHANNEL_ID)  # 非公開スレッドのチャンネルIDを指定
            thread = await channel.fetch_thread(thread_id)

            if thread and thread.archived:
                await thread.edit(archived=False)  # スレッドを公開
                logger.info(f'Published thread: {thread.name}')  # スレッド公開をログ出力

            scheduled_threads.pop(0)  # リストから削除
            await asyncio.sleep(30)  # スレッド公開後は1秒待機

        await asyncio.sleep(30)  # 1秒ごとにチェック

@client.event
async def on_ready():
    logger.info('Bot is ready.')  # ボットが準備完了した時のログ
    client.loop.create_task(check_and_publish_thread())  # スレッドの公開チェックを開始

@client.event
async def on_message(message):
    # メッセージが予約投稿チャンネルからのものであれば処理
    if message.channel.id == SCHEDULE_CHANNEL_ID:  # 予約投稿チャンネルIDを指定
        logger.info(f'Received message in schedule channel: {message.content}')
        emoji = "🙏" 
        await message.add_reaction(emoji)
        await process_message(message)

TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
client.run(TOKEN)
