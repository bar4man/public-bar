# economy.py
import discord
from discord.ext import commands
import json
import random

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="balance")
    async def balance(self, ctx):
        try:
            with open("economy.json", "r") as f:
                data = json.load(f)
            bal = data.get(str(ctx.author.id), 0)
            await ctx.send(f"💰 {ctx.author.mention}, your balance is {bal}£")
        except Exception as e:
            await ctx.send(f"❌ Error checking balance: {e}")

    @commands.command(name="daily")
    async def daily(self, ctx):
        try:
            with open("economy.json", "r") as f:
                data = json.load(f)
            amount = random.randint(100, 200) * 2
            data[str(ctx.author.id)] = data.get(str(ctx.author.id), 0) + amount
            with open("economy.json", "w") as f:
                json.dump(data, f, indent=2)
            await ctx.send(f"💰 {ctx.author.mention} received {amount}£ as daily bonus!")
        except Exception as e:
            await ctx.send(f"❌ Error giving daily: {e}")

async def setup(bot):
    await bot.add_cog(Economy(bot))
