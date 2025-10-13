# admin.py

import discord
from discord.ext import commands
import json
import os

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, ctx):
        return discord.utils.get(ctx.author.roles, name="bot-admin") is not None

    @commands.command(name="give")
    async def give_money(self, ctx, member: discord.Member, amount: int):
        if not self.is_admin(ctx):
            return await ctx.send("❌ You do not have permission.")
        try:
            econ_file = "economy.json"
            data = {}
            if os.path.exists(econ_file):
                with open(econ_file, "r") as f:
                    data = json.load(f)
            uid = str(member.id)
            data.setdefault(uid, {}).setdefault("wallet", 0)
            data[uid]["wallet"] += amount
            with open(econ_file, "w") as f:
                json.dump(data, f, indent=2)
            await ctx.send(f"✅ Gave {amount}£ to {member.mention}")
        except Exception as e:
            await ctx.send(f"❌ Error giving money: {str(e)}")

    @commands.command(name="take")
    async def take_money(self, ctx, member: discord.Member, amount: int):
        if not self.is_admin(ctx):
            return await ctx.send("❌ You do not have permission.")
        try:
            econ_file = "economy.json"
            data = {}
            if os.path.exists(econ_file):
                with open(econ_file, "r") as f:
                    data = json.load(f)
            uid = str(member.id)
            data.setdefault(uid, {}).setdefault("wallet", 0)
            data[uid]["wallet"] -= amount
            if data[uid]["wallet"] < 0:
                data[uid]["wallet"] = 0
            with open(econ_file, "w") as f:
                json.dump(data, f, indent=2)
            await ctx.send(f"✅ Took {amount}£ from {member.mention}")
        except Exception as e:
            await ctx.send(f"❌ Error taking money: {str(e)}")

async def setup(bot):
    await bot.add_cog(Admin(bot))
