# main.py

import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import random
import json
from datetime import datetime, timezone
import webserver
import economy

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.all()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='~~', intents=intents)
bot.remove_command("help")

# ---------------- Config ----------------
CONFIG_FILE = "config.json"
LQ_ROLE = "low quality"
READER_ROLE = "reader"
LQ_ACCESS_ROLE = "lq-access"
FULL_ACCESS_ROLE = "bot-admin"
HOLDER_ROLE = "holder"

# Load or create config
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"auto_delete": {}, "autorole": None, "grape_gifs": [], "member_numbers": {}}, f)
with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

# ---------------- Permission Helpers ----------------
def has_role(member, role_name):
    return discord.utils.get(member.roles, name=role_name) is not None

def is_allowed(ctx, command_type):
    if command_type == "lq":
        return has_role(ctx.author, LQ_ACCESS_ROLE) or has_role(ctx.author, FULL_ACCESS_ROLE)
    if command_type == "full":
        return has_role(ctx.author, FULL_ACCESS_ROLE)
    if command_type == "grape":
        return has_role(ctx.author, HOLDER_ROLE) or has_role(ctx.author, FULL_ACCESS_ROLE)
    return False

# ---------------- Events ----------------
@bot.event
async def on_ready():
    print(f"Bot ready as {bot.user.name}")
    auto_cleaner.start()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing argument: {error.param.name}")
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument type or member not found.")
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Unknown command. Use ~~help to see available commands.")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")

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

# ---------------- Custom Help ----------------
@bot.command(name="help")
async def custom_help(ctx):
    try:
        embed = discord.Embed(title="Available Commands", color=discord.Color.blurple())
        if is_allowed(ctx, "full"):
            embed.add_field(name="~~clear [num]", value="Clear messages (1-100)", inline=False)
            embed.add_field(name="~~setdelete on/off", value="Toggle auto-deletion in channel", inline=False)
            embed.add_field(name="~~maxmsg [num]", value="Set max allowed messages", inline=False)
            embed.add_field(name="~~maxage [sec]", value="Set max message age in seconds", inline=False)
            embed.add_field(name="~~setnum @user [number]", value="Assign a specific number to a user", inline=False)
            embed.add_field(name="~~numq [number]", value="Check if a number is in use", inline=False)
            embed.add_field(name="~~allowgrape @user", value="Give holder role", inline=False)
            embed.add_field(name="~~disallowgrape @user", value="Remove holder role", inline=False)
            embed.add_field(name="~~rest @user", value="Reset nickname to original number", inline=False)
        if is_allowed(ctx, "lq"):
            embed.add_field(name="~~lq @user", value="Assign low quality role and remove reader role", inline=False)
            embed.add_field(name="~~unlq @user", value="Remove low quality role and add reader role", inline=False)
        if is_allowed(ctx, "grape"):
            embed.add_field(name="~~grape @user", value="Send a grape GIF with message", inline=False)
        embed.add_field(name="~~economy", value="Shows economy commands", inline=False)
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error executing help command: {str(e)}")

# ---------------- Economy ----------------
economy.register_commands(bot)

# ---------------- Run Bot ----------------
webserver.keep_alive()  # Keep alive for Render hosting

bot.run(token, log_handler=handler, log_level=logging.DEBUG)


