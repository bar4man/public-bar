# economy.py

import discord
from discord.ext import commands
import json
import os
import random

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.econ_file = "economy.json"
        if not os.path.exists(self.econ_file):
            with open(self.econ_file, "w") as f:
                json.dump({}, f)

    def load_data(self):
        with open(self.econ_file, "r") as f:
            return json.load(f)

    def save_data(self, data):
        with open(self.econ_file, "w") as f:
            json.dump(data, f, indent=2)

    @commands.command(name="balance")
    async def balance(self, ctx):
        try:
            data = self.load_data()
            uid = str(ctx.author.id)
            wallet = data.get(uid, {}).get("wallet", 0)
            await ctx.send(f"💰 {ctx.author.mention}, you have {wallet}£ in your wallet.")
        except Exception as e:
            await ctx.send(f"❌ Error checking balance: {str(e)}")

    @commands.command(name="daily")
    async def daily(self, ctx):
        try:
            data = self.load_data()
            uid = str(ctx.author.id)
            amount = random.randint(100, 200) * 2
            data.setdefault(uid, {}).setdefault("wallet", 0)
            data[uid]["wallet"] += amount
            self.save_data(data)
            await ctx.send(f"💵 {ctx.author.mention}, you collected your daily {amount}£!")
        except Exception as e:
            await ctx.send(f"❌ Error collecting daily: {str(e)}")

    @commands.command(name="pay")
    async def pay(self, ctx, member: discord.Member, amount: int):
        try:
            if amount <= 0:
                return await ctx.send("❌ Amount must be greater than 0.")
            data = self.load_data()
            uid_from = str(ctx.author.id)
            uid_to = str(member.id)
            wallet_from = data.get(uid_from, {}).get("wallet", 0)
            if wallet_from < amount:
                return await ctx.send("❌ You do not have enough money.")
            data.setdefault(uid_to, {}).setdefault("
