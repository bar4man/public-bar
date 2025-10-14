import discord
from discord.ext import commands
import json
import os
import asyncio
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict

class Economy(commands.Cog):
    """Economy system commands for earning and managing money."""
    
    def __init__(self, bot):
        self.bot = bot
        self.econ_file = "economy.json"
        self.lock = asyncio.Lock()
        self.cooldowns_file = "cooldowns.json"
        self._initialize_files()
    
    def _initialize_files(self):
        """Create necessary files if they don't exist."""
        if not os.path.exists(self.econ_file):
            with open(self.econ_file, "w") as f:
                json.dump({}, f, indent=2)
        
        if not os.path.exists(self.cooldowns_file):
            with open(self.cooldowns_file, "w") as f:
                json.dump({}, f, indent=2)
    
    # ---------------- Utility Functions ----------------
    async def load_data(self) -> dict:
        """Load economy data from file."""
        async with self.lock:
            try:
                with open(self.econ_file, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.error(f"Error loading economy data: {e}")
                return {}
    
    async def save_data(self, data: dict) -> bool:
        """Save economy data to file."""
        async with self.lock:
            try:
                with open(self.econ_file, "w") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                logging.error(f"Error saving economy data: {e}")
                return False
    
    async def load_cooldowns(self) -> dict:
        """Load cooldown data."""
        try:
            with open(self.cooldowns_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    async def save_cooldowns(self, cooldowns: dict):
        """Save cooldown data."""
        try:
            with open(self.cooldowns_file, "w") as f:
                json.dump(cooldowns, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving cooldowns: {e}")
    
    async def check_cooldown(self, user_id: int, command: str, cooldown_hours: int) -> Optional[float]:
        """Check if user is on cooldown. Returns remaining time or None."""
        cooldowns = await self.load_cooldowns()
        user_cooldowns = cooldowns.get(str(user_id), {})
        
        if command in user_cooldowns:
            last_used = datetime.fromisoformat(user_cooldowns[command])
            now = datetime.now(timezone.utc)
            time_passed = (now - last_used).total_seconds()
            cooldown_seconds = cooldown_hours * 3600
            
            if time_passed < cooldown_seconds:
                return cooldown_seconds - time_passed
        
        return None
    
    async def set_cooldown(self, user_id: int, command: str):
        """Set cooldown for a command."""
        cooldowns = await self.load_cooldowns()
        uid = str(user_id)
        
        if uid not in cooldowns:
            cooldowns[uid] = {}
        
        cooldowns[uid][command] = datetime.now(timezone.utc).isoformat()
        await self.save_cooldowns(cooldowns)
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0):
        """Safely update wallet and bank balances."""
        data = await self.load_data()
        uid = str(user_id)
        
        if uid not in data:
            data[uid] = {"wallet": 0, "bank": 0}
        
        data[uid]["wallet"] = max(0, data[uid].get("wallet", 0) + wallet_change)
        data[uid]["bank"] = max(0, data[uid].get("bank", 0) + bank_change)
        
        await self.save_data(data)
        return data[uid]
    
    def format_time(self, seconds: float) -> str:
        """Format seconds into readable time."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    # ---------------- Commands ----------------
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx, member: discord.Member = None):
        """Check your or someone else's balance.
        
        Usage: ~~balance [@user]
        """
        member = member or ctx.author
        
        try:
            data = await self.load_data()
            uid = str(member.id)
            wallet = data.get(uid, {}).get("wallet", 0)
            bank = data.get(uid, {}).get("bank", 0)
            total = wallet + bank
            
            embed = discord.Embed(
                title=f"💰 {member.display_name}'s Balance",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="💵 Wallet", value=f"{wallet:,}£", inline=True)
            embed.add_field(name="🏦 Bank", value=f"{bank:,}£", inline=True)
            embed.add_field(name="💎 Total", value=f"{total:,}£", inline=True)
            embed.set_footer(text=f"Requested by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Balance check failed: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="Error while checking balance.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx, amount: str):
        """Deposit money from wallet to bank.
        
        Usage: ~~deposit <amount|all>
        Example: ~~deposit 1000 or ~~deposit all
        """
        uid = ctx.author.id
        data = await self.load_data()
        wallet = data.get(str(uid), {}).get("wallet", 0)
        
        # Handle "all" keyword
        if amount.lower() == "all":
            amount = wallet
        else:
            try:
                amount = int(amount)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please provide a valid number or use `all`.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Deposit amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if wallet < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{wallet:,}£** in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        try:
            result = await self.update_balance(uid, wallet_change=-amount, bank_change=amount)
            
            embed = discord.Embed(
                title="🏦 Deposit Successful",
                description=f"Deposited **{amount:,}£** to your bank.",
                color=discord.Color.green()
            )
            embed.add_field(name="💵 New Wallet", value=f"{result['wallet']:,}£", inline=True)
            embed.add_field(name="🏦 New Bank", value=f"{result['bank']:,}£", inline=True)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} deposited {amount}£ to bank")
            
        except Exception as e:
            logging.error(f"Deposit failed: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="Error while depositing money.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx, amount: str):
        """Withdraw money from bank to wallet.
        
        Usage: ~~withdraw <amount|all>
        Example: ~~withdraw 1000 or ~~withdraw all
        """
        uid = ctx.author.id
        data = await self.load_data()
        bank = data.get(str(uid), {}).get("bank", 0)
        
        # Handle "all" keyword
        if amount.lower() == "all":
            amount = bank
        else:
            try:
                amount = int(amount)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please provide a valid number or use `all`.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Withdraw amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if bank < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{bank:,}£** in your bank.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        try:
            result = await self.update_balance(uid, wallet_change=amount, bank_change=-amount)
            
            embed = discord.Embed(
                title="🏦 Withdrawal Successful",
                description=f"Withdrew **{amount:,}£** from your bank.",
                color=discord.Color.green()
            )
            embed.add_field(name="💵 New Wallet", value=f"{result['wallet']:,}£", inline=True)
            embed.add_field(name="🏦 New Bank", value=f"{result['bank']:,}£", inline=True)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} withdrew {amount}£ from bank")
            
        except Exception as e:
            logging.error(f"Withdraw failed: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="Error while withdrawing money.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim your daily reward.
        
        Usage: ~~daily
        """
        # Check cooldown (24 hours)
        remaining = await self.check_cooldown(ctx.author.id, "daily", 24)
        
        if remaining:
            embed = discord.Embed(
                title="⏰ Daily Already Claimed",
                description=f"You can claim your daily reward again in **{self.format_time(remaining)}**",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        # Random daily reward between 500-1500
        reward = random.randint(500, 1500)
        
        try:
            result = await self.update_balance(ctx.author.id, wallet_change=reward)
            await self.set_cooldown(ctx.author.id, "daily")
            
            embed = discord.Embed(
                title="🎁 Daily Reward Claimed!",
                description=f"You received **{reward:,}£**!",
                color=discord.Color.green()
            )
            embed.add_field(name="💵 New Wallet Balance", value=f"{result['wallet']:,}£", inline=False)
            embed.set_footer(text="Come back in 24 hours for your next daily reward!")
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} claimed daily reward: {reward}£")
            
        except Exception as e:
            logging.error(f"Daily reward failed: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="Error while claiming daily reward.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="work")
    async def work(self, ctx):
        """Work to earn money.
        
        Usage: ~~work
        """
        # Check cooldown (1 hour)
        remaining = await self.check_cooldown(ctx.author.id, "work", 1)
        
        if remaining:
            embed = discord.Embed(
                title="⏰ Already Worked Recently",
                description=f"You can work again in **{self.format_time(remaining)}**",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        # Random work earnings
        earnings = random.randint(50, 250)
        
        jobs = [
            "delivered packages", "drove a taxi", "worked at a café",
            "coded a website", "designed graphics", "tutored students",
            "wrote articles", "cleaned offices", "sold products",
            "streamed on Twitch", "made TikTok videos", "walked dogs"
        ]
        job = random.choice(jobs)
        
        try:
            result = await self.update_balance(ctx.author.id, wallet_change=earnings)
            await self.set_cooldown(ctx.author.id, "work")
            
            embed = discord.Embed(
                title="💼 Work Complete!",
                description=f"You {job} and earned **{earnings:,}£**!",
                color=discord.Color.blue()
            )
            embed.add_field(name="💵 New Wallet Balance", value=f"{result['wallet']:,}£", inline=False)
            embed.set_footer(text="You can work again in 1 hour!")
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} worked and earned {earnings}£")
            
        except Exception as e:
            logging.error(f"Work failed: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="Error while working.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="pay", aliases=["give"])
    async def pay(self, ctx, member: discord.Member, amount: int):
        """Pay another user money from your wallet.
        
        Usage: ~~pay @user <amount>
        """
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You cannot pay yourself!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You cannot pay bots!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Payment amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        data = await self.load_data()
        sender_wallet = data.get(str(ctx.author.id), {}).get("wallet", 0)
        
        if sender_wallet < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{sender_wallet:,}£** in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        try:
            await self.update_balance(ctx.author.id, wallet_change=-amount)
            await self.update_balance(member.id, wallet_change=amount)
            
            embed = discord.Embed(
                title="💸 Payment Successful",
                description=f"{ctx.author.mention} paid **{amount:,}£** to {member.mention}",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Transaction ID: {ctx.message.id}")
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} paid {amount}£ to {member}")
            
        except Exception as e:
            logging.error(f"Payment failed: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="Error while processing payment.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx):
        """Show the richest users on the server.
        
        Usage: ~~leaderboard
        """
        try:
            data = await self.load_data()
            
            # Calculate total wealth for each user
            user_totals = []
            for uid, user_data in data.items():
                wallet = user_data.get("wallet", 0)
                bank = user_data.get("bank", 0)
                total = wallet + bank
                
                if total > 0:
                    user_totals.append((int(uid), total))
            
            # Sort by total wealth
            user_totals.sort(key=lambda x: x[1], reverse=True)
            
            if not user_totals:
                embed = discord.Embed(
                    title="📊 Leaderboard",
                    description="No users have any money yet!",
                    color=discord.Color.blue()
                )
                return await ctx.send(embed=embed)
            
            # Build leaderboard
            embed = discord.Embed(
                title="📊 Wealth Leaderboard",
                description="Top richest users on the server",
                color=discord.Color.gold()
            )
            
            medals = ["🥇", "🥈", "🥉"]
            
            for i, (uid, total) in enumerate(user_totals[:10]):
                user = self.bot.get_user(uid)
                username = user.display_name if user else f"User {uid}"
                
                medal = medals[i] if i < 3 else f"`#{i+1}`"
                embed.add_field(
                    name=f"{medal} {username}",
                    value=f"💰 {total:,}£",
                    inline=False
                )
            
            embed.set_footer(text=f"Total users: {len(user_totals)}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Leaderboard failed: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="Error while loading leaderboard.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
