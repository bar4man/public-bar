import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import random
import json
from datetime import datetime, timezone, timedelta
from threading import Thread
from flask import Flask
import webserver

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='~~', intents=intents)
bot.remove_command("help")

CONFIG_FILE = "config.json"
ECON_FILE = "economy.json"
LQ_ROLE = "low quality"
READER_ROLE = "reader"
LQ_ACCESS_ROLE = "lq-access"
FULL_ACCESS_ROLE = "bot-admin"
HOLDER_ROLE = "holder"

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"auto_delete": {}, "autorole": None, "grape_gifs": [], "member_numbers": {}}, f)
if not os.path.exists(ECON_FILE):
    with open(ECON_FILE, 'w') as f:
        json.dump({"users": {}}, f)

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

# Helper functions

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_economy():
    with open(ECON_FILE, 'r') as f:
        return json.load(f)

def save_economy(data):
    with open(ECON_FILE, 'w') as f:
        json.dump(data, f, indent=2)

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

# Economy helpers

def ensure_user(user_id):
    data = load_economy()
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"wallet": 0, "bank": 0, "last_daily": None, "last_work": None}
        save_economy(data)

def change_balance(user_id, wallet_change=0, bank_change=0):
    data = load_economy()
    ensure_user(user_id)
    data["users"][str(user_id)]["wallet"] += wallet_change
    data["users"][str(user_id)]["bank"] += bank_change
    save_economy(data)

# --- Bot events and tasks remain as in your original file ---

@bot.event
async def on_ready():
    print(f"Bot ready as {bot.user.name}")
    auto_cleaner.start()
    backup_economy.start()

# -------------- Economy Commands --------------

@bot.command()
async def balance(ctx, member: discord.Member = None):
    member = member or ctx.author
    ensure_user(member.id)
    data = load_economy()["users"][str(member.id)]
    await ctx.send(f"💰 {member.display_name} has {data['wallet']} Pounds in wallet and {data['bank']} Pounds in bank.")

@bot.command()
async def work(ctx):
    ensure_user(ctx.author.id)
    data = load_economy()["users"][str(ctx.author.id)]
    last_work = data.get("last_work")
    now_ts = datetime.now(timezone.utc).timestamp()

    if last_work and now_ts - last_work < 1800:
        remaining = int(1800 - (now_ts - last_work))
        return await ctx.send(f"⏳ You need to wait {remaining//60}m {remaining%60}s to work again.")

    earned = random.randint(20, 100)
    if has_role(ctx.author, HOLDER_ROLE):
        earned *= 2
    change_balance(ctx.author.id, wallet_change=earned)
    data = load_economy()["users"][str(ctx.author.id)]
    data["last_work"] = now_ts
    save_economy(load_economy())
    await ctx.send(f"💼 You worked and earned {earned} Pounds!")

@bot.command()
async def daily(ctx):
    ensure_user(ctx.author.id)
    data = load_economy()["users"][str(ctx.author.id)]
    now_ts = datetime.now(timezone.utc).timestamp()

    if data.get("last_daily") and now_ts - data["last_daily"] < 86400:
        remaining = int(86400 - (now_ts - data['last_daily']))
        return await ctx.send(f"⏳ You need to wait {remaining//3600}h {(remaining%3600)//60}m for next daily.")

    reward = random.randint(100, 200)
    if has_role(ctx.author, HOLDER_ROLE):
        reward *= 2
    change_balance(ctx.author.id, wallet_change=reward)
    data = load_economy()["users"][str(ctx.author.id)]
    data["last_daily"] = now_ts
    save_economy(load_economy())
    await ctx.send(f"🎁 You claimed your daily reward of {reward} Pounds!")

@bot.command()
async def deposit(ctx, amount: int):
    ensure_user(ctx.author.id)
    data = load_economy()["users"][str(ctx.author.id)]
    if amount <= 0 or amount > data['wallet']:
        return await ctx.send("❌ Invalid deposit amount.")
    change_balance(ctx.author.id, wallet_change=-amount, bank_change=amount)
    await ctx.send(f"🏦 Deposited {amount} Pounds to your bank.")

