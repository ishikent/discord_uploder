import discord
import os
import asyncio
from datetime import datetime
import logging
import re
from discord.ext import tasks
from zoneinfo import ZoneInfo
from keep_alive import keep_alive

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# スレッド情報を格納するリストとロック
schedule_queue = []
thread_lock = asyncio.Lock()

SCHEDULE_CHANNEL_ID = int(os.getenv("YOUR_SCHEDULE_CHANNEL_ID"))  # スレッド予約を受け取るチャンネル
THREAD_CHANNEL_ID   = int(os.getenv("YOUR_THREAD_CHANNEL_ID"))    # 非公開スレッドがあるチャンネル

#この辞書が設定してないとメンションが飛ばせない
subscription_roles = {}
subscription_roles["Basic"]    = 1280744389186162688
subscription_roles["Standard"] = 1285833817013223465

logger.info(f'SCHEDULE_CHANNEL_ID : {SCHEDULE_CHANNEL_ID}')  
logger.info(f'THREAD_CHANNEL_ID : {THREAD_CHANNEL_ID}')  

class Schedule():
    MSG_PATTERN = r"^thread_id@(\d+),publish_date@(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})$"
    DATE_FORMAT = '%Y-%m-%dT%H:%M'
    ZONEINFO = ZoneInfo("Asia/Tokyo")

    def __init__(self, message):
        self.message = message

        match_obj = re.match(Schedule.MSG_PATTERN, self.message.content)

        self.valid_format_flg = False
        if not match_obj:
            return

        try:
            self.thread_id    = int(match_obj.group(1))
            self.publish_time = datetime.strptime(match_obj.group(2), Schedule.DATE_FORMAT).replace(tzinfo=Schedule.ZONEINFO)

            logger.info(f'Scheduled thread: ID={self.thread_id}, Publish Time={self.publish_time}')
        except Exception as e:
            logger.error(f'Error processing message: {e}')

        #指定したスレッドが存在するかチェック
        # (※スケジュールを指定するしてから、予約時までの間に対象スレッドが消される可能性もあるが、まぁそれは考えない)
        thread = client.get_channel(self.get_thread_id())
        if not thread:
            return

        #ここまできて初めてこのインスタンスは有効となる
        self.valid_format_flg = True

    def __lt__(self, other):
        return self.get_time() < other.get_time()

    def get_message(self):
        return self.message

    def get_content(self):
        return self.message.content

    def get_thread_id(self):
        return self.thread_id

    def get_thread(self):
        #公開予定の非公開スレッドを取得
        return client.get_channel(self.get_thread_id())

    def get_time(self):
        return self.publish_time

    #判定系
    def is_valid(self):
        return self.valid_format_flg

    def after_schedule_time(self):
        now = datetime.now(tz=Schedule.ZONEINFO)
        return now >= self.publish_time

    def before_schedule_time(self):
        now = datetime.now(tz=Schedule.ZONEINFO)
        return now < self.publish_time



async def process_message(sch_message):
    logger.info(f'Processing message: {sch_message.get_content()}')

    async with thread_lock:
        schedule_queue.append(sch_message)
        schedule_queue.sort()

    logger.info(f'Scheduled thread: ID={sch_message.get_thread_id()}, Publish Time={sch_message.get_time()}')


@tasks.loop(seconds=1)
async def check_and_publish_thread():

    async with thread_lock:
        #スケジュール未設定
        if not schedule_queue:
            return

        for i,sch in enumerate(schedule_queue):
            print(f"{i}   {sch.get_thread().name}:{sch.get_time()}")

        sch_message = schedule_queue[0]
        #スケジュール時刻前
        if sch_message.before_schedule_time():
            return

        #公開予定の非公開スレッドを取得
        thread = sch_message.get_thread()
        guild = thread.guild
        
        # role = discord.utils.get(thread.guild.roles, id=BASIC_ROLE_ID)
        mentions = ' '.join([role.mention for role in guild.roles if (thread.permissions_for(role).view_channel and role.id in subscription_roles.values())])
        # スレッドにメンション付きでメッセージを送信
        await thread.send(f'{mentions} スレッドが公開されました: {thread.name}')

        schedule_queue.pop(0)

@client.event
async def on_ready():
    logger.info('Bot is ready.')
    check_and_publish_thread.start()

@client.event
async def on_message(message):
    if message.channel.id != SCHEDULE_CHANNEL_ID:
        return

    sch_message = Schedule(message)
    if not sch_message.is_valid() or not sch_message.get_thread():
        await message.add_reaction('❌')
        return
    
    logger.info(f'Received message in schedule channel: {message.content}')
    await sch_message.get_message().add_reaction("👍")
    await process_message(sch_message)


TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
client.run(TOKEN)
