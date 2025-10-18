import discord
from discord.ext import commands
import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

class SimpleEconomy:
    def __init__(self):
        self.users = {}
        self.inventory = {}
        self.cooldowns = {}
        logging.info("💰 Simple economy system loaded")
    
    def get_user(self, user_id: int) -> Dict:
        if user_id not in self.users:
            self.users[user_id] = {
                "wallet": 100,
                "bank": 0,
                "bank_limit": 5000,
                "networth": 100,
                "daily_streak": 0,
                "last_daily": None,
                "total_earned": 0
            }
        return self.users[user_id]
    
    def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        user = self.get_user(user_id)
        user['wallet'] = max(0, user['wallet'] + wallet_change)
        user['bank'] = max(0, user['bank'] + bank_change)
        
        if user['bank'] > user['bank_limit']:
            user['bank'] = user['bank_limit']
        
        user['networth'] = user['wallet'] + user['bank']
        
        if wallet_change > 0 or bank_change > 0:
            user['total_earned'] += (wallet_change + bank_change)
        
        logging.info(f"💰 Updated user {user_id}: wallet={user['wallet']}")
        return user
    
    def transfer_money(self, from_user: int, to_user: int, amount: int) -> bool:
        from_user_data = self.get_user(from_user)
        to_user_data = self.get_user(to_user)
        
        if from_user_data['wallet'] < amount:
            return False
        
        from_user_data['wallet'] -= amount
        to_user_data['wallet'] += amount
        
        from_user_data['networth'] = from_user_data['wallet'] + from_user_data['bank']
        to_user_data['networth'] = to_user_data['wallet'] + to_user_data['bank']
        
        return True
    
    def check_cooldown(self, user_id: int, command: str, cooldown_seconds: int) -> Optional[float]:
        cooldown_key = f"{user_id}_{command}"
        last_used = self.cooldowns.get(cooldown_key)
        
        if last_used:
            time_passed = (datetime.now() - last_used).total_seconds()
            if time_passed < cooldown_seconds:
                return cooldown_seconds - time_passed
        return None
    
    def set_cooldown(self, user_id: int, command: str):
        cooldown_key = f"{user_id}_{command}"
        self.cooldowns[cooldown_key] = datetime.now()
    
    def add_to_inventory(self, user_id: int, item: Dict):
        if user_id not in self.inventory:
            self.inventory[user_id] = []
        self.inventory[user_id].append(item)
    
    def get_inventory(self, user_id: int) -> List:
        return self.inventory.get(user_id, [])
    
    def use_item(self, user_id: int, item_index: int) -> bool:
        if user_id in self.inventory and item_index < len(self.inventory[user_id]):
            self.inventory[user_id].pop(item_index)
            return True
        return False

