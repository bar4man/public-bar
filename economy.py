import discord
from discord.ext import commands
import motor.motor_asyncio
import asyncio
import random
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

class HybridStorage:
    def __init__(self):
        self.mongo_connected = False
        self.client = None
        self.db = None
        self.memory_users = {}
        self.setup_mongo()
    
    def setup_mongo(self):
        """Try to connect to MongoDB."""
        try:
            connection_string = os.getenv('MONGODB_URI')
            if connection_string:
                self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
                self.db = self.client.economy_bot
                self.mongo_connected = True
                logging.info("✅ MongoDB connected")
            else:
                logging.warning("❌ MONGODB_URI not set")
        except Exception as e:
            logging.warning(f"❌ MongoDB failed: {e}")
    
    async def get_user(self, user_id: int) -> Dict:
        if self.mongo_connected:
            try:
                user = await self.db.users.find_one({"user_id": user_id})
                if user:
                    return user
            except Exception as e:
                logging.error(f"MongoDB read failed: {e}")
                self.mongo_connected = False
        
        # Fallback to memory
        if user_id not in self.memory_users:
            self.memory_users[user_id] = self._default_user(user_id)
        return self.memory_users[user_id]
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        user = await self.get_user(user_id)
        
        user['wallet'] = max(0, user['wallet'] + wallet_change)
        user['bank'] = max(0, user['bank'] + bank_change)
        
        if user['bank'] > user['bank_limit']:
            user['bank'] = user['bank_limit']
        
        user['networth'] = user['wallet'] + user['bank']
        user['last_active'] = datetime.now()
        
        # Try to save to MongoDB
        if self.mongo_connected:
            try:
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {"$set": user},
                    upsert=True
                )
            except Exception as e:
                logging.error(f"MongoDB save failed: {e}")
                self.mongo_connected = False
        
        return user
    
    def _default_user(self, user_id: int) -> Dict:
        return {
            "user_id": user_id,
            "wallet": 100,
            "bank": 0,
            "bank_limit": 5000,
            "networth": 100,
            "daily_streak": 0,
            "last_daily": None,
            "total_earned": 0,
            "created_at": datetime.now(),
            "last_active": datetime.now()
        }

# Global storage
storage = HybridStorage()

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def format_money(self, amount: int) -> str:
        return f"{amount:,}£"
    
    async def create_economy_embed(self, title: str, color: discord.Color = discord.Color.gold()) -> discord.Embed:
        db_status = "✅ MongoDB" if storage.mongo_connected else "💾 Memory"
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Economy System | {db_status}")
        return embed
    
    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await storage.get_user(member.id)
        
        embed = await self.create_economy_embed(f"💰 {member.display_name}'s Balance")
        embed.add_field(name="💵 Wallet", value=self.format_money(user['wallet']), inline=True)
        embed.add_field(name="🏦 Bank", value=f"{self.format_money(user['bank'])} / {self.format_money(user['bank_limit'])}", inline=True)
        embed.add_field(name="💎 Total", value=self.format_money(user['networth']), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="daily")
    async def daily(self, ctx):
        reward = 1000
        user = await storage.update_balance(ctx.author.id, wallet_change=reward)
        
        embed = await self.create_economy_embed("🎁 Daily Reward!", discord.Color.green())
        embed.description = f"You received {self.format_money(reward)}!"
        embed.add_field(name="💵 New Balance", value=self.format_money(user['wallet']), inline=False)
        embed.add_field(name="💾 Storage", value="MongoDB" if storage.mongo_connected else "Memory", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
