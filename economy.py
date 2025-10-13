# economy.py

import discord
from discord.ext import tasks
import json
import random
from datetime import datetime, timezone
import asyncio

CONFIG_FILE = "config.json"
ECON_FILE = "economy.json"
HOLDER_ROLE = "holder"

# ---------------- Economy Helpers ----------------

def load_economy():
    with open(ECON_FILE, 'r') as f:
        return json.load(f)

def save_economy(data):
    with open(ECON_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def ensure_user(user_id):
    data = load_economy()
    if str(user_id) not in data["users"]:
        data["users"][str(user_id)] = {"wallet": 0, "bank": 0, "last_daily": None}
        save_economy(data)

def change_balance(user_id, wallet_change=0, bank_change=0):
    data = load_economy()
    ensure_user(user_id)
    data["users"][str(user_id)]["wallet"] += wallet_change
    data["users"][str(user_id)]["bank"] += bank_change
    save_economy(data)

# ---------------- Economy Commands ----------------

def register_commands(bot):

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, discord.ext.commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: {error.param.name}")
        elif isinstance(error, discord.ext.commands.BadArgument):
            await ctx.send(f"❌ Invalid argument type or member not found.")
        elif isinstance(error, discord.ext.commands.CommandNotFound):
            await ctx.send(f"❌ Unknown command. Use ~~economy to see available economy commands.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")

    @bot.command()
    async def balance(ctx, member: discord.Member = None):
        try:
            member = member or ctx.author
            ensure_user(member.id)
            data = load_economy()["users"][str(member.id)]
            await ctx.send(f"💰 {member.display_name} has {data['wallet']} Pounds in wallet and {data['bank']} Pounds in bank.")
        except Exception as e:
            await ctx.send(f"❌ Error fetching balance: {str(e)}")

    @bot.command()
    async def daily(ctx):
        try:
            ensure_user(ctx.author.id)
            data = load_economy()["users"][str(ctx.author.id)]
            now_ts = datetime.now(timezone.utc).timestamp()
            if data.get("last_daily") and now_ts - data["last_daily"] < 86400:
                remaining = int(86400 - (now_ts - data['last_daily']))
                return await ctx.send(f"⏳ You need to wait {remaining//3600}h {(remaining%3600)//60}m for next daily.")
            reward = random.randint(100, 200)
            if any(role.name.lower() == HOLDER_ROLE for role in ctx.author.roles):
                reward *= 2
            change_balance(ctx.author.id, wallet_change=reward)
            data["last_daily"] = now_ts
            save_economy(load_economy())
            await ctx.send(f"🎁 You claimed your daily reward of {reward} Pounds!")
        except Exception as e:
            await ctx.send(f"❌ Error claiming daily reward: {str(e)}")

    @bot.command()
    async def give(ctx, member: discord.Member, amount: int):
        try:
            if not any(role.name.lower() == 'bot-admin' for role in ctx.author.roles):
                return await ctx.send("❌ You do not have permission to use this command.")
            ensure_user(member.id)
            change_balance(member.id, wallet_change=amount)
            await ctx.send(f"💰 Gave {amount} Pounds to {member.display_name}.")
        except Exception as e:
            await ctx.send(f"❌ Error giving money: {str(e)}")

    @bot.command()
    async def take(ctx, member: discord.Member, amount: int):
        try:
            if not any(role.name.lower() == 'bot-admin' for role in ctx.author.roles):
                return await ctx.send("❌ You do not have permission to use this command.")
            ensure_user(member.id)
            change_balance(member.id, wallet_change=-amount)
            await ctx.send(f"💸 Took {amount} Pounds from {member.display_name}.")
        except Exception as e:
            await ctx.send(f"❌ Error taking money: {str(e)}")
