# main.py

import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import json
from datetime import datetime, timezone
import webserver

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.all()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="~~", intents=intents)
# Keep default help command

# ---------------- Config ----------------
CONFIG_FILE = "config.json"
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"auto_delete": {}, "autorole": None, "grape_gifs": [], "member_numbers": {}}, f)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

# ---------------- Permissions ----------------
FULL_ACCESS_ROLE = "bot-admin"
LQ_ACCESS_ROLE = "lq-access"
HOLDER_ROLE = "holder"

def has_role(member, role_name):
    return discord.utils.get(member.roles, name=role_name) is not None

def is_allowed(ctx, command_type):
    if command_type == "full":
        return has_role(ctx.author, FULL_ACCESS_ROLE)
    if command_type == "lq":
        return has_role(ctx.author, LQ_ACCESS_ROLE) or has_role(ctx.author, FULL_ACCESS_ROLE)
    if command_type == "grape":
        return has_role(ctx.author, HOLDER_ROLE) or has_role(ctx.author, FULL_ACCESS_ROLE)
    return False

# ---------------- Command Error Handling ----------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument type or member not found.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Use ~~help to see available commands.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")

# ---------------- Message Filtering ----------------
spam_tracker = {}
SPAM_TIMEFRAME = 5
SPAM_LIMIT = 5

@bot.event
async def on_message(message):
    if message.author.bot or isinstance(message.channel, discord.DMChannel):
        return

    try:
        content = message.content.lower()

        # Spam filter
        now_ts = datetime.now(timezone.utc).timestamp()
        spam_tracker.setdefault(message.author.id, [])
        spam_tracker[message.author.id] = [t for t in spam_tracker[message.author.id] if now_ts - t < SPAM_TIMEFRAME]
        spam_tracker[message.author.id].append(now_ts)
        if len(spam_tracker[message.author.id]) > SPAM_LIMIT:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, slow down!", delete_after=5)
            return

        # Link/word filter
        try:
            filter_data = json.load(open("filter.json", "r"))
        except:
            filter_data = {"blocked_links": [], "blocked_words": []}

        for word in filter_data.get("blocked_words", []):
            if word.strip() and word.lower() in content:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, watch your language!", delete_after=5)
                return

        for link in filter_data.get("blocked_links", []):
            if link.strip() and link.lower() in content:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, links not allowed!", delete_after=5)
                return

    except Exception as e:
        print(f"Filter error: {e}")

    await bot.process_commands(message)

# ---------------- Auto Cleaner ----------------
@tasks.loop(seconds=30)
async def auto_cleaner():
    for cid, conf in config.get("auto_delete", {}).items():
        if not conf.get("enabled"):
            continue
        channel = bot.get_channel(int(cid))
        if not channel:
            continue
        try:
            messages = [msg async for msg in channel.history(limit=500, oldest_first=True)]
        except discord.Forbidden:
            continue
        now = datetime.utcnow()
        if conf.get("max_age"):
            for msg in messages:
                age = (now - msg.created_at).total_seconds()
                if age > conf["max_age"]:
                    try: await msg.delete(); await asyncio.sleep(1)
                    except: continue
        if conf.get("max_messages") and len(messages) > conf["max_messages"]:
            to_delete = messages[:len(messages) - conf["max_messages"]]
            for msg in to_delete:
                try: await msg.delete(); await asyncio.sleep(1)
                except: continue

# ---------------- Load Cogs ----------------
async def load_cogs():
    await bot.load_extension("admin")
    await bot.load_extension("economy")

@bot.event
async def on_ready():
    print(f"Bot ready as {bot.user.name}")
    await load_cogs()
    auto_cleaner.start()

# ---------------- Keep Alive ----------------
webserver.keep_alive()

# ---------------- Run Bot ----------------
bot.run(TOKEN, log_handler=logging.FileHandler('discord.log', encoding='utf-8', mode='w'), log_level=logging.DEBUG)
