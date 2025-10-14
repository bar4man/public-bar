import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import json
from datetime import datetime, timezone
import webserver

# ---------------- Setup ----------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "true").lower() == "true"

# Logging
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="w")
logging.basicConfig(level=logging.INFO, handlers=[handler])

# Discord intents
intents = discord.Intents.all()
intents.message_content = True
intents.members = True

# Bot setup
bot = commands.Bot(command_prefix="~~", intents=intents)
bot.remove_command("help")  # (optional) remove default help to make custom one later

# ---------------- Config ----------------
CONFIG_FILE = "config.json"

default_config = {
    "auto_delete": {},
    "autorole": None,
    "grape_gifs": [],
    "member_numbers": {}
}

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, "w") as f:
        json.dump(default_config, f, indent=2)

with open(CONFIG_FILE, "r") as f:
    config = json.load(f)

config_lock = asyncio.Lock()

async def save_config():
    async with config_lock:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)

# ---------------- Permissions ----------------
FULL_ACCESS_ROLE = "bot-admin"
LQ_ACCESS_ROLE = "lq-access"
HOLDER_ROLE = "holder"

def has_role(member, role_name: str):
    return discord.utils.get(member.roles, name=role_name) is not None

def is_allowed(ctx, command_type: str):
    author = ctx.author
    if command_type == "full":
        return has_role(author, FULL_ACCESS_ROLE)
    elif command_type == "lq":
        return has_role(author, LQ_ACCESS_ROLE) or has_role(author, FULL_ACCESS_ROLE)
    elif command_type == "grape":
        return has_role(author, HOLDER_ROLE) or has_role(author, FULL_ACCESS_ROLE)
    return False

# ---------------- Error Handling ----------------
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: `{error.param.name}`")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ Invalid argument type or member not found.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Unknown command. Use `~~help` to see available commands.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You do not have permission to use this command.")
    else:
        logging.error(f"Error in command {ctx.command}: {error}")
        await ctx.send("⚠️ An unexpected error occurred. Check the logs for details.")

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
        now_ts = datetime.now(timezone.utc).timestamp()

        # Spam filter
        spam_tracker.setdefault(message.author.id, [])
        spam_tracker[message.author.id] = [
            t for t in spam_tracker[message.author.id] if now_ts - t < SPAM_TIMEFRAME
        ]
        spam_tracker[message.author.id].append(now_ts)

        if len(spam_tracker[message.author.id]) > SPAM_LIMIT:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, slow down!", delete_after=5)
            return

        # Link/word filter
        try:
            with open("filter.json", "r") as f:
                filter_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            filter_data = {"blocked_links": [], "blocked_words": []}

        for word in filter_data.get("blocked_words", []):
            if word and word.lower() in content:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, watch your language!", delete_after=5)
                return

        for link in filter_data.get("blocked_links", []):
            if link and link.lower() in content:
                await message.delete()
                await message.channel.send(f"{message.author.mention}, links not allowed!", delete_after=5)
                return

    except Exception as e:
        logging.warning(f"Message filter error: {e}")

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

        # Age cleanup
        if conf.get("max_age"):
            for msg in messages:
                age = (now - msg.created_at).total_seconds()
                if age > conf["max_age"]:
                    try:
                        await msg.delete()
                        await asyncio.sleep(1)
                    except:
                        continue

        # Count cleanup
        if conf.get("max_messages") and len(messages) > conf["max_messages"]:
            to_delete = messages[: len(messages) - conf["max_messages"]]
            for msg in to_delete:
                try:
                    await msg.delete()
                    await asyncio.sleep(1)
                except:
                    continue

# ---------------- Cog Loader ----------------
async def load_cogs():
    cogs = ["admin", "economy"]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logging.info(f"✅ Loaded cog: {cog}")
        except Exception as e:
            logging.error(f"❌ Failed to load cog {cog}: {e}")

# ---------------- Startup ----------------
@bot.event
async def setup_hook():
    await load_cogs()
    auto_cleaner.start()

@bot.event
async def on_ready():
    logging.info(f"✅ Bot is ready as {bot.user} (ID: {bot.user.id})")

# ---------------- Keep Alive ----------------
if KEEP_ALIVE:
    webserver.keep_alive()

# ---------------- Run ----------------
bot.run(TOKEN)