# Global economy instance
economy = SimpleEconomy()

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def format_money(self, amount: int) -> str:
        return f"{amount:,}£"
    
    def format_time(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    async def create_economy_embed(self, title: str, color: discord.Color = discord.Color.gold()) -> discord.Embed:
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="💾 In-Memory Storage | Data resets on restart")
        return embed

    # ========== COMMANDS ==========
    
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user_data = economy.get_user(member.id)
        
        wallet = user_data["wallet"]
        bank = user_data["bank"]
        bank_limit = user_data["bank_limit"]
        total = wallet + bank
        bank_usage = (bank / bank_limit) * 100 if bank_limit > 0 else 0
        
        embed = await self.create_economy_embed(f"💰 {member.display_name}'s Balance")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💵 Wallet", value=self.format_money(wallet), inline=True)
        embed.add_field(name="🏦 Bank", value=f"{self.format_money(bank)} / {self.format_money(bank_limit)}", inline=True)
        embed.add_field(name="💎 Total", value=self.format_money(total), inline=True)
        
        # Bank usage bar
        bars = 10
        filled_bars = min(bars, int(bank_usage / 10))
        bar = "█" * filled_bars + "░" * (bars - filled_bars)
        embed.add_field(name="🏦 Bank Usage", value=f"`{bar}` {bank_usage:.1f}%", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context):
        # Check cooldown
        remaining = economy.check_cooldown(ctx.author.id, "daily", 24 * 3600)
        if remaining:
            embed = await self.create_economy_embed("⏰ Daily Already Claimed", discord.Color.orange())
            embed.description = f"You can claim your daily reward again in **{self.format_time(remaining)}**"
            return await ctx.send(embed=embed)
        
        user_data = economy.get_user(ctx.author.id)
        
        # Calculate reward with streak bonus
        base_reward = random.randint(500, 1000)
        streak = user_data.get("daily_streak", 0)
        streak_bonus = min(streak, 7) * 50
        total_reward = base_reward + streak_bonus
        
        # Update user
        result = economy.update_balance(ctx.author.id, wallet_change=total_reward)
        economy.set_cooldown(ctx.author.id, "daily")
        
        # Update streak
        user_data["daily_streak"] = streak + 1
        user_data["last_daily"] = datetime.now().isoformat()
        
        embed = await self.create_economy_embed("🎁 Daily Reward Claimed!", discord.Color.green())
        embed.description = f"You received {self.format_money(total_reward)}!"
        
        breakdown = f"• Base: {self.format_money(base_reward)}\n• Streak Bonus: {self.format_money(streak_bonus)} (Day {streak + 1})"
        embed.add_field(name="💰 Breakdown", value=breakdown, inline=False)
        embed.add_field(name="💵 New Balance", value=self.format_money(result["wallet"]), inline=False)
        embed.set_footer(text="Come back in 24 hours for your next reward!")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="work")
    async def work(self, ctx: commands.Context):
        # Check cooldown
        remaining = economy.check_cooldown(ctx.author.id, "work", 3600)
        if remaining:
            embed = await self.create_economy_embed("⏰ Already Worked Recently", discord.Color.orange())
            embed.description = f"You can work again in **{self.format_time(remaining)}**"
            return await ctx.send(embed=embed)
        
        # Job types with different earnings
        jobs = {
            "delivered packages": (50, 100),
            "drove for Uber": (60, 120),
            "worked at a café": (40, 80),
            "coded a website": (100, 250),
            "designed graphics": (80, 150)
        }
        
        job, (min_earn, max_earn) = random.choice(list(jobs.items()))
        earnings = random.randint(min_earn, max_earn)
        
        result = economy.update_balance(ctx.author.id, wallet_change=earnings)
        economy.set_cooldown(ctx.author.id, "work")
        
        embed = await self.create_economy_embed("💼 Work Complete!", discord.Color.blue())
        embed.description = f"You {job} and earned {self.format_money(earnings)}!"
        embed.add_field(name="💵 New Balance", value=self.format_money(result["wallet"]), inline=False)
        embed.set_footer(text="You can work again in 1 hour!")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="pay", aliases=["give", "transfer"])
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        if member == ctx.author:
            embed = await self.create_economy_embed("❌ Invalid Action", discord.Color.red())
            embed.description = "You cannot pay yourself!"
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = await self.create_economy_embed("❌ Invalid Action", discord.Color.red())
            embed.description = "You cannot pay bots!"
            return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = await self.create_economy_embed("❌ Invalid Amount", discord.Color.red())
            embed.description = "Payment amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        # Check if user has enough money
        user_data = economy.get_user(ctx.author.id)
        if user_data["wallet"] < amount:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Process transfer
        success = economy.transfer_money(ctx.author.id, member.id, amount)
        
        if success:
            embed = await self.create_economy_embed("💸 Payment Successful", discord.Color.green())
            embed.description = f"{ctx.author.mention} paid {self.format_money(amount)} to {member.mention}"
        else:
            embed = await self.create_economy_embed("⚠️ Transfer Failed", discord.Color.red())
            embed.description = "The payment could not be processed."
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
