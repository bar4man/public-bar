# main.py

import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import random
import json
from datetime import datetime, timedelta, timezone
import time
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
LQ_ROLE = "low quality"
READER_ROLE = "reader"
LQ_ACCESS_ROLE = "lq-access"
FULL_ACCESS_ROLE = "bot-admin"
HOLDER_ROLE = "holder"

# Economy file
ECON_FILE = "economy.json"

# Ensure config exists
if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"auto_delete": {}, "autorole": None, "grape_gifs": [], "member_numbers": {}}, f)

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

# Ensure economy file exists
if not os.path.exists(ECON_FILE):
    with open(ECON_FILE, 'w') as f:
        json.dump({}, f)

with open(ECON_FILE, 'r') as f:
    try:
        economy = json.load(f)
    except:
        economy = {}


def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def save_economy():
    with open(ECON_FILE, 'w') as f:
        json.dump(economy, f, indent=2)


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

def _now_iso():
    return datetime.now(timezone.utc).isoformat()

def ensure_user(uid: str):
    if uid not in economy:
        economy[uid] = {"wallet": 0, "bank": 0, "last_work": None, "last_daily": None}
        return True
    return False

def get_balances(uid: str):
    ensure_user(uid)
    data = economy[uid]
    return data.get("wallet", 0), data.get("bank", 0)

def change_balance(uid: str, wallet_change=0, bank_change=0):
    ensure_user(uid)
    economy[uid]["wallet"] = max(0, economy[uid].get("wallet", 0) + int(wallet_change))
    economy[uid]["bank"] = max(0, economy[uid].get("bank", 0) + int(bank_change))
    save_economy()

def set_last_work(uid: str):
    ensure_user(uid)
    economy[uid]["last_work"] = _now_iso()
    save_economy()

def set_last_daily(uid: str):
    ensure_user(uid)
    economy[uid]["last_daily"] = _now_iso()
    save_economy()

def parse_iso(iso_str):
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except:
        return None

# -------------- Events --------------

@bot.event
async def on_ready():
    print(f"Bot ready as {bot.user.name}")
    auto_cleaner.start()

    # sync commands if any (if you later add app commands)
    try:
        await bot.tree.sync()
    except Exception:
        pass

    number_data = config.get("member_numbers", {})
    for member in bot.get_all_members():
        if not member.bot:
            member_id = str(member.id)
            if member_id not in number_data:
                try:
                    num = int(member.display_name)
                    number_data[member_id] = {"number": num, "original": num}
                except:
                    continue
            else:
                try:
                    await member.edit(nick=str(number_data[member_id]["number"]))
                except:
                    continue
    config["member_numbers"] = number_data
    save_config()

@bot.event
async def on_member_join(member):
    role_name = config.get("autorole")
    if role_name:
        role = discord.utils.get(member.guild.roles, name=role_name)
        if role:
            await member.add_roles(role)

    number_data = config.get("member_numbers", {})
    member_id = str(member.id)
    if member_id in number_data:
        number = number_data[member_id]["number"]
    else:
        current = max([v["number"] for v in number_data.values()], default=124)
        number = current + 1
        number_data[member_id] = {"number": number, "original": number}
        config["member_numbers"] = number_data
        save_config()
    try:
        await member.edit(nick=str(number))
    except:
        pass

@bot.event
async def on_member_remove(member):
    # keep previous behaviour
    pass

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

        now = datetime.now(timezone.utc)

        if conf.get("max_age"):
            for msg in messages:
                age = (now - msg.created_at).total_seconds()
                if age > conf["max_age"]:
                    try:
                        await msg.delete()
                        await asyncio.sleep(1)
                    except:
                        continue

        if conf.get("max_messages") and len(messages) > conf["max_messages"]:
            to_delete = messages[:len(messages) - conf["max_messages"]]
            for msg in to_delete:
                try:
                    await msg.delete()
                    await asyncio.sleep(1)
                except:
                    continue

# -------------- Commands (existing) --------------

@bot.command()
async def clear(ctx, amount: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Please choose a number between 1 and 100.")
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"🧹 Deleted {len(deleted)} messages.", delete_after=3)

@bot.command()
async def setdelete(ctx, toggle: str):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    cid = str(ctx.channel.id)
    config["auto_delete"].setdefault(cid, {})
    config["auto_delete"][cid]["enabled"] = toggle.lower() == "on"
    save_config()
    await ctx.send(f"🛠️ Auto-delete {'enabled' if toggle.lower() == 'on' else 'disabled'} for this channel.")

