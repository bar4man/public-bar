import discord
from discord.ext import commands
import json
import os
import asyncio
import logging

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.econ_file = "economy.json"
        self.lock = asyncio.Lock()

        # Create economy.json if missing
        if not os.path.exists(self.econ_file):
            with open(self.econ_file, "w") as f:
                json.dump({}, f, indent=2)

    # ---------------- Utility Functions ----------------
    async def load_data(self):
        async with self.lock:
            try:
                with open(self.econ_file, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return {}

    async def save_data(self, data):
        async with self.lock:
            with open(self.econ_file, "w") as f:
                json.dump(data, f, indent=2)

    def is_admin(self, member):
        """Check if a user has the 'bot-admin' role."""
        return discord.utils.get(member.roles, name="bot-admin") is not None

    # ---------------- Commands ----------------
    @commands.command(name="give")
    async def give_money(self, ctx, member: discord.Member, amount: int):
        """Give a member some money (Admin only)."""
        if not self.is_admin(ctx.author):
            return await ctx.send("❌ You do not have permission to use this command.")

        if amount <= 0:
            return await ctx.send("❌ Amount must be greater than zero.")

        try:
            data = await self.load_data()
            uid = str(member.id)
            data.setdefault(uid, {}).setdefault("wallet", 0)
            data[uid]["wallet"] += amount
            await self.save_data(data)

            await ctx.send(f"✅ Gave **{amount}£** to {member.mention}")
            logging.info(f"Gave {amount}£ to {member} by {ctx.author}")
        except Exception as e:
            logging.error(f"Error in give_money: {e}")
            await ctx.send("⚠️ An unexpected error occurred while giving money.")

    @commands.command(name="take")
    async def take_money(self, ctx, member: discord.Member, amount: int):
        """Take money from a member (Admin only)."""
        if not self.is_admin(ctx.author):
            return await ctx.send("❌ You do not have permission to use this command.")

        if amount <= 0:
            return await ctx.send("❌ Amount must be greater than zero.")

        try:
            data = await self.load_data()
            uid = str(member.id)
            data.setdefault(uid, {}).setdefault("wallet", 0)
            data[uid]["wallet"] = max(0, data[uid]["wallet"] - amount)
            await self.save_data(data)

            await ctx.send(f"✅ Took **{amount}£** from {member.mention}")
            logging.info(f"Took {amount}£ from {member} by {ctx.author}")
        except Exception as e:
            logging.error(f"Error in take_money: {e}")
            await ctx.send("⚠️ An unexpected error occurred while taking money.")

    @commands.command(name="setmoney")
    async def set_money(self, ctx, member: discord.Member, amount: int):
        """Directly set a member's balance (Admin only)."""
        if not self.is_admin(ctx.author):
            return await ctx.send("❌ You do not have permission to use this command.")

        if amount < 0:
            return await ctx.send("❌ Balance cannot be negative.")

        try:
            data = await self.load_data()
            uid = str(member.id)
            data.setdefault(uid, {})["wallet"] = amount
            await self.save_data(data)

            await ctx.send(f"💰 Set {member.mention}'s balance to **{amount}£**")
            logging.info(f"Set {member}'s balance to {amount}£ by {ctx.author}")
        except Exception as e:
            logging.error(f"Error in set_money: {e}")
            await ctx.send("⚠️ An unexpected error occurred while setting money.")

async def setup(bot):
    await bot.add_cog(Admin(bot))
