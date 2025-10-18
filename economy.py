import discord
from discord.ext import commands
import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Dict

class SimpleEconomy:
    def __init__(self):
        self.users = {}
        logging.info("💰 Simple economy system loaded")
    
    def get_user(self, user_id: int) -> Dict:
        if user_id not in self.users:
            self.users[user_id] = {
                "wallet": 100,
                "bank": 0,
                "bank_limit": 5000,
                "networth": 100
            }
        return self.users[user_id]
    
    def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        user = self.get_user(user_id)
        user['wallet'] = max(0, user['wallet'] + wallet_change)
        user['bank'] = max(0, user['bank'] + bank_change)
        user['networth'] = user['wallet'] + user['bank']
        logging.info(f"💰 Updated user {user_id}: wallet={user['wallet']}")
        return user

economy = SimpleEconomy()

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def format_money(self, amount: int) -> str:
        return f"{amount:,}£"
    
    @commands.command(name="balance", aliases=["bal"])
    async def balance(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user = economy.get_user(member.id)
        
        embed = discord.Embed(title=f"💰 {member.display_name}'s Balance", color=0x00ff00)
        embed.add_field(name="💵 Wallet", value=self.format_money(user['wallet']), inline=True)
        embed.add_field(name="🏦 Bank", value=f"{self.format_money(user['bank'])} / {self.format_money(user['bank_limit'])}", inline=True)
        embed.add_field(name="💎 Net Worth", value=self.format_money(user['networth']), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="daily")
    async def daily(self, ctx):
        reward = random.randint(500, 1000)
        user = economy.update_balance(ctx.author.id, wallet_change=reward)
        
        embed = discord.Embed(title="🎁 Daily Reward!", color=0x00ff00)
        embed.description = f"You received {self.format_money(reward)}!"
        embed.add_field(name="💵 New Balance", value=self.format_money(user['wallet']), inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="work")
    async def work(self, ctx):
        earnings = random.randint(80, 200)
        user = economy.update_balance(ctx.author.id, wallet_change=earnings)
        
        embed = discord.Embed(title="💼 Work Complete!", color=0x0099ff)
        embed.description = f"You worked and earned {self.format_money(earnings)}!"
        embed.add_field(name="💵 New Balance", value=self.format_money(user['wallet']), inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