@bot.command()
async def maxmsg(ctx, amount: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    cid = str(ctx.channel.id)
    config["auto_delete"].setdefault(cid, {})
    config["auto_delete"][cid]["max_messages"] = amount
    save_config()
    await ctx.send(f"🔢 Max messages set to {amount}.")

@bot.command()
async def maxage(ctx, seconds: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    cid = str(ctx.channel.id)
    config["auto_delete"].setdefault(cid, {})
    config["auto_delete"][cid]["max_age"] = seconds
    save_config()
    await ctx.send(f"⏳ Max message age set to {seconds} seconds.")

@bot.command()
async def numq(ctx, number: int):
    number_data = config.get("member_numbers", {})
    for uid, data in number_data.items():
        if data["number"] == number:
            member = ctx.guild.get_member(int(uid))
            if member:
                return await ctx.send(f"❌ Number {number} is already in use by {member.mention}.")
    await ctx.send(f"✅ Number {number} is available.")

@bot.command()
async def setnum(ctx, member: discord.Member, number: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    number_data = config.get("member_numbers", {})
    for uid, data in number_data.items():
        if data["number"] == number and uid != str(member.id):
            return await ctx.send("❌ That number is already taken.")

    member_id = str(member.id)
    if member_id not in number_data:
        number_data[member_id] = {"number": number, "original": number}
    else:
        number_data[member_id]["number"] = number
    config["member_numbers"] = number_data
    save_config()
    try:
        await member.edit(nick=str(number))
    except:
        pass
    await ctx.send(f"✅ Set number {number} for {member.mention}.")

@bot.command()
async def grape(ctx, user: discord.Member):
    if not is_allowed(ctx, "grape"):
        return await ctx.send("❌ You do not have permission.")
    gifs = config.get("grape_gifs", [])
    gif = random.choice(gifs) if gifs else None
    embed = discord.Embed(description=f"**{ctx.author.display_name} took advantage of {user.display_name}**", color=discord.Color.purple())
    if gif:
        embed.set_image(url=gif)
    await ctx.send(embed=embed)

@bot.command()
async def lq(ctx, member: discord.Member):
    if not is_allowed(ctx, "lq"):
        return await ctx.send("❌ You do not have permission.")
    guild = ctx.guild
    lq_role = discord.utils.get(guild.roles, name=LQ_ROLE)
    reader_role = discord.utils.get(guild.roles, name=READER_ROLE)
    if lq_role:
        await member.add_roles(lq_role)
    if reader_role:
        await member.remove_roles(reader_role)
    await ctx.send(f"{member.mention} marked as low quality.")

@bot.command()
async def unlq(ctx, member: discord.Member):
    if not is_allowed(ctx, "lq"):
        return await ctx.send("❌ You do not have permission.")
    guild = ctx.guild
    lq_role = discord.utils.get(guild.roles, name=LQ_ROLE)
    reader_role = discord.utils.get(guild.roles, name=READER_ROLE)
    if reader_role:
        await member.add_roles(reader_role)
    if lq_role:
        await member.remove_roles(lq_role)
    await ctx.send(f"{member.mention} restored to reader.")

@bot.command()
async def allowgrape(ctx, member: discord.Member):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    role = discord.utils.get(ctx.guild.roles, name=HOLDER_ROLE)
    if not role:
        role = await ctx.guild.create_role(name=HOLDER_ROLE)
    await member.add_roles(role)
    await ctx.send(f"✅ {member.mention} can now use ~~grape.")

@bot.command()
async def disallowgrape(ctx, member: discord.Member):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    role = discord.utils.get(ctx.guild.roles, name=HOLDER_ROLE)
    if not role:
        return await ctx.send("⚠️ 'holder' role does not exist.")
    await member.remove_roles(role)
    await ctx.send(f"🚫 {member.mention} can no longer use ~~grape.")

@bot.command()
async def rest(ctx, member: discord.Member):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    number_data = config.get("member_numbers", {})
    member_id = str(member.id)
    if member_id in number_data:
        number_data[member_id]["number"] = number_data[member_id]["original"]
        config["member_numbers"] = number_data
        save_config()
        try:
            await member.edit(nick=str(number_data[member_id]["original"]))
        except:
            pass
        await ctx.send(f"🔄 Reset nickname of {member.mention} to original number.")
    else:
        await ctx.send("❌ This user does not have a number registered.")

# -------------- Help --------------

@bot.command(name="help")
async def custom_help(ctx):
    if not any(has_role(ctx.author, r) for r in [FULL_ACCESS_ROLE, LQ_ACCESS_ROLE, HOLDER_ROLE]):
        return await ctx.send("❌ You do not have permission to use this command.")

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
        embed.add_field(name="~~rest @user", value="Reset a member's nickname to their original number", inline=False)

    if is_allowed(ctx, "lq"):
        embed.add_field(name="~~lq @user", value="Assign low quality role and remove reader role", inline=False)
        embed.add_field(name="~~unlq @user", value="Remove low quality role and add reader role", inline=False)

    if is_allowed(ctx, "grape"):
        embed.add_field(name="~~grape @user", value="Send a grape GIF with message", inline=False)

    # Economy section
    embed.add_field(name="💰 Economy", value="~~balance [user] | ~~work | ~~daily | ~~deposit <amt> | ~~withdraw <amt> | ~~transfer <user> <amt> | ~~leaderboard", inline=False)

    await ctx.send(embed=embed)

# -------------- Economy Commands --------------

WORK_COOLDOWN = 30 * 60  # seconds (30 minutes)
DAILY_COOLDOWN = 24 * 60 * 60  # seconds (24 hours)

@bot.command()
async def balance(ctx, member: discord.Member = None):
    target = member or ctx.author
    uid = str(target.id)
    ensure_user(uid)
    wallet, bank = get_balances(uid)
    embed = discord.Embed(title=f"{target.display_name}'s Balance", color=discord.Color.gold())
    embed.add_field(name="Wallet", value=f"{wallet} coins", inline=True)
    embed.add_field(name="Bank", value=f"{bank} coins", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def work(ctx):
    uid = str(ctx.author.id)
    ensure_user(uid)
    last = parse_iso(economy[uid].get("last_work"))
    now = datetime.now(timezone.utc)
    if last and (now - last).total_seconds() < WORK_COOLDOWN:
        remaining = WORK_COOLDOWN - int((now - last).total_seconds())
        mins = remaining // 60
        secs = remaining % 60
        return await ctx.send(f"🕒 You must wait {mins}m {secs}s before working again.")

    earned = random.randint(20, 100)
    change_balance(uid, wallet_change=earned)
    set_last_work(uid)
    await ctx.send(f"💼 You worked and earned {earned} coins!")

@bot.command()
async def daily(ctx):
    uid = str(ctx.author.id)
    ensure_user(uid)
    last = parse_iso(economy[uid].get("last_daily"))
    now = datetime.now(timezone.utc)
    if last and (now - last).total_seconds() < DAILY_COOLDOWN:
        remaining = DAILY_COOLDOWN - int((now - last).total_seconds())
        hours = remaining // 3600
        mins = (remaining % 3600) // 60
        return await ctx.send(f"⏳ You must wait {hours}h {mins}m before claiming daily again.")

    reward = random.randint(200, 500)
    change_balance(uid, wallet_change=reward)
    set_last_daily(uid)
    await ctx.send(f"🎁 You claimed your daily reward of {reward} coins!")

@bot.command()
async def deposit(ctx, amount: int):
    uid = str(ctx.author.id)
    ensure_user(uid)
    wallet, bank = get_balances(uid)
    if amount <= 0:
        return await ctx.send("❌ Amount must be positive.")
    if wallet < amount:
        return await ctx.send("❌ You don't have enough in your wallet.")
    change_balance(uid, wallet_change=-amount, bank_change=amount)
    await ctx.send(f"🏦 Deposited {amount} coins to your bank.")

@bot.command()
async def withdraw(ctx, amount: int):
    uid = str(ctx.author.id)
    ensure_user(uid)
    wallet, bank = get_balances(uid)
    if amount <= 0:
        return await ctx.send("❌ Amount must be positive.")
    if bank < amount:
        return await ctx.send("❌ You don't have enough in your bank.")
    change_balance(uid, wallet_change=amount, bank_change=-amount)
    await ctx.send(f"💸 Withdrew {amount} coins to your wallet.")

@bot.command()
async def transfer(ctx, member: discord.Member, amount: int):
    if member.bot:
        return await ctx.send("❌ You cannot transfer to bots.")
    uid = str(ctx.author.id)
    target_id = str(member.id)
    ensure_user(uid)
    ensure_user(target_id)
    wallet, _ = get_balances(uid)
    if amount <= 0:
        return await ctx.send("❌ Amount must be positive.")
    if wallet < amount:
        return await ctx.send("❌ You don't have enough in your wallet.")
    change_balance(uid, wallet_change=-amount)
    change_balance(target_id, wallet_change=amount)
    await ctx.send(f"✅ Sent {amount} coins to {member.mention}.")

@bot.command()
async def leaderboard(ctx):
    # show top 10 by total (wallet + bank)
    snapshot = []
    for uid, data in economy.items():
        total = data.get("wallet", 0) + data.get("bank", 0)
        snapshot.append((uid, total))
    snapshot.sort(key=lambda x: x[1], reverse=True)
    top = snapshot[:10]
    embed = discord.Embed(title="🏆 Economy Leaderboard", color=discord.Color.gold())
    if not top:
        embed.description = "No data yet."
    else:
        desc = ""
        for i, (uid, total) in enumerate(top, start=1):
            member = ctx.guild.get_member(int(uid))
            name = member.display_name if member else f"User {uid}"
            desc += f"**{i}. {name}** — {total} coins\n"
        embed.description = desc
    await ctx.send(embed=embed)

@bot.command()
async def reset_economy(ctx):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    economy.clear()
    save_economy()
    await ctx.send("✅ Economy has been reset.")

# -------------- Remaining existing commands --------------
# lq/unlq/allowgrape/disallowgrape/rest implemented earlier
# (they remain above in this file)

# -------------- Keep-alive & Run --------------

webserver.keep_alive()

# --- keep alive web server for Render ---
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run).start()

bot.run(token, log_handler=handler, log_level=logging.DEBUG)
