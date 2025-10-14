import discord
from discord.ext import commands
import json
import os
import asyncio
import random
import logging
from datetime import datetime, timedelta

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.econ_file = "economy.json"
        self.lock = asyncio.Lock()
        self.cooldowns = {}  # Tracks daily rewards

        if not os.path.exists(self.econ_file):
            with open(self.econ_file, "w") as f:
                json.dump({}, f, indent=2)

    # ---------------- Utility ----------------
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

    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0):
        """Safely update wallet and bank balances."""
        data = await self.load_data()
        uid = str(user_id)
        data.setdefault(uid, {}).setdefault("wallet", 0)
        data.setdefault(uid, {}).setdefault("bank", 0)

        data[uid]["wallet"] = max(0, data[uid]["wallet"] + wallet_change)
        data[uid]["bank"] = max(0, data[uid]["bank"] + bank_change)

        await self.save_data(data)
        return data[uid]

    # ---------------- Commands ----------------
    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        try:
            data = await self.load_data()
            uid = str(member.id)
            wallet = data.get(uid, {}).get("wallet", 0)
            bank = data.get(uid, {}).get("bank", 0)
            await ctx.send(f"💰 {member.mention} has **{wallet}£** in wallet and **{bank}£** in bank.")
        except Exception as e:
            logging.error(f"Balance check failed: {e}")
            await ctx.send("⚠️ Error while checking balance.")

    @commands.command(name="deposit")
    async def deposit(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("❌ Deposit amount must be greater than 0.")

        uid = ctx.author.id
        data = await self.load_data()
        wallet = data.get(str(uid), {}).get("wallet", 0)

        if wallet < amount:
            return await ctx.send("❌ You do not have enough money in your wallet.")

        try:
            await self.update_balance(uid, wallet_change=-amount, bank_change=amount)
            await ctx.send(f"🏦 Deposited **{amount}£** to your bank.")
            logging.info(f"{ctx.author} deposited {amount}£ to bank.")
        except Exception as e:
            logging.error(f"Deposit failed: {e}")
            await ctx.send("⚠️ Error while depositing money.")

    @commands.command(name="withdraw")
    async def withdraw(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("❌ Withdraw amount must be greater than 0.")

        uid = ctx.author.id
        data = await self.load_data()
        bank = data.get(str(uid), {}).get("bank", 0)

        if bank < amount:
            return await ctx.send("❌ You do not have enough money in your bank.")

        try:
            await self.update_balance(uid, wallet_change=amount, bank_change=-amount)
            await ctx.send(f"🏦 Withdrew **{amount}£** from your bank.")
            logging.info(f"{ctx.author} withdrew {amount}£ from bank.")
        except Exception as e:
            logging.error(f"Withdraw failed: {e}")
            await ctx.send("⚠️ Error while withdrawing money.")

    @commands.command(name="bank")
    async def bank_balance(self, ctx):
        uid = ctx.author.id
        try:
            data = await self.load_data()
            bank = data.get(str(uid), {}).get("bank", 0)
            await ctx.send(f"🏦 {ctx.author.mention}, you have **{bank}£** in your bank.")
        except Exception as e:
            logging.error(f"Bank balance failed: {e}")
            await ctx.send("⚠️ Error while checking bank balance.")

    # You can keep previous commands: daily, pay, richest

async def setup(bot):
    await bot.add_cog(Economy(bot))
