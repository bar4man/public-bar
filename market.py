import discord
from discord.ext import commands, tasks
import random
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import math
from economy import db

class MarketSystem:
    """Complex market system with gold and stocks simulation."""
    
    def __init__(self):
        self.market_open = False
        self.market_hours = {"open": 9, "close": 17}  # 9 AM to 5 PM
        self.last_update = datetime.now(timezone.utc)
        self.volatility = 0.02  # 2% daily volatility base
        self.market_sentiment = 0.0  # -1 to 1 scale
        
        # Gold market specifics
        self.gold_price = 1850.0  # Starting price per ounce
        self.gold_volatility = 0.015
        self.gold_demand = 0.0
        
        # Stock definitions
        self.stocks = {
            "TECH": {
                "name": "Quantum Tech Inc.",
                "sector": "Technology",
                "price": 150.0,
                "volatility": 0.025,
                "dividend_yield": 0.012,
                "market_cap": 500000000,
                "pe_ratio": 25.0,
                "description": "Leading AI and quantum computing company"
            },
            "ENERGY": {
                "name": "SolarFlare Energy",
                "sector": "Energy", 
                "price": 85.0,
                "volatility": 0.018,
                "dividend_yield": 0.032,
                "market_cap": 200000000,
                "pe_ratio": 15.0,
                "description": "Renewable energy solutions provider"
            },
            "BANK": {
                "name": "Global Trust Bank",
                "sector": "Financial",
                "price": 45.0,
                "volatility": 0.015,
                "dividend_yield": 0.045,
                "market_cap": 800000000,
                "pe_ratio": 12.0,
                "description": "International banking and financial services"
            },
            "PHARMA": {
                "name": "BioGen Pharmaceuticals", 
                "sector": "Healthcare",
                "price": 120.0,
                "volatility": 0.022,
                "dividend_yield": 0.008,
                "market_cap": 350000000,
                "pe_ratio": 30.0,
                "description": "Biotechnology and pharmaceutical research"
            },
            "AUTO": {
                "name": "EcoMotion Motors",
                "sector": "Automotive",
                "price": 65.0,
                "volatility": 0.020,
                "dividend_yield": 0.015,
                "market_cap": 150000000,
                "pe_ratio": 18.0,
                "description": "Electric vehicle manufacturer"
            }
        }
        
        # Economic indicators
        self.inflation_rate = 0.025
        self.interest_rate = 0.035
        self.gdp_growth = 0.028
        
        # News events that affect markets
        self.news_events = []
        self.generate_news_events()
    
    def generate_news_events(self):
        """Generate random news events that affect market sentiment."""
        events = [
            {"type": "positive", "impact": 0.1, "text": "Strong economic growth reported"},
            {"type": "negative", "impact": -0.08, "text": "Inflation concerns rise"},
            {"type": "positive", "impact": 0.05, "text": "Tech sector shows strong earnings"},
            {"type": "negative", "impact": -0.06, "text": "Energy prices volatile"},
            {"type": "positive", "impact": 0.07, "text": "New government stimulus announced"},
            {"type": "negative", "impact": -0.09, "text": "Global trade tensions increase"},
            {"type": "sector", "sector": "TECH", "impact": 0.12, "text": "Breakthrough in quantum computing"},
            {"type": "sector", "sector": "ENERGY", "impact": -0.1, "text": "Oil supply disruptions"},
            {"type": "gold", "impact": 0.15, "text": "Gold demand surges as safe haven"},
            {"type": "gold", "impact": -0.08, "text": "Strong dollar pressures gold prices"}
        ]
        self.news_events = random.sample(events, 3)  # 3 random events
    
    def calculate_market_sentiment(self):
        """Calculate current market sentiment based on various factors."""
        base_sentiment = random.uniform(-0.2, 0.2)
        
        # Economic factors
        if self.gdp_growth > 0.03:
            base_sentiment += 0.1
        elif self.gdp_growth < 0.02:
            base_sentiment -= 0.1
            
        if self.inflation_rate > 0.03:
            base_sentiment -= 0.15
        elif self.inflation_rate < 0.02:
            base_sentiment += 0.05
            
        # News impact
        for event in self.news_events:
            if event["type"] in ["positive", "negative"]:
                base_sentiment += event["impact"]
        
        # Keep within bounds
        self.market_sentiment = max(-1.0, min(1.0, base_sentiment))
        return self.market_sentiment
    
    def update_prices(self):
        """Update all market prices based on complex algorithms."""
        if not self.market_open:
            return
            
        sentiment = self.calculate_market_sentiment()
        
        # Update gold price
        gold_change = random.gauss(0, self.gold_volatility)
        gold_change += sentiment * 0.01  # Market sentiment effect
        gold_change += self.gold_demand * 0.005  # Demand effect
        
        # Apply news effects to gold
        for event in self.news_events:
            if event["type"] == "gold":
                gold_change += event["impact"] * 0.5
        
        self.gold_price *= (1 + gold_change)
        self.gold_price = max(100.0, min(5000.0, self.gold_price))  # Reasonable bounds
        
        # Update stock prices
        for symbol, stock in self.stocks.items():
            # Base random movement
            change = random.gauss(0, stock["volatility"])
            
            # Market sentiment effect
            change += sentiment * stock["volatility"] * 2
            
            # Sector-specific news
            for event in self.news_events:
                if event.get("sector") == symbol:
                    change += event["impact"]
            
            # Company-specific factors
            earnings_surprise = random.gauss(0, 0.02)
            change += earnings_surprise
            
            # Apply change
            new_price = stock["price"] * (1 + change)
            
            # Prevent extreme values but allow growth/decline
            min_price = stock["price"] * 0.1  # Can drop to 10% of original
            max_price = stock["price"] * 10.0  # Can grow to 10x original
            
            stock["price"] = max(min_price, min(max_price, new_price))
        
        self.last_update = datetime.now(timezone.utc)
    
    def get_market_status(self):
        """Get current market status and trends."""
        status = {
            "market_open": self.market_open,
            "sentiment": self.market_sentiment,
            "gold_price": self.gold_price,
            "last_update": self.last_update,
            "news": self.news_events
        }
        return status