@bot.command()
async def withdraw(ctx, amount: int):
    ensure_user(ctx.author.id)
    data = load_economy()["users"][str(ctx.author.id)]
    if amount <= 0 or amount > data['bank']:
        return await ctx.send("❌ Invalid withdraw amount.")
    change_balance(ctx.author.id, wallet_change=amount, bank_change=-amount)
    await ctx.send(f"💵 Withdrew {amount} Pounds from your bank.")

@bot.command()
async def transfer(ctx, member: discord.Member, amount: int):
    if member.bot or member.id == ctx.author.id:
        return await ctx.send("❌ Invalid recipient.")
    ensure_user(ctx.author.id)
    ensure_user(member.id)
    data_sender = load_economy()["users"][str(ctx.author.id)]
    if amount <= 0 or amount > data_sender['wallet']:
        return await ctx.send("❌ Invalid transfer amount.")
    change_balance(ctx.author.id, wallet_change=-amount)
    change_balance(member.id, wallet_change=amount)
    await ctx.send(f"💸 Transferred {amount} Pounds to {member.display_name}.")

@bot.command()
async def leaderboard(ctx):
    data = load_economy()["users"]
    sorted_users = sorted(data.items(), key=lambda x: x[1]['wallet']+x[1]['bank'], reverse=True)[:10]
    desc = ''
    for i, (uid, info) in enumerate(sorted_users, 1):
        member = ctx.guild.get_member(int(uid))
        name = member.display_name if member else f'User {uid}'
        desc += f"{i}. {name} — {info['wallet']+info['bank']} Pounds\n"
    await ctx.send(f"🏆 **Leaderboard**\n{desc}")

# Backup economy every hour
@tasks.loop(hours=1)
async def backup_economy():
    import shutil
    shutil.copy(ECON_FILE, f"economy_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

# ----------------- Custom Help -----------------
@bot.command(name="help")
async def custom_help(ctx):
    embed = discord.Embed(title="Available Commands", color=discord.Color.blurple())

    if is_allowed(ctx, "full"):
        embed.add_field(name="~~clear [num]", value="Clear messages (1-100)", inline=False)
        embed.add_field(name="~~setdelete on/off", value="Toggle auto-deletion in channel", inline=False)
        embed.add_field(name="~~maxmsg [num]", value="Set max allowed messages", inline=False)
        embed.add_field(name="~~maxage [sec]", value="Set max message age in seconds", inline=False)
        embed.add_field(name="~~setnum @user [number]", value="Assign a specific number to a user", inline=False)
        embed.add_field(name="~~allowgrape @user", value="Give holder role", inline=False)
        embed.add_field(name="~~disallowgrape @user", value="Remove holder role", inline=False)
        embed.add_field(name="~~rest @user", value="Reset a member's nickname to their original number", inline=False)

    if is_allowed(ctx, "lq"):
        embed.add_field(name="~~lq @user", value="Assign low quality role and remove reader role", inline=False)
        embed.add_field(name="~~unlq @user", value="Remove low quality role and add reader role", inline=False)

    if is_allowed(ctx, "grape"):
        embed.add_field(name="~~grape @user", value="Send a grape GIF with message", inline=False)

    embed.add_field(name="~~economy", value="Show economy commands help", inline=False)

    await ctx.send(embed=embed)

@bot.command(name="economy")
async def economy_help(ctx):
    embed = discord.Embed(title="Economy Commands", color=discord.Color.green())
    embed.add_field(name="~~balance [user]", value="Check wallet and bank", inline=False)
    embed.add_field(name="~~work", value="Work to earn Pounds (30m cooldown)", inline=False)
    embed.add_field(name="~~daily", value="Claim daily reward (24h cooldown)", inline=False)
    embed.add_field(name="~~deposit <amount>", value="Deposit Pounds to bank", inline=False)
    embed.add_field(name="~~withdraw <amount>", value="Withdraw Pounds from bank", inline=False)
    embed.add_field(name="~~transfer <user> <amount>", value="Send Pounds to another user", inline=False)
    embed.add_field(name="~~leaderboard", value="Show top 10 richest users", inline=False)
    await ctx.send(embed=embed)

# --- Keep the rest of your bot code including auto_cleaner and Flask keep-alive ---

webserver.keep_alive()

app = Flask('')
@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)
Thread(target=run).start()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
