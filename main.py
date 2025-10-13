# main.py

import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
from threading import Thread
from flask import Flask

# Import modules
import economy
import admin

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='~~', intents=intents)
bot.remove_command("help")

# ---------------- Events ----------------

@bot.event
async def on_ready():
    print(f"Bot ready as {bot.user.name}")
    economy.auto_cleaner.start()

# ---------------- Flask Webserver for Render ----------------

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

# ---------------- Register Commands ----------------

admin.register_commands(bot)
economy.register_commands(bot)

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
