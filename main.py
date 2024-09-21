import discord
import os
import asyncio
from keep_alive import keep_alive
from datetime import datetime
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

client = discord.Client(intents=discord.Intents.default())

# スレッド情報を格納するリストとロック
scheduled_threads = []
thread_lock = asyncio.Lock()

SCHEDULE_CHANNEL_ID = int(os.getenv("YOUR_SCHEDULE_CHANNEL_ID"))  # スレッド予約を受け取るチャンネル
THREAD_CHANNEL_ID   = int(os.getenv("YOUR_THREAD_CHANNEL_ID"))    # 非公開スレッドがあるチャンネル

logger.info(f'SCHEDULE_CHANNEL_ID : {SCHEDULE_CHANNEL_ID}')  
logger.info(f'THREAD_CHANNEL_ID : {THREAD_CHANNEL_ID}')  

pattern = r"^thread_id@(\d+),publish_date@(\d{4}-\d{2}-\d{2} \d{2}:\d{2})$"

async def process_message(message):
    logger.info(f'Processing message: {message.content}') 

    content = message.content
    match_obj = re.match(pattern, content)

    if match_obj:
        try:
            thread_id = int(match_obj.group(1))
            publish_time = datetime.strptime(match_obj.group(2), '%Y-%m-%d %H:%M')

            async with thread_lock:
                scheduled_threads.append((thread_id, publish_time))
                scheduled_threads.sort(key=lambda x: x[1])  
                await message.delete()  

            logger.info(f'Scheduled thread: ID={thread_id}, Publish Time={publish_time}')
        except Exception as e:
            logger.error(f'Error processing message: {e}')

async def check_and_publish_thread():
    await client.wait_until_ready()  

    while not client.is_closed():
        now = discord.utils.utcnow()  

        async with thread_lock:
            if not scheduled_threads:
                await asyncio.sleep(1)
                continue

            thread_id, publish_time = scheduled_threads[0]
            if now >= publish_time:
                channel = client.get_channel(THREAD_CHANNEL_ID)  
                thread = await channel.fetch_thread(thread_id)

                if thread and thread.archived:
                    await thread.edit(archived=False)  
                    logger.info(f'Published thread: {thread.name}')  

                scheduled_threads.pop(0)  
        
        await asyncio.sleep(1)  

@client.event
async def on_ready():
    logger.info('Bot is ready.')  
    # client.loop.create_task(check_and_publish_thread())  

@client.event
async def on_message(message):
    if message.channel.id != SCHEDULE_CHANNEL_ID:  
        return

    if not re.match(pattern, message.content):
        await message.add_reaction('❌')  
        return
    
    logger.info(f'Received message in schedule channel: {message.content}')
    await message.add_reaction("🙏") 
    await process_message(message)

TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
client.run(TOKEN)
