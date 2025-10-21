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
    """Enhanced market system with gold and stocks simulation."""
    
    def __init__(self):
        self.market_open = False
        self.market_hours = {"open": 9, "close": 17}  # 9 AM to 5 PM UTC
        self.last_update = datetime.now(timezone.utc)
        self.volatility = 0.02  # 2% daily volatility base
        self.market_sentiment = 0.0  # -1 to 1 scale
        
        # Gold market specifics
        self.gold_price = 1850.0  # Starting price per ounce
        self.gold_volatility = 0.015
        self.gold_demand = 0.0
        
        # Stock definitions with more realistic data
        self.stocks = {
            "TECH": {
                "name": "Quantum Tech Inc.",
                "sector": "Technology",
                "price": 150.0,
                "previous_price": 150.0,  # Track previous price for change calculation
                "volatility": 0.025,
                "dividend_yield": 0.012,
                "market_cap": 500000000,
                "pe_ratio": 25.0,
                "description": "Leading AI and quantum computing company",
                "volume": 0,  # Trading volume
                "day_high": 150.0,
                "day_low": 150.0
            },
            "ENERGY": {
                "name": "SolarFlare Energy",
                "sector": "Energy", 
                "price": 85.0,
                "previous_price": 85.0,
                "volatility": 0.018,
                "dividend_yield": 0.032,
                "market_cap": 200000000,
                "pe_ratio": 15.0,
                "description": "Renewable energy solutions provider",
                "volume": 0,
                "day_high": 85.0,
                "day_low": 85.0
            },
            "BANK": {
                "name": "Global Trust Bank",
                "sector": "Financial",
                "price": 45.0,
                "previous_price": 45.0,
                "volatility": 0.015,
                "dividend_yield": 0.045,
                "market_cap": 800000000,
                "pe_ratio": 12.0,
                "description": "International banking and financial services",
                "volume": 0,
                "day_high": 45.0,
                "day_low": 45.0
            },
            "PHARMA": {
                "name": "BioGen Pharmaceuticals", 
                "sector": "Healthcare",
                "price": 120.0,
                "previous_price": 120.0,
                "volatility": 0.022,
                "dividend_yield": 0.008,
                "market_cap": 350000000,
                "pe_ratio": 30.0,
                "description": "Biotechnology and pharmaceutical research",
                "volume": 0,
                "day_high": 120.0,
                "day_low": 120.0
            },
            "AUTO": {
                "name": "EcoMotion Motors",
                "sector": "Automotive",
                "price": 65.0,
                "previous_price": 65.0,
                "volatility": 0.020,
                "dividend_yield": 0.015,
                "market_cap": 150000000,
                "pe_ratio": 18.0,
                "description": "Electric vehicle manufacturer",
                "volume": 0,
                "day_high": 65.0,
                "day_low": 65.0
            }
        }
        
        # Economic indicators
        self.inflation_rate = 0.025
        self.interest_rate = 0.035
        self.gdp_growth = 0.028
        
        # News events that affect markets
        self.news_events = []
        self.market_trend = "stable"  # bull, bear, stable
        self.generate_news_events()
        
        # Trading volume tracking
        self.daily_volume = 0
        self.market_cap_total = sum(stock["market_cap"] for stock in self.stocks.values())
    
    def generate_news_events(self):
        """Generate random news events that affect market sentiment."""
        positive_events = [
            {"type": "positive", "impact": 0.1, "text": "Strong economic growth reported across sectors"},
            {"type": "positive", "impact": 0.08, "text": "Consumer confidence reaches all-time high"},
            {"type": "positive", "impact": 0.12, "text": "Government announces major infrastructure spending"},
            {"type": "positive", "impact": 0.06, "text": "Unemployment rate drops to record low"},
            {"type": "positive", "impact": 0.09, "text": "Global markets show strong recovery signs"}
        ]
        
        negative_events = [
            {"type": "negative", "impact": -0.08, "text": "Inflation concerns rise among investors"},
            {"type": "negative", "impact": -0.11, "text": "Global trade tensions escalate"},
            {"type": "negative", "impact": -0.07, "text": "Manufacturing data shows slowdown"},
            {"type": "negative", "impact": -0.09, "text": "Housing market shows signs of cooling"},
            {"type": "negative", "impact": -0.13, "text": "Geopolitical tensions affect global markets"}
        ]
        
        sector_events = [
            {"type": "sector", "sector": "TECH", "impact": 0.15, "text": "Breakthrough in quantum computing announced"},
            {"type": "sector", "sector": "TECH", "impact": -0.12, "text": "Tech sector faces regulatory scrutiny"},
            {"type": "sector", "sector": "ENERGY", "impact": 0.14, "text": "Renewable energy adoption exceeds expectations"},
            {"type": "sector", "sector": "ENERGY", "impact": -0.10, "text": "Oil supply disruptions affect energy sector"},
            {"type": "sector", "sector": "BANK", "impact": 0.08, "text": "Banks report strong quarterly earnings"},
            {"type": "sector", "sector": "BANK", "impact": -0.11, "text": "Interest rate concerns weigh on banking stocks"},
            {"type": "sector", "sector": "PHARMA", "impact": 0.18, "text": "New drug approval boosts pharmaceutical sector"},
            {"type": "sector", "sector": "PHARMA", "impact": -0.09, "text": "Clinical trial results disappoint investors"},
            {"type": "sector", "sector": "AUTO", "impact": 0.12, "text": "Electric vehicle sales surge globally"},
            {"type": "sector", "sector": "AUTO", "impact": -0.08, "text": "Supply chain issues affect auto manufacturers"}
        ]
        
        gold_events = [
            {"type": "gold", "impact": 0.15, "text": "Gold demand surges as safe haven asset"},
            {"type": "gold", "impact": -0.08, "text": "Strong dollar pressures gold prices downward"},
            {"type": "gold", "impact": 0.12, "text": "Central banks increase gold reserves"},
            {"type": "gold", "impact": -0.06, "text": "Improved economic outlook reduces gold appeal"}
        ]
        
        # Mix events for variety
        all_events = positive_events + negative_events + sector_events + gold_events
        self.news_events = random.sample(all_events, min(5, len(all_events)))  # 5 random events
        
        # Determine market trend based on news
        total_impact = sum(event["impact"] for event in self.news_events)
        if total_impact > 0.1:
            self.market_trend = "bull"
        elif total_impact < -0.1:
            self.market_trend = "bear"
        else:
            self.market_trend = "stable"
    
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
            
        if self.interest_rate > 0.04:
            base_sentiment -= 0.1
        elif self.interest_rate < 0.03:
            base_sentiment += 0.05
            
        # News impact
        for event in self.news_events:
            if event["type"] in ["positive", "negative"]:
                base_sentiment += event["impact"]
        
        # Market trend influence
        if self.market_trend == "bull":
            base_sentiment += 0.1
        elif self.market_trend == "bear":
            base_sentiment -= 0.1
        
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
        
        # Update gold price and track day high/low
        old_gold_price = self.gold_price
        self.gold_price *= (1 + gold_change)
        self.gold_price = max(100.0, min(5000.0, self.gold_price))  # Reasonable bounds
        
        # Update stock prices
        for symbol, stock in self.stocks.items():
            # Store previous price
            stock["previous_price"] = stock["price"]
            
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
            
            # Update day high/low
            stock["day_high"] = max(stock["day_high"], stock["price"])
            stock["day_low"] = min(stock["day_low"], stock["price"])
            
            # Simulate some trading volume
            stock["volume"] += random.randint(1000, 10000)
            self.daily_volume += stock["volume"]
        
        self.last_update = datetime.now(timezone.utc)
    
    def get_price_change(self, symbol):
        """Calculate price change percentage for a stock."""
        if symbol in self.stocks:
            stock = self.stocks[symbol]
            if stock["previous_price"] > 0:
                return ((stock["price"] - stock["previous_price"]) / stock["previous_price"]) * 100
        return 0
    
    def get_market_status(self):
        """Get current market status and trends."""
        # Calculate overall market change
        total_change = 0
        for symbol in self.stocks:
            total_change += self.get_price_change(symbol)
        avg_change = total_change / len(self.stocks)
        
        status = {
            "market_open": self.market_open,
            "sentiment": self.market_sentiment,
            "trend": self.market_trend,
            "gold_price": self.gold_price,
            "market_change": avg_change,
            "daily_volume": self.daily_volume,
            "last_update": self.last_update,
            "news": self.news_events
        }
        return status

