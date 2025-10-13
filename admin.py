# admin.py
import discord
from discord.ext import commands
import json
from datetime import datetime

CONFIG_FILE = "config.json"

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Example admin command
    @commands.command(name="give")
    async def give_money(self, ctx, member: discord.Member, amount: int):
        try:
            if not discord.utils.get(ctx.author.roles, name="bot-admin"):
                return await ctx.send("❌ You don’t have permission.")
            with open("economy.json", "r") as f:
                data = json.load(f)
            data.setdefault(str(member.id), 0)
            data[str(member.id)] += amount
            with open("economy.json", "w") as f:
                json.dump(data, f, indent=2)
            await ctx.send(f"✅ Gave {amount}£ to {member.mention}")
        except Exception as e:
            await ctx.send(f"❌ Error giving money: {e}")

    @commands.command(name="take")
    async def take_money(self, ctx, member: discord.Member, amount: int):
        try:
            if not discord.utils.get(ctx.author.roles, name="bot-admin"):
                return await ctx.send("❌ You don’t have permission.")
            with open("economy.json", "r") as f:
                data = json.load(f)
            data.setdefault(str(member.id), 0)
            data[str(member.id)] = max(0, data[str(member.id)] - amount)
            with open("economy.json", "w") as f:
                json.dump(data, f, indent=2)
            await ctx.send(f"✅ Took {amount}£ from {member.mention}")
        except Exception as e:
            await ctx.send(f"❌ Error taking money: {e}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
