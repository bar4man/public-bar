import discord
from discord.ext import commands
import json
import logging
from datetime import datetime

logger = logging.getLogger('discord_bot')

class Admin(commands.Cog):
    """Admin commands - requires bot-admin role"""
    
    def __init__(self, bot):
        self.bot = bot
        self.admin_role = "bot-admin"
        self.economy_file = "economy.json"
        self.market_file = "market.json"
    
    def has_admin_role(self, member):
        """Check if member has bot-admin role"""
        return discord.utils.get(member.roles, name=self.admin_role) is not None
    
    def load_economy(self):
        """Load economy data"""
        try:
            with open(self.economy_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading economy: {e}")
            return {}
    
    def save_economy(self, data):
        """Save economy data"""
        try:
            with open(self.economy_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving economy: {e}")
            return False
    
    def load_market(self):
        """Load market data"""
        try:
            with open(self.market_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading market: {e}")
            return {}
    
    def save_market(self, data):
        """Save market data"""
        try:
            with open(self.market_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving market: {e}")
            return False
    
    async def cog_check(self, ctx):
        """Check if user has admin role for all commands in this cog"""
        if not self.has_admin_role(ctx.author):
            embed = discord.Embed(
                title="🔒 Admin Only",
                description=f"This command requires the `{self.admin_role}` role.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return False
        return True
    
    @commands.command(name='addmoney')
    async def addmoney(self, ctx, member: discord.Member, amount: int):
        """Add money to a user's wallet
        
        Usage: !addmoney @user <amount>
        Example: !addmoney @john 1000
        """
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="Cannot add money to bots.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        economy = self.load_economy()
        user_id = str(member.id)
        
        if user_id not in economy:
            economy[user_id] = {
                "wallet": 0,
                "bank": 0,
                "total_earned": 0,
                "inventory": {},
                "stocks": {}
            }
        
        old_balance = economy[user_id]["wallet"]
        economy[user_id]["wallet"] += amount
        new_balance = economy[user_id]["wallet"]
        
        if self.save_economy(economy):
            embed = discord.Embed(
                title="💰 Money Added",
                description=f"Added **{amount:,}£** to {member.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Previous Balance", value=f"{old_balance:,}£", inline=True)
            embed.add_field(name="New Balance", value=f"{new_balance:,}£", inline=True)
            embed.set_footer(text=f"Action by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} added {amount}£ to {member}")
        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description="Failed to save economy data.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='removemoney')
    async def removemoney(self, ctx, member: discord.Member, amount: int):
        """Remove money from a user's wallet
        
        Usage: !removemoney @user <amount>
        Example: !removemoney @john 500
        """
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="Cannot remove money from bots.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        economy = self.load_economy()
        user_id = str(member.id)
        
        if user_id not in economy:
            economy[user_id] = {
                "wallet": 0,
                "bank": 0,
                "total_earned": 0,
                "inventory": {},
                "stocks": {}
            }
        
        old_balance = economy[user_id]["wallet"]
        economy[user_id]["wallet"] = max(0, economy[user_id]["wallet"] - amount)
        new_balance = economy[user_id]["wallet"]
        actual_removed = old_balance - new_balance
        
        if self.save_economy(economy):
            embed = discord.Embed(
                title="💸 Money Removed",
                description=f"Removed **{actual_removed:,}£** from {member.mention}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Previous Balance", value=f"{old_balance:,}£", inline=True)
            embed.add_field(name="New Balance", value=f"{new_balance:,}£", inline=True)
            
            if actual_removed < amount:
                embed.add_field(
                    name="⚠️ Note",
                    value=f"User only had {old_balance:,}£",
                    inline=False
                )
            
            embed.set_footer(text=f"Action by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} removed {actual_removed}£ from {member}")
        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description="Failed to save economy data.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='setmoney')
    async def setmoney(self, ctx, member: discord.Member, amount: int):
        """Set a user's wallet balance
        
        Usage: !setmoney @user <amount>
        Example: !setmoney @john 5000
        """
        if amount < 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount cannot be negative.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="Cannot set money for bots.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        economy = self.load_economy()
        user_id = str(member.id)
        
        if user_id not in economy:
            economy[user_id] = {
                "wallet": 0,
                "bank": 0,
                "total_earned": 0,
                "inventory": {},
                "stocks": {}
            }
        
        old_balance = economy[user_id]["wallet"]
        economy[user_id]["wallet"] = amount
        
        if self.save_economy(economy):
            embed = discord.Embed(
                title="💰 Balance Set",
                description=f"Set {member.mention}'s wallet to **{amount:,}£**",
                color=discord.Color.blue()
            )
            embed.add_field(name="Previous Balance", value=f"{old_balance:,}£", inline=True)
            embed.add_field(name="New Balance", value=f"{amount:,}£", inline=True)
            embed.set_footer(text=f"Action by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} set {member}'s balance to {amount}£")
        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description="Failed to save economy data.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='resetuser')
    async def resetuser(self, ctx, member: discord.Member):
        """Reset a user's economy data completely
        
        Usage: !resetuser @user
        Example: !resetuser @john
        """
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="Cannot reset bot economy data.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        economy = self.load_economy()
        user_id = str(member.id)
        
        if user_id not in economy:
            embed = discord.Embed(
                title="ℹ️ No Data",
                description=f"{member.mention} has no economy data to reset.",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        old_data = economy[user_id].copy()
        del economy[user_id]
        
        if self.save_economy(economy):
            embed = discord.Embed(
                title="🔄 User Reset",
                description=f"Successfully reset all economy data for {member.mention}",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Wallet Cleared",
                value=f"{old_data.get('wallet', 0):,}£",
                inline=True
            )
            embed.add_field(
                name="Bank Cleared",
                value=f"{old_data.get('bank', 0):,}£",
                inline=True
            )
            embed.set_footer(text=f"Action by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} reset economy data for {member}")
        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description="Failed to save economy data.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='viewuser')
    async def viewuser(self, ctx, member: discord.Member):
        """View detailed economy information about a user
        
        Usage: !viewuser @user
        Example: !viewuser @john
        """
        economy = self.load_economy()
        user_id = str(member.id)
        
        if user_id not in economy:
            economy[user_id] = {
                "wallet": 0,
                "bank": 0,
                "total_earned": 0,
                "inventory": {},
                "stocks": {}
            }
        
        user_data = economy[user_id]
        wallet = user_data.get("wallet", 0)
        bank = user_data.get("bank", 0)
        total = wallet + bank
        total_earned = user_data.get("total_earned", 0)
        inventory_count = len(user_data.get("inventory", {}))
        stocks = user_data.get("stocks", {})
        stock_count = sum(stocks.values())
        
        embed = discord.Embed(
            title=f"💼 {member.display_name}'s Economy Profile",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Money info
        embed.add_field(name="💵 Wallet", value=f"{wallet:,}£", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{bank:,}£", inline=True)
        embed.add_field(name="💎 Total", value=f"{total:,}£", inline=True)
        
        # Stats
        embed.add_field(name="📊 Total Earned", value=f"{total_earned:,}£", inline=True)
        embed.add_field(name="🎒 Inventory Items", value=f"{inventory_count}", inline=True)
        embed.add_field(name="📈 Stock Shares", value=f"{stock_count}", inline=True)
        
        embed.set_footer(text=f"User ID: {member.id} | Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='setprice')
    async def setprice(self, ctx, stock_symbol: str, price: int):
        """Set a stock price manually
        
        Usage: !setprice <symbol> <price>
        Example: !setprice TECH 150
        """
        stock_symbol = stock_symbol.upper()
        
        if price <= 0:
            embed = discord.Embed(
                title="❌ Invalid Price",
                description="Price must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        market = self.load_market()
        
        if stock_symbol not in market.get("stocks", {}):
            embed = discord.Embed(
                title="❌ Stock Not Found",
                description=f"Stock symbol `{stock_symbol}` does not exist.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        old_price = market["stocks"][stock_symbol]["price"]
        market["stocks"][stock_symbol]["price"] = price
        
        # Add to history
        if "history" not in market["stocks"][stock_symbol]:
            market["stocks"][stock_symbol]["history"] = []
        
        market["stocks"][stock_symbol]["history"].append({
            "price": price,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only last 100 entries
        if len(market["stocks"][stock_symbol]["history"]) > 100:
            market["stocks"][stock_symbol]["history"] = market["stocks"][stock_symbol]["history"][-100:]
        
        if self.save_market(market):
            stock_name = market["stocks"][stock_symbol]["name"]
            change = price - old_price
            change_percent = ((price - old_price) / old_price * 100) if old_price > 0 else 0
            
            embed = discord.Embed(
                title="📊 Stock Price Updated",
                description=f"**{stock_name}** (`{stock_symbol}`)",
                color=discord.Color.green() if change >= 0 else discord.Color.red()
            )
            embed.add_field(name="Old Price", value=f"{old_price:,}£", inline=True)
            embed.add_field(name="New Price", value=f"{price:,}£", inline=True)
            embed.add_field(
                name="Change",
                value=f"{change:+,}£ ({change_percent:+.2f}%)",
                inline=True
            )
            embed.set_footer(text=f"Updated by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} set {stock_symbol} price to {price}£")
        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description="Failed to save market data.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='addstock')
    async def addstock(self, ctx, symbol: str, name: str, price: int):
        """Add a new stock to the market
        
        Usage: !addstock <symbol> <name> <price>
        Example: !addstock GAME "Gaming Corp" 80
        """
        symbol = symbol.upper()
        
        if price <= 0:
            embed = discord.Embed(
                title="❌ Invalid Price",
                description="Price must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        market = self.load_market()
        
        if symbol in market.get("stocks", {}):
            embed = discord.Embed(
                title="❌ Stock Exists",
                description=f"Stock symbol `{symbol}` already exists.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if "stocks" not in market:
            market["stocks"] = {}
        
        market["stocks"][symbol] = {
            "name": name,
            "price": price,
            "history": [{
                "price": price,
                "timestamp": datetime.utcnow().isoformat()
            }]
        }
        
        if self.save_market(market):
            embed = discord.Embed(
                title="📈 Stock Added",
                description=f"Added **{name}** (`{symbol}`) to the market!",
                color=discord.Color.green()
            )
            embed.add_field(name="Starting Price", value=f"{price:,}£", inline=True)
            embed.set_footer(text=f"Added by {ctx.author.name}")
            
            await ctx.send(embed=embed)
            logger.info(f"{ctx.author} added stock {symbol} ({name}) at {price}£")
        else:
            embed = discord.Embed(
                title="⚠️ Error",
                description="Failed to save market data.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
    
    @commands.command(name='sendnews')
    async def sendnews(self, ctx, channel: discord.TextChannel, *, message: str):
        """Send a market news message to a specific channel
        
        Usage: !sendnews #channel <message>
        Example: !sendnews #economy TECH stock surges 20%!
        """
        embed = discord.Embed(
            title="📰 Market News",
            description=message,
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Market Update")
        
        try:
            await channel.send(embed=embed)
            
            # Save to news history
            market = self.load_market()
            if "news" not in market:
                market["news"] = []
            
            market["news"].append({
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "author": str(ctx.author)
            })
            
            # Keep only last 50 news items
            if len(market["news"]) > 50:
                market["news"] = market["news"][-50:]
            
            self.save_market(market)
            
            confirm_embed = discord.Embed(
                title="✅ News Sent",
                description=f"Market news sent to {channel.mention}",
                color=discord.Color.green()
            )
            await ctx.send(embed=confirm_embed)
            logger.info(f"{ctx.author} sent market news to #{channel.name}")
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description=f"I don't have permission to send messages in {channel.mention}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

async def setup(bot):
    """Load the Admin cog"""
    await bot.add_cog(Admin(bot))
    logger.info("Admin cog loaded")
