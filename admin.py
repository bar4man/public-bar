import discord
from discord.ext import commands
import json
import os
import asyncio
import logging
from typing import Optional

class Admin(commands.Cog):
    """Administrative commands for bot management."""
    
    def __init__(self, bot):
        self.bot = bot
        self.econ_file = "economy.json"
        self.lock = asyncio.Lock()
        self._initialize_economy()
    
    def _initialize_economy(self):
        """Create economy.json if it doesn't exist."""
        if not os.path.exists(self.econ_file):
            with open(self.econ_file, "w") as f:
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
    
    def is_admin(self, member: discord.Member) -> bool:
        """Check if user has the 'bot-admin' role."""
        return discord.utils.get(member.roles, name="bot-admin") is not None
    
    async def get_user_balance(self, user_id: int) -> dict:
        """Get user's wallet and bank balance."""
        data = await self.load_data()
        uid = str(user_id)
        return {
            "wallet": data.get(uid, {}).get("wallet", 0),
            "bank": data.get(uid, {}).get("bank", 0)
        }
    
    # ---------------- Admin Check Decorator ----------------
    async def cog_check(self, ctx):
        """Global check for all commands in this cog."""
        if not self.is_admin(ctx.author):
            embed = discord.Embed(
                title="🔒 Admin Only",
                description="This command requires the `bot-admin` role.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return False
        return True
    
    # ---------------- Commands ----------------
    @commands.command(name="give", aliases=["addmoney"])
    async def give_money(self, ctx, member: discord.Member, amount: int):
        """Give money to a member.
        
        Usage: ~~give @user <amount>
        Example: ~~give @John 1000
        """
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than zero.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="You cannot give money to bots.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        try:
            data = await self.load_data()
            uid = str(member.id)
            
            # Initialize user data if doesn't exist
            if uid not in data:
                data[uid] = {"wallet": 0, "bank": 0}
            
            old_balance = data[uid]["wallet"]
            data[uid]["wallet"] += amount
            new_balance = data[uid]["wallet"]
            
            await self.save_data(data)
            
            # Success embed
            embed = discord.Embed(
                title="💰 Money Given",
                description=f"Successfully gave **{amount:,}£** to {member.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Previous Balance", value=f"{old_balance:,}£", inline=True)
            embed.add_field(name="New Balance", value=f"{new_balance:,}£", inline=True)
            embed.set_footer(text=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} gave {amount}£ to {member}")
            
        except Exception as e:
            logging.error(f"Error in give_money: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="An unexpected error occurred while giving money.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="take", aliases=["removemoney"])
    async def take_money(self, ctx, member: discord.Member, amount: int):
        """Take money from a member.
        
        Usage: ~~take @user <amount>
        Example: ~~take @John 500
        """
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than zero.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="You cannot take money from bots.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        try:
            data = await self.load_data()
            uid = str(member.id)
            
            # Initialize user data if doesn't exist
            if uid not in data:
                data[uid] = {"wallet": 0, "bank": 0}
            
            old_balance = data[uid]["wallet"]
            data[uid]["wallet"] = max(0, data[uid]["wallet"] - amount)
            new_balance = data[uid]["wallet"]
            actual_taken = old_balance - new_balance
            
            await self.save_data(data)
            
            # Success embed
            embed = discord.Embed(
                title="💸 Money Taken",
                description=f"Took **{actual_taken:,}£** from {member.mention}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Previous Balance", value=f"{old_balance:,}£", inline=True)
            embed.add_field(name="New Balance", value=f"{new_balance:,}£", inline=True)
            
            if actual_taken < amount:
                embed.add_field(
                    name="⚠️ Note",
                    value=f"User only had {old_balance:,}£, took all available.",
                    inline=False
                )
            
            embed.set_footer(text=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} took {actual_taken}£ from {member}")
            
        except Exception as e:
            logging.error(f"Error in take_money: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="An unexpected error occurred while taking money.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="setmoney", aliases=["setbalance"])
    async def set_money(self, ctx, member: discord.Member, amount: int):
        """Set a member's wallet balance to a specific amount.
        
        Usage: ~~setmoney @user <amount>
        Example: ~~setmoney @John 5000
        """
        if amount < 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Balance cannot be negative.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="You cannot set balance for bots.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        try:
            data = await self.load_data()
            uid = str(member.id)
            
            # Get old balance
            old_balance = data.get(uid, {}).get("wallet", 0)
            
            # Initialize user data
            if uid not in data:
                data[uid] = {"wallet": 0, "bank": 0}
            
            data[uid]["wallet"] = amount
            await self.save_data(data)
            
            # Success embed
            embed = discord.Embed(
                title="💰 Balance Set",
                description=f"Set {member.mention}'s wallet balance to **{amount:,}£**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Previous Balance", value=f"{old_balance:,}£", inline=True)
            embed.add_field(name="New Balance", value=f"{amount:,}£", inline=True)
            embed.set_footer(text=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} set {member}'s balance to {amount}£")
            
        except Exception as e:
            logging.error(f"Error in set_money: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="An unexpected error occurred while setting money.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="resetuser")
    async def reset_user(self, ctx, member: discord.Member):
        """Reset a user's economy data completely.
        
        Usage: ~~resetuser @user
        """
        try:
            data = await self.load_data()
            uid = str(member.id)
            
            if uid not in data:
                embed = discord.Embed(
                    title="ℹ️ No Data",
                    description=f"{member.mention} has no economy data to reset.",
                    color=discord.Color.blue()
                )
                return await ctx.send(embed=embed)
            
            old_data = data[uid].copy()
            del data[uid]
            await self.save_data(data)
            
            embed = discord.Embed(
                title="🔄 User Reset",
                description=f"Successfully reset economy data for {member.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Wallet Cleared", value=f"{old_data.get('wallet', 0):,}£", inline=True)
            embed.add_field(name="Bank Cleared", value=f"{old_data.get('bank', 0):,}£", inline=True)
            embed.set_footer(text=f"Action by {ctx.author.name}", icon_url=ctx.author.display_avatar.url)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} reset economy data for {member}")
            
        except Exception as e:
            logging.error(f"Error in reset_user: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="An unexpected error occurred while resetting user.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name="viewuser")
    async def view_user(self, ctx, member: discord.Member):
        """View detailed economy information about a user.
        
        Usage: ~~viewuser @user
        """
        try:
            data = await self.load_data()
            uid = str(member.id)
            user_data = data.get(uid, {"wallet": 0, "bank": 0})
            
            wallet = user_data.get("wallet", 0)
            bank = user_data.get("bank", 0)
            total = wallet + bank
            
            embed = discord.Embed(
                title=f"💼 Economy Profile: {member.display_name}",
                color=discord.Color.blue()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="💰 Wallet", value=f"{wallet:,}£", inline=True)
            embed.add_field(name="🏦 Bank", value=f"{bank:,}£", inline=True)
            embed.add_field(name="💎 Total", value=f"{total:,}£", inline=True)
            embed.set_footer(text=f"User ID: {member.id}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Error in view_user: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="An unexpected error occurred while viewing user data.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