class MarketCog(commands.Cog):
    """Enhanced market trading system with gold and stocks."""
    
    def __init__(self, bot):
        self.bot = bot
        self.market = MarketSystem()
        self.price_update_task = self.update_market_prices.start()
        self.market_hours_task = self.manage_market_hours.start()
        self.news_announcement_task = self.announce_market_news.start()
        self.announcement_channel_id = None
    
    def cog_unload(self):
        """Cleanup tasks when cog is unloaded."""
        self.price_update_task.cancel()
        self.market_hours_task.cancel()
        self.news_announcement_task.cancel()
    
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
                # Reset daily stats
                for stock in self.market.stocks.values():
                    stock["day_high"] = stock["price"]
                    stock["day_low"] = stock["price"]
                    stock["volume"] = 0
                self.market.daily_volume = 0
                logging.info("🏛️ Market opened for trading")
                
                # Send market open announcement
                await self.send_market_announcement("🔔 **Market Open**\nTrading is now active for the day!")
        else:
            if self.market.market_open:
                self.market.market_open = False
                logging.info("🏛️ Market closed for the day")
                
                # Send market close announcement with daily summary
                await self.send_market_announcement("🔔 **Market Closed**\nTrading has ended for the day.")
    
    @tasks.loop(minutes=30)
    async def announce_market_news(self):
        """Automatically send market news and updates."""
        if not self.market.market_open:
            return
            
        # 20% chance to send news every 30 minutes when market is open
        if random.random() < 0.2:
            await self.send_market_update()
    
    async def send_market_announcement(self, message):
        """Send announcement to configured channel."""
        if self.announcement_channel_id:
            channel = self.bot.get_channel(self.announcement_channel_id)
            if channel:
                embed = await self.create_market_embed("🏛️ Market Announcement", discord.Color.gold())
                embed.description = message
                
                # Add current market status for open/close announcements
                if "open" in message.lower() or "close" in message.lower():
                    status = self.market.get_market_status()
                    trend_emoji = "📈" if status["trend"] == "bull" else "📉" if status["trend"] == "bear" else "➡️"
                    embed.add_field(
                        name="📊 Market Overview",
                        value=f"Sentiment: {status['sentiment']:+.2f}\nTrend: {status['trend'].title()} {trend_emoji}",
                        inline=True
                    )
                    
                    # Top movers
                    movers = self.get_top_movers()
                    if movers:
                        movers_text = "\n".join([f"**{symbol}**: {change:+.1f}%" for symbol, change in movers[:3]])
                        embed.add_field(name="🚀 Top Movers", value=movers_text, inline=True)
                
                await channel.send(embed=embed)
    
    async def send_market_update(self):
        """Send periodic market updates."""
        if not self.announcement_channel_id:
            return
            
        channel = self.bot.get_channel(self.announcement_channel_id)
        if not channel:
            return
            
        status = self.market.get_market_status()
        
        # Only send updates if there's significant movement or important news
        if abs(status["market_change"]) > 1 or any(abs(event["impact"]) > 0.1 for event in status["news"]):
            embed = await self.create_market_embed("📰 Market Update", discord.Color.blue())
            
            # Market summary
            change_emoji = "📈" if status["market_change"] > 0 else "📉" if status["market_change"] < 0 else "➡️"
            embed.add_field(
                name="📊 Market Summary",
                value=f"Overall Change: {status['market_change']:+.2f}% {change_emoji}\nGold: ${status['gold_price']:,.2f}/oz",
                inline=False
            )
            
            # Top movers
            movers = self.get_top_movers()
            if movers:
                movers_text = "\n".join([f"**{symbol}**: {change:+.1f}%" for symbol, change in movers[:3]])
                embed.add_field(name="🚀 Top Movers", value=movers_text, inline=True)
            
            # Latest news highlight
            if status["news"]:
                latest_news = status["news"][0]
                impact_emoji = "📈" if latest_news["impact"] > 0 else "📉" if latest_news["impact"] < 0 else "📰"
                embed.add_field(
                    name=f"{impact_emoji} Market News",
                    value=latest_news["text"],
                    inline=False
                )
            
            await channel.send(embed=embed)
    
    def get_top_movers(self, count=5):
        """Get top gaining and losing stocks."""
        movers = []
        for symbol in self.market.stocks:
            change = self.market.get_price_change(symbol)
            movers.append((symbol, change))
        
        # Sort by absolute change (biggest movers first)
        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        return movers[:count]
    
    async def get_user_portfolio(self, user_id: int) -> Dict:
        """Get user's investment portfolio."""
        user = await db.get_user(user_id)
        portfolio = user.get("portfolio", {
            "gold_ounces": 0.0,
            "stocks": {},
            "total_investment": 0,
            "total_value": 0,
            "daily_pnl": 0,
            "total_pnl": 0
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
    
    @commands.command(name="setmarketchannel")
    @commands.has_permissions(administrator=True)
    async def set_market_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set the channel for market announcements and news."""
        channel = channel or ctx.channel
        self.announcement_channel_id = channel.id
        
        embed = await self.create_market_embed("✅ Market Channel Set", discord.Color.green())
        embed.description = f"Market announcements and news will now be sent to {channel.mention}"
        await ctx.send(embed=embed)
    
    @commands.command(name="market", aliases=["mkt"])
    async def market_status(self, ctx: commands.Context):
        """View current market status and prices."""
        status = self.market.get_market_status()
        
        embed = await self.create_market_embed("🏛️ Financial Markets")
        
        # Market overview
        status_text = "**OPEN** 🟢" if status["market_open"] else "**CLOSED** 🔴"
        trend_emoji = "📈" if status["trend"] == "bull" else "📉" if status["trend"] == "bear" else "➡️"
        
        embed.add_field(
            name="📊 Market Overview",
            value=(
                f"Status: {status_text}\n"
                f"Trend: {status['trend'].title()} {trend_emoji}\n"
                f"Sentiment: {status['sentiment']:+.2f}\n"
                f"Daily Volume: {status['daily_volume']:,}\n"
                f"Gold: ${status['gold_price']:,.2f}/oz"
            ),
            inline=False
        )
        
        # Stock prices with changes
        stocks_text = ""
        for symbol, stock in self.market.stocks.items():
            change = self.market.get_price_change(symbol)
            change_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            stocks_text += f"**{symbol}**: ${stock['price']:,.2f} ({change:+.1f}%) {change_emoji}\n"
        
        embed.add_field(name="💹 Stocks", value=stocks_text, inline=True)
        
        # Top movers
        movers = self.get_top_movers(3)
        if movers:
            movers_text = "\n".join([f"**{symbol}**: {change:+.1f}%" for symbol, change in movers])
            embed.add_field(name="🚀 Top Movers", value=movers_text, inline=True)
        
        # Economic indicators
        econ_text = (
            f"Inflation: {self.market.inflation_rate:.1%}\n"
            f"Interest Rate: {self.market.interest_rate:.1%}\n"
            f"GDP Growth: {self.market.gdp_growth:.1%}"
        )
        embed.add_field(name="📈 Economy", value=econ_text, inline=True)
        
        # News highlights
        if status["news"]:
            news_text = "\n".join([f"• {event['text']}" for event in status["news"][:2]])
            embed.add_field(name="📰 Market News", value=news_text, inline=False)
        
        await ctx.send(embed=embed)

    # ... (rest of your existing market commands remain the same - stocks, gold, buy, sell, portfolio, news)

    @commands.command(name="topmovers")
    async def top_movers(self, ctx: commands.Context):
        """View today's top gaining and losing stocks."""
        movers = self.get_top_movers(10)  # Get top 10 movers
        
        embed = await self.create_market_embed("🚀 Today's Top Movers")
        
        gainers = [(sym, chg) for sym, chg in movers if chg > 0]
        losers = [(sym, chg) for sym, chg in movers if chg < 0]
        
        if gainers:
            gainers_text = "\n".join([f"**{symbol}**: +{change:.1f}% 📈" for symbol, change in gainers[:5]])
            embed.add_field(name="📈 Top Gainers", value=gainers_text, inline=True)
        
        if losers:
            losers_text = "\n".join([f"**{symbol}**: {change:.1f}% 📉" for symbol, change in losers[:5]])
            embed.add_field(name="📉 Top Losers", value=losers_text, inline=True)
        
        if not gainers and not losers:
            embed.description = "No significant price movements today."
        
        await ctx.send(embed=embed)
    
    @commands.command(name="forcnews")
    @commands.has_permissions(administrator=True)
    async def force_news(self, ctx: commands.Context):
        """Force generate new market news (Admin only)."""
        self.market.generate_news_events()
        
        embed = await self.create_market_embed("📰 News Regenerated", discord.Color.green())
        embed.description = "Market news has been refreshed!"
        
        # Show new news
        if self.market.news_events:
            news_text = "\n".join([f"• {event['text']}" for event in self.market.news_events[:3]])
            embed.add_field(name="Latest News", value=news_text, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MarketCog(bot))