class MarketCog(commands.Cog):
    """Market trading system with gold and stocks."""
    
    def __init__(self, bot):
        self.bot = bot
        self.market = MarketSystem()
        self.price_update_task = self.update_market_prices.start()
        self.market_hours_task = self.manage_market_hours.start()
    
    def cog_unload(self):
        """Cleanup tasks when cog is unloaded."""
        self.price_update_task.cancel()
        self.market_hours_task.cancel()
    
    @tasks.loop(minutes=5)
    async def update_market_prices(self):
        """Update market prices every 5 minutes when market is open."""
        if self.market.market_open:
            self.market.update_prices()
            logging.info("📈 Market prices updated")
    
    @tasks.loop(minutes=1)
    async def manage_market_hours(self):
        """Manage market opening/closing based on UTC time."""
        now = datetime.now(timezone.utc)
        current_hour = now.hour
        
        # Market hours: 9 AM to 5 PM UTC
        if 9 <= current_hour < 17:
            if not self.market.market_open:
                self.market.market_open = True
                self.market.generate_news_events()  # New events each day
                logging.info("🏛️ Market opened for trading")
        else:
            if self.market.market_open:
                self.market.market_open = False
                logging.info("🏛️ Market closed for the day")
    
    async def get_user_portfolio(self, user_id: int) -> Dict:
        """Get user's investment portfolio."""
        user = await db.get_user(user_id)
        portfolio = user.get("portfolio", {
            "gold_ounces": 0.0,
            "stocks": {},
            "total_investment": 0,
            "total_value": 0
        })
        return portfolio
    
    async def update_user_portfolio(self, user_id: int, portfolio: Dict):
        """Update user's investment portfolio."""
        await db.update_user(user_id, {"portfolio": portfolio})
    
    async def create_market_embed(self, title: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
        """Create a standardized market embed."""
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        status = "🟢 OPEN" if self.market.market_open else "🔴 CLOSED"
        sentiment_emoji = "📈" if self.market.market_sentiment > 0 else "📉" if self.market.market_sentiment < 0 else "➡️"
        
        embed.set_footer(text=f"Market: {status} | Sentiment: {sentiment_emoji}")
        return embed
    
    # ========== MARKET COMMANDS ==========
    
    @commands.command(name="market", aliases=["mkt"])
    async def market_status(self, ctx: commands.Context):
        """View current market status and prices."""
        status = self.market.get_market_status()
        
        embed = await self.create_market_embed("🏛️ Financial Markets")
        
        # Market overview
        status_text = "**OPEN** 🟢" if status["market_open"] else "**CLOSED** 🔴"
        sentiment_text = f"{status['sentiment']:+.2f}"
        
        embed.add_field(
            name="📊 Market Overview",
            value=f"Status: {status_text}\nSentiment: {sentiment_text}\nGold: ${status['gold_price']:,.2f}/oz",
            inline=False
        )
        
        # Stock prices
        stocks_text = ""
        for symbol, stock in self.market.stocks.items():
            change_emoji = "📈" if stock["price"] > 150 else "📉" if stock["price"] < 150 else "➡️"
            stocks_text += f"**{symbol}**: ${stock['price']:,.2f} {change_emoji}\n"
        
        embed.add_field(name="💹 Stocks", value=stocks_text, inline=True)
        
        # Economic indicators
        econ_text = f"""
        Inflation: {self.market.inflation_rate:.1%}
        Interest Rate: {self.market.interest_rate:.1%}
        GDP Growth: {self.market.gdp_growth:.1%}
        """
        embed.add_field(name="📈 Economy", value=econ_text, inline=True)
        
        # News highlights
        if status["news"]:
            news_text = "\n".join([f"• {event['text']}" for event in status["news"][:2]])
            embed.add_field(name="📰 Market News", value=news_text, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="stocks", aliases=["stock"])
    async def stocks_info(self, ctx: commands.Context, symbol: str = None):
        """View detailed stock information."""
        if symbol and symbol.upper() in self.market.stocks:
            # Specific stock info
            stock = self.market.stocks[symbol.upper()]
            
            embed = await self.create_market_embed(f"💹 {stock['name']} ({symbol.upper()})")
            
            embed.description = stock["description"]
            
            embed.add_field(name="💰 Current Price", value=f"${stock['price']:,.2f}", inline=True)
            embed.add_field(name="🏢 Sector", value=stock["sector"], inline=True)
            embed.add_field(name="📊 Volatility", value=f"{stock['volatility']:.1%}", inline=True)
            
            embed.add_field(name="💸 Dividend Yield", value=f"{stock['dividend_yield']:.1%}", inline=True)
            embed.add_field(name="📈 P/E Ratio", value=f"{stock['pe_ratio']:.1f}", inline=True)
            embed.add_field(name="💎 Market Cap", value=f"${stock['market_cap']:,}", inline=True)
            
            # Buy/sell recommendation based on simple analysis
            if stock["pe_ratio"] < 15:
                recommendation = "🟢 Undervalued (Consider Buying)"
            elif stock["pe_ratio"] > 25:
                recommendation = "🔴 Overvalued (Consider Selling)"
            else:
                recommendation = "🟡 Fairly Valued (Hold)"
            
            embed.add_field(name="💡 Analysis", value=recommendation, inline=False)
            
        else:
            # All stocks overview
            embed = await self.create_market_embed("💹 Available Stocks")
            
            for symbol, stock in self.market.stocks.items():
                stock_info = (
                    f"Price: ${stock['price']:,.2f}\n"
                    f"Sector: {stock['sector']}\n"
                    f"Div: {stock['dividend_yield']:.1%} | P/E: {stock['pe_ratio']:.1f}"
                )
                embed.add_field(
                    name=f"{symbol} - {stock['name']}",
                    value=stock_info,
                    inline=True
                )
            
            embed.add_field(
                name="💡 Usage",
                value="Use `~~stock <SYMBOL>` for detailed analysis\nExample: `~~stock TECH`",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="gold")
    async def gold_info(self, ctx: commands.Context):
        """View gold market information."""
        embed = await self.create_market_embed("🥇 Gold Market")
        
        gold = self.market.gold_price
        change_today = random.uniform(-2.0, 2.0)  # Simulate daily change
        
        embed.description = "Gold is a safe-haven asset that typically performs well during economic uncertainty."
        
        embed.add_field(name="💰 Current Price", value=f"${gold:,.2f} per ounce", inline=True)
        embed.add_field(name="📈 Change Today", value=f"{change_today:+.2f}%", inline=True)
        embed.add_field(name="📊 Volatility", value=f"{self.market.gold_volatility:.1%}", inline=True)
        
        # Gold analysis
        if gold < 1500:
            analysis = "🟢 Potentially Undervalued - Good buying opportunity"
        elif gold > 2000:
            analysis = "🔴 Potentially Overvalued - Consider profit-taking"
        else:
            analysis = "🟡 Fairly Valued - Monitor market conditions"
        
        embed.add_field(name="💡 Market Analysis", value=analysis, inline=False)
        
        # Factors affecting gold
        factors = [
            f"Inflation: {'High' if self.market.inflation_rate > 0.03 else 'Moderate'}",
            f"Market Sentiment: {'Risk-Off' if self.market.market_sentiment < 0 else 'Risk-On'}",
            f"Interest Rates: {'Rising' if self.market.interest_rate > 0.04 else 'Stable'}"
        ]
        
        embed.add_field(name="📰 Key Factors", value="\n".join(f"• {f}" for f in factors), inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="buyasset", aliases=["buy"])
    async def buy_asset(self, ctx: commands.Context, asset_type: str, symbol: str = None, amount: float = None):
        """Buy stocks or gold."""
        if not self.market.market_open:
            embed = await self.create_market_embed("❌ Market Closed", discord.Color.red())
            embed.description = "Trading is only available during market hours (9 AM - 5 PM UTC)."
            return await ctx.send(embed=embed)
        
        if asset_type.lower() not in ["stock", "gold"]:
            embed = await self.create_market_embed("❌ Invalid Asset Type", discord.Color.red())
            embed.description = "Available types: `stock`, `gold`\nExample: `~~buy stock TECH 10`"
            return await ctx.send(embed=embed)
        
        if amount is None or amount <= 0:
            embed = await self.create_market_embed("❌ Invalid Amount", discord.Color.red())
            embed.description = "Please specify a positive amount to buy."
            return await ctx.send(embed=embed)
        
        user_data = await db.get_user(ctx.author.id)
        portfolio = await self.get_user_portfolio(ctx.author.id)
        
        if asset_type.lower() == "gold":
            # Buy gold
            cost = amount * self.market.gold_price
            fee = cost * 0.01  # 1% transaction fee
            
            if user_data["bank"] < cost + fee:
                embed = await self.create_market_embed("❌ Insufficient Funds", discord.Color.red())
                embed.description = f"You need ${cost + fee:,.2f} in your bank (including 1% fee), but only have ${user_data['bank']:,.2f}."
                return await ctx.send(embed=embed)
            
            # Execute purchase
            portfolio["gold_ounces"] += amount
            portfolio["total_investment"] += cost + fee
            await self.update_user_portfolio(ctx.author.id, portfolio)
            await db.update_balance(ctx.author.id, bank_change=-(cost + fee))
            
            embed = await self.create_market_embed("✅ Gold Purchase Complete", discord.Color.green())
            embed.description = f"Bought {amount:.2f} oz of gold for ${cost:,.2f}"
            embed.add_field(name="💰 Cost", value=f"${cost:,.2f}", inline=True)
            embed.add_field(name="💸 Fee", value=f"${fee:,.2f}", inline=True)
            embed.add_field(name="🥇 Total Gold", value=f"{portfolio['gold_ounces']:.2f} oz", inline=True)
            
        else:
            # Buy stocks
            if not symbol or symbol.upper() not in self.market.stocks:
                embed = await self.create_market_embed("❌ Invalid Stock Symbol", discord.Color.red())
                embed.description = f"Available stocks: {', '.join(self.market.stocks.keys())}"
                return await ctx.send(embed=embed)
            
            symbol = symbol.upper()
            stock = self.market.stocks[symbol]
            cost = amount * stock["price"]
            fee = cost * 0.005  # 0.5% transaction fee for stocks
            
            if user_data["bank"] < cost + fee:
                embed = await self.create_market_embed("❌ Insufficient Funds", discord.Color.red())
                embed.description = f"You need ${cost + fee:,.2f} in your bank (including 0.5% fee), but only have ${user_data['bank']:,.2f}."
                return await ctx.send(embed=embed)
            
            # Execute purchase
            if symbol not in portfolio["stocks"]:
                portfolio["stocks"][symbol] = 0.0
            
            portfolio["stocks"][symbol] += amount
            portfolio["total_investment"] += cost + fee
            await self.update_user_portfolio(ctx.author.id, portfolio)
            await db.update_balance(ctx.author.id, bank_change=-(cost + fee))
            
            embed = await self.create_market_embed("✅ Stock Purchase Complete", discord.Color.green())
            embed.description = f"Bought {amount:.0f} shares of {stock['name']} for ${cost:,.2f}"
            embed.add_field(name="💰 Cost", value=f"${cost:,.2f}", inline=True)
            embed.add_field(name="💸 Fee", value=f"${fee:,.2f}", inline=True)
            embed.add_field(name="📊 Total Shares", value=f"{portfolio['stocks'][symbol]:.0f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="sellasset", aliases=["sell"])
    async def sell_asset(self, ctx: commands.Context, asset_type: str, symbol: str = None, amount: float = None):
        """Sell stocks or gold."""
        if not self.market.market_open:
            embed = await self.create_market_embed("❌ Market Closed", discord.Color.red())
            embed.description = "Trading is only available during market hours (9 AM - 5 PM UTC)."
            return await ctx.send(embed=embed)
        
        if asset_type.lower() not in ["stock", "gold"]:
            embed = await self.create_market_embed("❌ Invalid Asset Type", discord.Color.red())
            embed.description = "Available types: `stock`, `gold`\nExample: `~~sell stock TECH 5`"
            return await ctx.send(embed=embed)
        
        if amount is None or amount <= 0:
            embed = await self.create_market_embed("❌ Invalid Amount", discord.Color.red())
            embed.description = "Please specify a positive amount to sell."
            return await ctx.send(embed=embed)
        
        portfolio = await self.get_user_portfolio(ctx.author.id)
        
        if asset_type.lower() == "gold":
            # Sell gold
            if portfolio["gold_ounces"] < amount:
                embed = await self.create_market_embed("❌ Insufficient Gold", discord.Color.red())
                embed.description = f"You only have {portfolio['gold_ounces']:.2f} oz of gold."
                return await ctx.send(embed=embed)
            
            proceeds = amount * self.market.gold_price
            fee = proceeds * 0.01  # 1% transaction fee
            
            # Execute sale
            portfolio["gold_ounces"] -= amount
            portfolio["total_investment"] -= (amount * self.market.gold_price)  # Approximate cost basis
            await self.update_user_portfolio(ctx.author.id, portfolio)
            await db.update_balance(ctx.author.id, bank_change=proceeds - fee)
            
            embed = await self.create_market_embed("✅ Gold Sale Complete", discord.Color.green())
            embed.description = f"Sold {amount:.2f} oz of gold for ${proceeds:,.2f}"
            embed.add_field(name="💰 Proceeds", value=f"${proceeds:,.2f}", inline=True)
            embed.add_field(name="💸 Fee", value=f"${fee:,.2f}", inline=True)
            embed.add_field(name="🥇 Remaining Gold", value=f"{portfolio['gold_ounces']:.2f} oz", inline=True)
            
        else:
            # Sell stocks
            if not symbol or symbol.upper() not in self.market.stocks:
                embed = await self.create_market_embed("❌ Invalid Stock Symbol", discord.Color.red())
                embed.description = f"Available stocks: {', '.join(self.market.stocks.keys())}"
                return await ctx.send(embed=embed)
            
            symbol = symbol.upper()
            
            if symbol not in portfolio["stocks"] or portfolio["stocks"][symbol] < amount:
                embed = await self.create_market_embed("❌ Insufficient Shares", discord.Color.red())
                embed.description = f"You don't have enough shares of {symbol}."
                return await ctx.send(embed=embed)
            
            stock = self.market.stocks[symbol]
            proceeds = amount * stock["price"]
            fee = proceeds * 0.005  # 0.5% transaction fee
            
            # Execute sale
            portfolio["stocks"][symbol] -= amount
            if portfolio["stocks"][symbol] == 0:
                del portfolio["stocks"][symbol]
            
            portfolio["total_investment"] -= (amount * stock["price"])  # Approximate cost basis
            await self.update_user_portfolio(ctx.author.id, portfolio)
            await db.update_balance(ctx.author.id, bank_change=proceeds - fee)
            
            embed = await self.create_market_embed("✅ Stock Sale Complete", discord.Color.green())
            embed.description = f"Sold {amount:.0f} shares of {stock['name']} for ${proceeds:,.2f}"
            embed.add_field(name="💰 Proceeds", value=f"${proceeds:,.2f}", inline=True)
            embed.add_field(name="💸 Fee", value=f"${fee:,.2f}", inline=True)
            embed.add_field(name="📊 Remaining Shares", value=f"{portfolio['stocks'].get(symbol, 0):.0f}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="portfolio", aliases=["port"])
    async def view_portfolio(self, ctx: commands.Context, member: discord.Member = None):
        """View your investment portfolio."""
        member = member or ctx.author
        user_data = await db.get_user(member.id)
        portfolio = await self.get_user_portfolio(member.id)
        
        embed = await self.create_market_embed(f"💼 {member.display_name}'s Investment Portfolio")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Calculate current values
        gold_value = portfolio["gold_ounces"] * self.market.gold_price
        
        stock_value = 0
        stocks_text = ""
        for symbol, shares in portfolio["stocks"].items():
            if symbol in self.market.stocks:
                value = shares * self.market.stocks[symbol]["price"]
                stock_value += value
                stocks_text += f"**{symbol}**: {shares:.0f} shares (${value:,.2f})\n"
        
        total_value = gold_value + stock_value
        profit_loss = total_value - portfolio["total_investment"]
        profit_percentage = (profit_loss / portfolio["total_investment"] * 100) if portfolio["total_investment"] > 0 else 0
        
        # Portfolio summary
        embed.add_field(
            name="📊 Portfolio Summary",
            value=(
                f"**Total Value**: ${total_value:,.2f}\n"
                f"**Total Invested**: ${portfolio['total_investment']:,.2f}\n"
                f"**Profit/Loss**: ${profit_loss:,.2f} ({profit_percentage:+.1f}%)"
            ),
            inline=False
        )
        
        # Gold holdings
        if portfolio["gold_ounces"] > 0:
            embed.add_field(
                name="🥇 Gold Holdings",
                value=f"{portfolio['gold_ounces']:.2f} oz (${gold_value:,.2f})",
                inline=True
            )
        
        # Stock holdings
        if portfolio["stocks"]:
            embed.add_field(
                name="💹 Stock Holdings",
                value=stocks_text or "No stocks",
                inline=True
            )
        
        # Performance indicator
        if profit_percentage > 10:
            performance = "🎯 Excellent Performance!"
        elif profit_percentage > 0:
            performance = "📈 Good Performance"
        elif profit_percentage > -10:
            performance = "📉 Moderate Performance"
        else:
            performance = "⚠️ Needs Improvement"
        
        embed.add_field(name="📈 Performance", value=performance, inline=False)
        
        if member == ctx.author:
            embed.add_field(
                name="💡 Trading Tips",
                value="• Buy low, sell high!\n• Diversify your investments\n• Monitor market news\n• Use `~~market` for current prices",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="news")
    async def market_news(self, ctx: commands.Context):
        """View current market news and events."""
        embed = await self.create_market_embed("📰 Market News & Events")
        
        if not self.market.news_events:
            embed.description = "No major market news at the moment."
        else:
            for i, event in enumerate(self.market.news_events, 1):
                impact_emoji = "📈" if event["impact"] > 0 else "📉" if event["impact"] < 0 else "➡️"
                embed.add_field(
                    name=f"{impact_emoji} News #{i}",
                    value=event["text"],
                    inline=False
                )
            
            embed.add_field(
                name="💡 Impact",
                value="Positive news 📈 typically boosts prices\nNegative news 📉 typically lowers prices",
                inline=False
            )
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MarketCog(bot))
