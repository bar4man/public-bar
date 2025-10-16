import discord
from discord.ext import commands
import json
import os
import asyncio
import random
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
import aiofiles

class Economy(commands.Cog):
    """Enhanced economy system with shop, games, and more earning opportunities."""
    
    def __init__(self, bot):
        self.bot = bot
        self.econ_file = "data/economy.json"
        self.cooldowns_file = "data/cooldowns.json"
        self.shop_file = "data/shop.json"
        self.inventory_file = "data/inventory.json"
        self.lock = asyncio.Lock()
        self._ensure_directories()
        self._initialize_shop()
    
    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        os.makedirs("data", exist_ok=True)
    
    def _initialize_shop(self):
        """Initialize the shop with default items if it doesn't exist."""
        default_shop = {
            "items": [
                {
                    "id": 1,
                    "name": "💰 Small Bank Upgrade",
                    "description": "Increase your bank limit by 5,000£",
                    "price": 2000,
                    "type": "upgrade",
                    "effect": {"bank_limit": 5000},
                    "emoji": "💰",
                    "stock": -1  # Unlimited
                },
                {
                    "id": 2,
                    "name": "🏦 Medium Bank Upgrade",
                    "description": "Increase your bank limit by 15,000£",
                    "price": 5000,
                    "type": "upgrade",
                    "effect": {"bank_limit": 15000},
                    "emoji": "🏦",
                    "stock": -1
                },
                {
                    "id": 3,
                    "name": "💎 Large Bank Upgrade",
                    "description": "Increase your bank limit by 50,000£",
                    "price": 15000,
                    "type": "upgrade",
                    "effect": {"bank_limit": 50000},
                    "emoji": "💎",
                    "stock": -1
                },
                {
                    "id": 4,
                    "name": "🎩 Lucky Hat",
                    "description": "Increases daily reward by 20% for 7 days",
                    "price": 3000,
                    "type": "consumable",
                    "effect": {"daily_bonus": 1.2, "duration": 7},
                    "emoji": "🎩",
                    "stock": -1
                },
                {
                    "id": 5,
                    "name": "🍀 Lucky Charm",
                    "description": "Increases work earnings by 30% for 5 days",
                    "price": 2500,
                    "type": "consumable",
                    "effect": {"work_bonus": 1.3, "duration": 5},
                    "emoji": "🍀",
                    "stock": -1
                },
                {
                    "id": 6,
                    "name": "🎯 Gambler's Dice",
                    "description": "25% better gambling odds for 3 uses",
                    "price": 4000,
                    "type": "consumable",
                    "effect": {"gamble_bonus": 1.25, "uses": 3},
                    "emoji": "🎯",
                    "stock": -1
                },
                {
                    "id": 7,
                    "name": "💼 Professional Tools",
                    "description": "Permanent 10% increase to work earnings",
                    "price": 10000,
                    "type": "permanent",
                    "effect": {"work_multiplier": 1.1},
                    "emoji": "💼",
                    "stock": -1
                },
                {
                    "id": 8,
                    "name": "🪙 Coin Multiplier",
                    "description": "Permanent 5% increase to all earnings",
                    "price": 20000,
                    "type": "permanent",
                    "effect": {"global_multiplier": 1.05},
                    "emoji": "🪙",
                    "stock": -1
                },
                {
                    "id": 9,
                    "name": "🎁 Mystery Box",
                    "description": "Random reward between 500-5000£",
                    "price": 1000,
                    "type": "consumable",
                    "effect": {"mystery_box": True},
                    "emoji": "🎁",
                    "stock": 5  # Limited stock per user refresh
                },
                {
                    "id": 10,
                    "name": "🛡️ Crime Insurance",
                    "description": "Prevent money loss from failed crimes for 5 uses",
                    "price": 3500,
                    "type": "consumable",
                    "effect": {"crime_insurance": 5},
                    "emoji": "🛡️",
                    "stock": -1
                }
            ]
        }
        
        if not os.path.exists(self.shop_file):
            with open(self.shop_file, "w") as f:
                json.dump(default_shop, f, indent=2)

    # ---------------- Enhanced File Operations ----------------
    async def load_data(self) -> Dict:
        """Load economy data with aiofiles for async operations."""
        async with self.lock:
            try:
                async with aiofiles.open(self.econ_file, "r") as f:
                    content = await f.read()
                    return json.loads(content) if content else {}
            except (FileNotFoundError, json.JSONDecodeError):
                return {}
    
    async def save_data(self, data: Dict) -> bool:
        """Save economy data with error handling."""
        async with self.lock:
            try:
                async with aiofiles.open(self.econ_file, "w") as f:
                    await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                return True
            except Exception as e:
                logging.error(f"Error saving economy data: {e}")
                return False
    
    async def load_cooldowns(self) -> Dict:
        """Load cooldown data."""
        try:
            async with aiofiles.open(self.cooldowns_file, "r") as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    async def save_cooldowns(self, cooldowns: Dict) -> bool:
        """Save cooldown data."""
        try:
            async with aiofiles.open(self.cooldowns_file, "w") as f:
                await f.write(json.dumps(cooldowns, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            logging.error(f"Error saving cooldowns: {e}")
            return False
    
    async def load_shop(self) -> Dict:
        """Load shop data."""
        try:
            async with aiofiles.open(self.shop_file, "r") as f:
                content = await f.read()
                return json.loads(content) if content else {"items": []}
        except (FileNotFoundError, json.JSONDecodeError):
            return {"items": []}
    
    async def save_shop(self, shop_data: Dict) -> bool:
        """Save shop data."""
        try:
            async with aiofiles.open(self.shop_file, "w") as f:
                await f.write(json.dumps(shop_data, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            logging.error(f"Error saving shop data: {e}")
            return False
    
    async def load_inventory(self) -> Dict:
        """Load inventory data."""
        try:
            async with aiofiles.open(self.inventory_file, "r") as f:
                content = await f.read()
                return json.loads(content) if content else {}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    async def save_inventory(self, inventory: Dict) -> bool:
        """Save inventory data."""
        try:
            async with aiofiles.open(self.inventory_file, "w") as f:
                await f.write(json.dumps(inventory, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            logging.error(f"Error saving inventory: {e}")
            return False

    # ---------------- Enhanced Cooldown System ----------------
    async def check_cooldown(self, user_id: int, command: str, cooldown_seconds: int) -> Optional[float]:
        """Check if user is on cooldown. Returns remaining time or None."""
        cooldowns = await self.load_cooldowns()
        user_cooldowns = cooldowns.get(str(user_id), {})
        
        if command in user_cooldowns:
            last_used = datetime.fromisoformat(user_cooldowns[command])
            now = datetime.now(timezone.utc)
            time_passed = (now - last_used).total_seconds()
            
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
    
    # ---------------- Enhanced Balance Management ----------------
    async def get_balance(self, user_id: int) -> Dict[str, int]:
        """Get user's balance data."""
        data = await self.load_data()
        uid = str(user_id)
        return data.get(uid, {"wallet": 0, "bank": 0, "bank_limit": 5000, "multipliers": {}})
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, 
                           bank_change: int = 0, bank_limit_change: int = 0) -> Dict[str, int]:
        """Safely update wallet, bank, and bank limit."""
        data = await self.load_data()
        uid = str(user_id)
        
        if uid not in data:
            data[uid] = {"wallet": 0, "bank": 0, "bank_limit": 5000, "multipliers": {}}
        
        # Update values
        data[uid]["wallet"] = max(0, data[uid].get("wallet", 0) + wallet_change)
        data[uid]["bank"] = max(0, data[uid].get("bank", 0) + bank_change)
        data[uid]["bank_limit"] = max(5000, data[uid].get("bank_limit", 5000) + bank_limit_change)
        
        # Ensure bank doesn't exceed bank limit
        if data[uid]["bank"] > data[uid]["bank_limit"]:
            data[uid]["bank"] = data[uid]["bank_limit"]
        
        await self.save_data(data)
        return data[uid]
    
    async def transfer_money(self, from_user: int, to_user: int, amount: int) -> bool:
        """Transfer money between users safely."""
        if amount <= 0:
            return False
        
        data = await self.load_data()
        from_uid = str(from_user)
        to_uid = str(to_user)
        
        # Check if sender has enough money
        if data.get(from_uid, {}).get("wallet", 0) < amount:
            return False
        
        # Perform transfer
        data.setdefault(from_uid, {"wallet": 0, "bank": 0, "bank_limit": 5000, "multipliers": {}})
        data.setdefault(to_uid, {"wallet": 0, "bank": 0, "bank_limit": 5000, "multipliers": {}})
        
        data[from_uid]["wallet"] -= amount
        data[to_uid]["wallet"] += amount
        
        return await self.save_data(data)
    
    # ---------------- Utility Functions ----------------
    def format_time(self, seconds: float) -> str:
        """Format seconds into readable time."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def format_money(self, amount: int) -> str:
        """Format money with commas and currency symbol."""
        return f"{amount:,}£"
    
    async def create_economy_embed(self, title: str, color: discord.Color = discord.Color.gold()) -> discord.Embed:
        """Create a standardized economy embed."""
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="Economy System")
        return embed

    # ---------------- Core Economy Commands ----------------
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        """Check your or someone else's balance with enhanced information."""
        member = member or ctx.author
        
        try:
            user_data = await self.get_balance(member.id)
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
            
            # Net worth rank (simplified)
            if member == ctx.author:
                embed.add_field(name="📊 Quick Actions", 
                              value="• Use `~~deposit <amount|all>` to deposit\n• Use `~~withdraw <amount|all>` to withdraw", 
                              inline=False)
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Balance check failed: {e}")
            embed = await self.create_economy_embed("⚠️ Error", discord.Color.red())
            embed.description = "An error occurred while checking the balance."
            await ctx.send(embed=embed)
    
    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str):
        """Deposit money from wallet to bank with enhanced feedback."""
        user_data = await self.get_balance(ctx.author.id)
        wallet = user_data["wallet"]
        bank = user_data["bank"]
        bank_limit = user_data["bank_limit"]
        
        # Handle amount input
        if amount.lower() == "all":
            deposit_amount = wallet
        elif amount.lower() == "max":
            deposit_amount = min(wallet, bank_limit - bank)
        else:
            try:
                deposit_amount = int(amount)
                if deposit_amount <= 0:
                    raise ValueError
            except ValueError:
                embed = await self.create_economy_embed("❌ Invalid Amount", discord.Color.red())
                embed.description = "Please provide a valid positive number, `all`, or `max`."
                return await ctx.send(embed=embed)
        
        # Validation checks
        if deposit_amount <= 0:
            embed = await self.create_economy_embed("❌ Invalid Amount", discord.Color.red())
            embed.description = "Deposit amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        if wallet < deposit_amount:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(wallet)} in your wallet."
            return await ctx.send(embed=embed)
        
        if bank + deposit_amount > bank_limit:
            embed = await self.create_economy_embed("❌ Bank Limit Exceeded", discord.Color.red())
            embed.description = f"Your bank can only hold {self.format_money(bank_limit)}. You have {self.format_money(bank)} already."
            return await ctx.send(embed=embed)
        
        try:
            result = await self.update_balance(ctx.author.id, wallet_change=-deposit_amount, bank_change=deposit_amount)
            
            embed = await self.create_economy_embed("🏦 Deposit Successful", discord.Color.green())
            embed.description = f"Deposited {self.format_money(deposit_amount)} to your bank."
            embed.add_field(name="💵 New Wallet", value=self.format_money(result["wallet"]), inline=True)
            embed.add_field(name="🏦 New Bank", value=f"{self.format_money(result['bank'])} / {self.format_money(result['bank_limit'])}", inline=True)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} deposited {deposit_amount}£")
            
        except Exception as e:
            logging.error(f"Deposit failed: {e}")
            embed = await self.create_economy_embed("⚠️ Error", discord.Color.red())
            embed.description = "An error occurred while processing your deposit."
            await ctx.send(embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Withdraw money from bank to wallet."""
        user_data = await self.get_balance(ctx.author.id)
        wallet = user_data["wallet"]
        bank = user_data["bank"]
        
        # Handle amount input
        if amount.lower() == "all":
            withdraw_amount = bank
        else:
            try:
                withdraw_amount = int(amount)
                if withdraw_amount <= 0:
                    raise ValueError
            except ValueError:
                embed = await self.create_economy_embed("❌ Invalid Amount", discord.Color.red())
                embed.description = "Please provide a valid positive number or `all`."
                return await ctx.send(embed=embed)
        
        # Validation checks
        if withdraw_amount <= 0:
            embed = await self.create_economy_embed("❌ Invalid Amount", discord.Color.red())
            embed.description = "Withdraw amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        if bank < withdraw_amount:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(bank)} in your bank."
            return await ctx.send(embed=embed)
        
        try:
            result = await self.update_balance(ctx.author.id, wallet_change=withdraw_amount, bank_change=-withdraw_amount)
            
            embed = await self.create_economy_embed("🏦 Withdrawal Successful", discord.Color.green())
            embed.description = f"Withdrew {self.format_money(withdraw_amount)} from your bank."
            embed.add_field(name="💵 New Wallet", value=self.format_money(result["wallet"]), inline=True)
            embed.add_field(name="🏦 New Bank", value=f"{self.format_money(result['bank'])} / {self.format_money(result['bank_limit'])}", inline=True)
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} withdrew {withdraw_amount}£")
            
        except Exception as e:
            logging.error(f"Withdraw failed: {e}")
            embed = await self.create_economy_embed("⚠️ Error", discord.Color.red())
            embed.description = "An error occurred while processing your withdrawal."
            await ctx.send(embed=embed)
    
    # ---------------- Enhanced Earning Commands ----------------
    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context):
        """Claim your daily reward with streak bonuses."""
        # Check cooldown (24 hours)
        remaining = await self.check_cooldown(ctx.author.id, "daily", 24 * 3600)
        
        if remaining:
            embed = await self.create_economy_embed("⏰ Daily Already Claimed", discord.Color.orange())
            embed.description = f"You can claim your daily reward again in **{self.format_time(remaining)}**"
            return await ctx.send(embed=embed)
        
        # Base reward with random bonus
        base_reward = random.randint(500, 1000)
        bonus = random.randint(0, 500)  # Random bonus
        total_reward = base_reward + bonus
        
        # Streak bonus (simplified - in real implementation, track streaks)
        streak_bonus = random.randint(0, 200) if random.random() < 0.3 else 0
        total_reward += streak_bonus
        
        try:
            result = await self.update_balance(ctx.author.id, wallet_change=total_reward)
            await self.set_cooldown(ctx.author.id, "daily")
            
            embed = await self.create_economy_embed("🎁 Daily Reward Claimed!", discord.Color.green())
            embed.description = f"You received {self.format_money(total_reward)}!"
            
            breakdown = f"• Base: {self.format_money(base_reward)}\n• Bonus: {self.format_money(bonus)}"
            if streak_bonus > 0:
                breakdown += f"\n• Streak: {self.format_money(streak_bonus)}"
            
            embed.add_field(name="💰 Breakdown", value=breakdown, inline=False)
            embed.add_field(name="💵 New Balance", value=self.format_money(result["wallet"]), inline=False)
            embed.set_footer(text="Come back in 24 hours for your next reward!")
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} claimed daily: {total_reward}£")
            
        except Exception as e:
            logging.error(f"Daily reward failed: {e}")
            embed = await self.create_economy_embed("⚠️ Error", discord.Color.red())
            embed.description = "An error occurred while claiming your daily reward."
            await ctx.send(embed=embed)
    
    @commands.command(name="work")
    async def work(self, ctx: commands.Context):
        """Work to earn money with different job types and bonuses."""
        # Check cooldown (1 hour)
        remaining = await self.check_cooldown(ctx.author.id, "work", 3600)
        
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
            "designed graphics": (80, 150),
            "tutored students": (70, 140),
            "streamed on Twitch": (90, 200),
            "invested in stocks": (150, 300),
            "sold artwork": (120, 180)
        }
        
        job, (min_earn, max_earn) = random.choice(list(jobs.items()))
        earnings = random.randint(min_earn, max_earn)
        
        # Critical work chance (10%)
        is_critical = random.random() < 0.1
        if is_critical:
            earnings *= 2
        
        try:
            result = await self.update_balance(ctx.author.id, wallet_change=earnings)
            await self.set_cooldown(ctx.author.id, "work")
            
            embed = await self.create_economy_embed("💼 Work Complete!", discord.Color.blue())
            
            if is_critical:
                embed.description = f"🎯 **CRITICAL WORK!** You {job} and earned {self.format_money(earnings)}!"
                embed.color = discord.Color.gold()
            else:
                embed.description = f"You {job} and earned {self.format_money(earnings)}!"
            
            embed.add_field(name="💵 New Balance", value=self.format_money(result["wallet"]), inline=False)
            embed.set_footer(text="You can work again in 1 hour!")
            
            await ctx.send(embed=embed)
            logging.info(f"{ctx.author} worked and earned {earnings}£")
            
        except Exception as e:
            logging.error(f"Work failed: {e}")
            embed = await self.create_economy_embed("⚠️ Error", discord.Color.red())
            embed.description = "An error occurred while working."
            await ctx.send(embed=embed)
    
    @commands.command(name="crime", aliases=["steal"])
    @commands.cooldown(1, 7200, commands.BucketType.user)  # 2 hour cooldown
    async def crime(self, ctx: commands.Context):
        """Commit a crime for high risk, high reward earnings."""
        success_chance = 0.6  # 60% success rate
        
        if random.random() < success_chance:
            # Successful crime
            earnings = random.randint(200, 800)
            crimes = [
                "hacked a rich person's bank account",
                "successfully pulled off a heist",
                "sold rare items on the black market",
                "won big at an illegal casino",
                "smuggled valuable goods"
            ]
            crime = random.choice(crimes)
            
            await self.update_balance(ctx.author.id, wallet_change=earnings)
            
            embed = await self.create_economy_embed("💰 Crime Successful!", discord.Color.green())
            embed.description = f"You {crime} and earned {self.format_money(earnings)}!"
            
        else:
            # Failed crime - lose money
            loss = random.randint(100, 400)
            user_data = await self.get_balance(ctx.author.id)
            actual_loss = min(loss, user_data["wallet"])
            
            failures = [
                "got caught shoplifting and had to pay a fine",
                "failed to hack the bank's security system",
                "were arrested and had to post bail",
                "lost your illegal goods to the police",
                "got scammed in a shady deal"
            ]
            failure = random.choice(failures)
            
            await self.update_balance(ctx.author.id, wallet_change=-actual_loss)
            
            embed = await self.create_economy_embed("🚓 Crime Failed!", discord.Color.red())
            embed.description = f"You {failure} and lost {self.format_money(actual_loss)}!"
        
        await ctx.send(embed=embed)
    
    # ---------------- Shop System ----------------
    @commands.command(name="shop", aliases=["store"])
    async def shop(self, ctx: commands.Context):
        """Browse the shop for upgrades and items."""
        shop_data = await self.load_shop()
        items = shop_data.get("items", [])
        
        if not items:
            embed = await self.create_economy_embed("🛍️ Shop")
            embed.description = "The shop is currently empty. Check back later!"
            return await ctx.send(embed=embed)
        
        embed = await self.create_economy_embed("🛍️ Economy Shop")
        embed.description = "Use `~~buy <item_id>` to purchase items!\n\n"
        
        for item in items:
            stock_info = "∞" if item.get("stock", -1) == -1 else f"{item['stock']} left"
            embed.add_field(
                name=f"{item['emoji']} {item['name']} - {self.format_money(item['price'])}",
                value=f"**ID:** `{item['id']}` | **Stock:** {stock_info}\n{item['description']}",
                inline=False
            )
        
        embed.add_field(
            name="💡 How to Buy",
            value="Use `~~buy <item_id>` to purchase an item.\nExample: `~~buy 1`",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="buy", aliases=["purchase"])
    async def buy(self, ctx: commands.Context, item_id: int):
        """Purchase an item from the shop."""
        shop_data = await self.load_shop()
        items = shop_data.get("items", [])
        
        item = next((i for i in items if i["id"] == item_id), None)
        if not item:
            embed = await self.create_economy_embed("❌ Item Not Found", discord.Color.red())
            embed.description = f"No item found with ID `{item_id}`. Use `~~shop` to see available items."
            return await ctx.send(embed=embed)
        
        # Check stock
        if item.get("stock", -1) == 0:
            embed = await self.create_economy_embed("❌ Out of Stock", discord.Color.red())
            embed.description = f"**{item['name']}** is out of stock! Check back later."
            return await ctx.send(embed=embed)
        
        # Check balance
        user_data = await self.get_balance(ctx.author.id)
        if user_data["wallet"] < item["price"]:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You need {self.format_money(item['price'])} but only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Process purchase
        await self.update_balance(ctx.author.id, wallet_change=-item["price"])
        
        # Add to inventory
        inventory = await self.load_inventory()
        user_inv = inventory.setdefault(str(ctx.author.id), [])
        
        # Create inventory item
        inv_item = {
            "id": item["id"],
            "name": item["name"],
            "type": item["type"],
            "purchased_at": datetime.now(timezone.utc).isoformat(),
            "effect": item["effect"],
            "emoji": item["emoji"]
        }
        
        # Handle different item types
        if item["type"] == "upgrade":
            # Apply upgrade immediately
            effect = item["effect"]
            if "bank_limit" in effect:
                await self.update_balance(ctx.author.id, bank_limit_change=effect["bank_limit"])
        
        elif item["type"] in ["consumable", "permanent"]:
            user_inv.append(inv_item)
            await self.save_inventory(inventory)
        
        # Update shop stock
        if item.get("stock", -1) > 0:
            item["stock"] -= 1
            await self.save_shop(shop_data)
        
        # Success message
        embed = await self.create_economy_embed("✅ Purchase Successful!", discord.Color.green())
        embed.description = f"You purchased **{item['emoji']} {item['name']}** for {self.format_money(item['price'])}!"
        
        if item["type"] == "upgrade":
            embed.add_field(
                name="⚡ Upgrade Applied",
                value=f"Your {list(item['effect'].keys())[0].replace('_', ' ').title()} has been upgraded!",
                inline=False
            )
        elif item["type"] in ["consumable", "permanent"]:
            embed.add_field(
                name="📦 Item Stored",
                value="Use `~~inventory` to view your items and `~~use <item>` to use consumables.",
                inline=False
            )
        
        await ctx.send(embed=embed)
        logging.info(f"{ctx.author} purchased {item['name']} for {item['price']}£")
    
    @commands.command(name="inventory", aliases=["inv", "items"])
    async def inventory(self, ctx: commands.Context, member: discord.Member = None):
        """View your inventory or another user's inventory."""
        member = member or ctx.author
        inventory = await self.load_inventory()
        user_inv = inventory.get(str(member.id), [])
        
        embed = await self.create_economy_embed(f"🎒 {member.display_name}'s Inventory")
        
        if not user_inv:
            embed.description = "No items in inventory. Visit the shop with `~~shop`!"
            return await ctx.send(embed=embed)
        
        # Group items by type
        consumables = [item for item in user_inv if item["type"] == "consumable"]
        permanent = [item for item in user_inv if item["type"] == "permanent"]
        
        if consumables:
            consumable_text = ""
            for item in consumables:
                consumable_text += f"{item['emoji']} **{item['name']}**\n"
            embed.add_field(name="🎁 Consumables", value=consumable_text, inline=False)
        
        if permanent:
            permanent_text = ""
            for item in permanent:
                permanent_text += f"{item['emoji']} **{item['name']}**\n"
            embed.add_field(name="💎 Permanent Items", value=permanent_text, inline=False)
        
        if member == ctx.author and consumables:
            embed.add_field(
                name="🔧 Usage",
                value="Use `~~use <item_name>` to use consumable items.",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="use")
    async def use_item(self, ctx: commands.Context, *, item_name: str):
        """Use a consumable item from your inventory."""
        inventory = await self.load_inventory()
        user_inv = inventory.get(str(ctx.author.id), [])
        
        # Find item (case insensitive partial match)
        item = None
        for inv_item in user_inv:
            if inv_item["type"] == "consumable" and item_name.lower() in inv_item["name"].lower():
                item = inv_item
                break
        
        if not item:
            embed = await self.create_economy_embed("❌ Item Not Found", discord.Color.red())
            embed.description = f"No consumable item named `{item_name}` found in your inventory."
            return await ctx.send(embed=embed)
        
        # Apply item effects
        effect = item["effect"]
        user_data = await self.get_balance(ctx.author.id)
        multipliers = user_data.setdefault("multipliers", {})
        
        result_text = ""
        
        if "daily_bonus" in effect:
            multipliers["daily"] = {
                "multiplier": effect["daily_bonus"],
                "expires": (datetime.now(timezone.utc) + timedelta(days=effect["duration"])).isoformat()
            }
            result_text = f"Daily rewards are now increased by 20% for {effect['duration']} days! ✨"
        
        elif "work_bonus" in effect:
            multipliers["work"] = {
                "multiplier": effect["work_bonus"],
                "expires": (datetime.now(timezone.utc) + timedelta(days=effect["duration"])).isoformat()
            }
            result_text = f"Work earnings are now increased by 30% for {effect['duration']} days! 💼"
        
        elif "gamble_bonus" in effect:
            multipliers["gamble"] = {
                "multiplier": effect["gamble_bonus"],
                "uses": effect["uses"]
            }
            result_text = f"Gambling odds improved for {effect['uses']} uses! 🎲"
        
        elif "mystery_box" in effect:
            reward = random.randint(500, 5000)
            await self.update_balance(ctx.author.id, wallet_change=reward)
            result_text = f"You opened the mystery box and found {self.format_money(reward)}! 🎉"
        
        elif "crime_insurance" in effect:
            multipliers["crime_insurance"] = effect["crime_insurance"]
            result_text = f"You're now insured against crime losses for {effect['crime_insurance']} crimes! 🛡️"
        
        # Remove item from inventory
        user_inv.remove(item)
        inventory[str(ctx.author.id)] = user_inv
        await self.save_inventory(inventory)
        await self.save_data(await self.load_data())  # Save multipliers
        
        embed = await self.create_economy_embed(f"✅ {item['emoji']} {item['name']} Used!", discord.Color.green())
        embed.description = result_text
        await ctx.send(embed=embed)

    # ---------------- Enhanced Mini-Games ----------------
    @commands.command(name="flip", aliases=["coinflip", "coin"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def coin_flip(self, ctx: commands.Context, choice: str, bet: int):
        """Flip a coin! Choose heads or tails and bet some money.
        
        Example: ~~flip heads 500
        """
        choice = choice.lower()
        if choice not in ["heads", "tails", "h", "t"]:
            embed = await self.create_economy_embed("❌ Invalid Choice", discord.Color.red())
            embed.description = "Please choose either `heads` or `tails`."
            return await ctx.send(embed=embed)
        
        if bet <= 0:
            embed = await self.create_economy_embed("❌ Invalid Bet", discord.Color.red())
            embed.description = "Bet amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        user_data = await self.get_balance(ctx.author.id)
        if user_data["wallet"] < bet:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Convert short choices
        if choice in ["h", "heads"]:
            choice = "heads"
        else:
            choice = "tails"
        
        # Flip the coin
        result = random.choice(["heads", "tails"])
        won = result == choice
        
        # Animated coin flip
        embed = await self.create_economy_embed("🪙 Coin Flip")
        embed.description = "Flipping the coin..."
        msg = await ctx.send(embed=embed)
        
        # Animation frames
        frames = ["🔄", "⚪", "🟡", "💰"]
        for frame in frames:
            embed.description = f"{frame} The coin is spinning..."
            await msg.edit(embed=embed)
            await asyncio.sleep(0.5)
        
        # Result
        if won:
            winnings = int(bet * 1.8)  # 80% profit
            await self.update_balance(ctx.author.id, wallet_change=winnings)
            
            embed = await self.create_economy_embed("🎉 You Won!", discord.Color.green())
            embed.description = f"The coin landed on **{result}**! You won {self.format_money(winnings)}!"
            embed.add_field(name="💰 Profit", value=f"+{self.format_money(winnings - bet)}", inline=True)
            
        else:
            await self.update_balance(ctx.author.id, wallet_change=-bet)
            
            embed = await self.create_economy_embed("💸 You Lost", discord.Color.red())
            embed.description = f"The coin landed on **{result}**. You lost {self.format_money(bet)}."
            embed.add_field(name="📉 Loss", value=f"-{self.format_money(bet)}", inline=True)
        
        embed.add_field(name="🎯 Your Choice", value=choice.title(), inline=True)
        embed.add_field(name="🪙 Result", value=result.title(), inline=True)
        
        await msg.edit(embed=embed)
    
    @commands.command(name="dice", aliases=["rolldice"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def dice_game(self, ctx: commands.Context, bet: int):
        """Roll two dice! Win if you roll 7 or 11, lose on 2, 3, or 12.
        
        Example: ~~dice 500
        """
        if bet <= 0:
            embed = await self.create_economy_embed("❌ Invalid Bet", discord.Color.red())
            embed.description = "Bet amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        user_data = await self.get_balance(ctx.author.id)
        if user_data["wallet"] < bet:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Roll animation
        embed = await self.create_economy_embed("🎲 Dice Game")
        embed.description = "Rolling the dice..."
        msg = await ctx.send(embed=embed)
        
        dice_faces = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        for _ in range(3):
            dice1 = random.choice(dice_faces)
            dice2 = random.choice(dice_faces)
            embed.description = f"Rolling... {dice1} {dice2}"
            await msg.edit(embed=embed)
            await asyncio.sleep(0.3)
        
        # Final roll
        roll1 = random.randint(1, 6)
        roll2 = random.randint(1, 6)
        total = roll1 + roll2
        
        dice1_face = dice_faces[roll1 - 1]
        dice2_face = dice_faces[roll2 - 1]
        
        # Determine result
        if total in [7, 11]:
            # Win
            winnings = int(bet * 2)  # Double your money
            await self.update_balance(ctx.author.id, wallet_change=winnings)
            
            embed = await self.create_economy_embed("🎉 You Won!", discord.Color.green())
            embed.description = f"You rolled **{total}**! {dice1_face} {dice2_face}"
            embed.add_field(name="💰 Winnings", value=f"+{self.format_money(winnings)}", inline=True)
            embed.add_field(name="📈 Profit", value=f"+{self.format_money(winnings - bet)}", inline=True)
            
        elif total in [2, 3, 12]:
            # Lose
            await self.update_balance(ctx.author.id, wallet_change=-bet)
            
            embed = await self.create_economy_embed("💸 You Lost", discord.Color.red())
            embed.description = f"You rolled **{total}**! {dice1_face} {dice2_face}"
            embed.add_field(name="📉 Loss", value=f"-{self.format_money(bet)}", inline=True)
            
        else:
            # Push (return bet)
            embed = await self.create_economy_embed("🤝 Push", discord.Color.blue())
            embed.description = f"You rolled **{total}**. It's a tie! Your bet has been returned."
            embed.add_field(name="💵 Result", value="Bet returned", inline=True)
        
        embed.add_field(name="🎲 Roll", value=f"{roll1} + {roll2} = {total}", inline=True)
        
        await msg.edit(embed=embed)
    
    @commands.command(name="rps", aliases=["rockpaperscissors"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def rock_paper_scissors(self, ctx: commands.Context, choice: str, bet: int):
        """Play Rock Paper Scissors against the bot!
        
        Example: ~~rps rock 500
        """
        choice = choice.lower()
        valid_choices = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
        
        if choice not in valid_choices:
            embed = await self.create_economy_embed("❌ Invalid Choice", discord.Color.red())
            embed.description = "Please choose `rock`, `paper`, or `scissors`."
            return await ctx.send(embed=embed)
        
        if bet <= 0:
            embed = await self.create_economy_embed("❌ Invalid Bet", discord.Color.red())
            embed.description = "Bet amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        user_data = await self.get_balance(ctx.author.id)
        if user_data["wallet"] < bet:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Bot's choice
        bot_choice = random.choice(list(valid_choices.keys()))
        
        # Animation
        embed = await self.create_economy_embed("🎮 Rock Paper Scissors")
        embed.description = f"You chose {valid_choices[choice]} {choice.title()}\nBot is choosing..."
        msg = await ctx.send(embed=embed)
        
        await asyncio.sleep(1)
        
        # Determine winner
        if choice == bot_choice:
            # Tie
            embed = await self.create_economy_embed("🤝 It's a Tie!", discord.Color.blue())
            embed.description = f"**{valid_choices[choice]} {choice.title()}** vs **{valid_choices[bot_choice]} {bot_choice.title()}**"
            embed.add_field(name="💰 Result", value="Bet returned", inline=True)
            
        elif ((choice == "rock" and bot_choice == "scissors") or
              (choice == "paper" and bot_choice == "rock") or
              (choice == "scissors" and bot_choice == "paper")):
            # Win
            winnings = int(bet * 1.5)
            await self.update_balance(ctx.author.id, wallet_change=winnings)
            
            embed = await self.create_economy_embed("🎉 You Win!", discord.Color.green())
            embed.description = f"**{valid_choices[choice]} {choice.title()}** beats **{valid_choices[bot_choice]} {bot_choice.title()}**"
            embed.add_field(name="💰 Winnings", value=f"+{self.format_money(winnings)}", inline=True)
            embed.add_field(name="📈 Profit", value=f"+{self.format_money(winnings - bet)}", inline=True)
            
        else:
            # Lose
            await self.update_balance(ctx.author.id, wallet_change=-bet)
            
            embed = await self.create_economy_embed("💸 You Lose", discord.Color.red())
            embed.description = f"**{valid_choices[bot_choice]} {bot_choice.title()}** beats **{valid_choices[choice]} {choice.title()}**"
            embed.add_field(name="📉 Loss", value=f"-{self.format_money(bet)}", inline=True)
        
        await msg.edit(embed=embed)
    
    @commands.command(name="guess", aliases=["numberguess"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def number_guess(self, ctx: commands.Context, bet: int):
        """Guess a number between 1-10! 3x payout for correct guess.
        
        Example: ~~guess 500
        """
        if bet <= 0:
            embed = await self.create_economy_embed("❌ Invalid Bet", discord.Color.red())
            embed.description = "Bet amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        user_data = await self.get_balance(ctx.author.id)
        if user_data["wallet"] < bet:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        embed = await self.create_economy_embed("🔢 Number Guessing Game")
        embed.description = f"I'm thinking of a number between 1 and 10...\nYou have 10 seconds to guess!\n\n**Prize:** {self.format_money(bet * 3)} (3x your bet)"
        
        await ctx.send(embed=embed)
        
        # Generate secret number
        secret_number = random.randint(1, 10)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel and m.content.isdigit()
        
        try:
            msg = await self.bot.wait_for("message", timeout=10.0, check=check)
            guess = int(msg.content)
            
            if guess == secret_number:
                winnings = bet * 3
                await self.update_balance(ctx.author.id, wallet_change=winnings)
                
                embed = await self.create_economy_embed("🎉 Correct Guess!", discord.Color.green())
                embed.description = f"You guessed **{guess}** and the number was **{secret_number}**!"
                embed.add_field(name="💰 Winnings", value=f"+{self.format_money(winnings)}", inline=True)
                embed.add_field(name="📈 Profit", value=f"+{self.format_money(winnings - bet)}", inline=True)
                
            else:
                await self.update_balance(ctx.author.id, wallet_change=-bet)
                
                embed = await self.create_economy_embed("💸 Wrong Guess", discord.Color.red())
                embed.description = f"You guessed **{guess}** but the number was **{secret_number}**."
                embed.add_field(name="📉 Loss", value=f"-{self.format_money(bet)}", inline=True)
            
            await ctx.send(embed=embed)
            
        except asyncio.TimeoutError:
            await self.update_balance(ctx.author.id, wallet_change=-bet)
            
            embed = await self.create_economy_embed("⏰ Time's Up!", discord.Color.red())
            embed.description = f"You took too long! The number was **{secret_number}**."
            embed.add_field(name="📉 Loss", value=f"-{self.format_money(bet)}", inline=True)
            await ctx.send(embed=embed)
    
    @commands.command(name="blackjack", aliases=["bj", "21"])
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def blackjack(self, ctx: commands.Context, bet: int):
        """Play a simple game of Blackjack against the bot!
        
        Example: ~~blackjack 500
        """
        if bet <= 0:
            embed = await self.create_economy_embed("❌ Invalid Bet", discord.Color.red())
            embed.description = "Bet amount must be greater than 0."
            return await ctx.send(embed=embed)
        
        user_data = await self.get_balance(ctx.author.id)
        if user_data["wallet"] < bet:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Card values
        cards = {
            "A": 11, "2": 2, "3": 3, "4": 4, "5": 5, 
            "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, 
            "J": 10, "Q": 10, "K": 10
        }
        card_emojis = {
            "A": "🅰️", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣", "5": "5️⃣",
            "6": "6️⃣", "7": "7️⃣", "8": "8️⃣", "9": "9️⃣", "10": "🔟",
            "J": "🇯", "Q": "🇶", "K": "🇰"
        }
        
        # Initial deal
        user_hand = [random.choice(list(cards.keys())) for _ in range(2)]
        bot_hand = [random.choice(list(cards.keys())) for _ in range(2)]
        
        user_score = sum(cards[card] for card in user_hand)
        bot_score = sum(cards[card] for card in bot_hand)
        
        # Handle aces
        if user_score > 21 and "A" in user_hand:
            user_score -= 10
        
        # Game loop
        game_over = False
        
        while not game_over and user_score < 21:
            # Show current state
            user_cards = " ".join(card_emojis.get(card, card) for card in user_hand)
            bot_cards = f"{card_emojis.get(bot_hand[0], bot_hand[0])} ❓"
            
            embed = await self.create_economy_embed("🎮 Blackjack")
            embed.add_field(name="Your Hand", value=f"{user_cards}\nScore: {user_score}", inline=False)
            embed.add_field(name="Bot's Hand", value=f"{bot_cards}\nScore: ?", inline=False)
            embed.add_field(name="💡 Options", value="Type `hit` to draw another card or `stand` to stay.", inline=False)
            
            await ctx.send(embed=embed)
            
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["hit", "stand", "h", "s"]
            
            try:
                msg = await self.bot.wait_for("message", timeout=30.0, check=check)
                action = msg.content.lower()
                
                if action in ["hit", "h"]:
                    new_card = random.choice(list(cards.keys()))
                    user_hand.append(new_card)
                    user_score += cards[new_card]
                    
                    # Handle aces
                    if user_score > 21 and "A" in user_hand:
                        user_score -= 10
                    
                    if user_score > 21:
                        game_over = True
                
                else:  # stand
                    game_over = True
                    
            except asyncio.TimeoutError:
                embed = await self.create_economy_embed("⏰ Time's Up!", discord.Color.red())
                embed.description = "You took too long! Your turn has ended."
                await ctx.send(embed=embed)
                game_over = True
        
        # Bot's turn
        while bot_score < 17 and user_score <= 21:
            new_card = random.choice(list(cards.keys()))
            bot_hand.append(new_card)
            bot_score += cards[new_card]
            
            # Handle aces
            if bot_score > 21 and "A" in bot_hand:
                bot_score -= 10
        
        # Determine winner
        user_cards_final = " ".join(card_emojis.get(card, card) for card in user_hand)
        bot_cards_final = " ".join(card_emojis.get(card, card) for card in bot_hand)
        
        if user_score > 21:
            # Player busts
            await self.update_balance(ctx.author.id, wallet_change=-bet)
            
            embed = await self.create_economy_embed("💸 Bust! You Lose", discord.Color.red())
            embed.description = f"You went over 21!"
            
        elif bot_score > 21:
            # Bot busts
            winnings = int(bet * 2)
            await self.update_balance(ctx.author.id, wallet_change=winnings)
            
            embed = await self.create_economy_embed("🎉 Dealer Busts! You Win!", discord.Color.green())
            embed.description = f"The dealer went over 21!"
            embed.add_field(name="💰 Winnings", value=f"+{self.format_money(winnings)}", inline=True)
            
        elif user_score > bot_score:
            # Player wins
            winnings = int(bet * 2)
            await self.update_balance(ctx.author.id, wallet_change=winnings)
            
            embed = await self.create_economy_embed("🎉 You Win!", discord.Color.green())
            embed.description = f"Your score ({user_score}) beats the dealer ({bot_score})!"
            embed.add_field(name="💰 Winnings", value=f"+{self.format_money(winnings)}", inline=True)
            
        elif user_score < bot_score:
            # Bot wins
            await self.update_balance(ctx.author.id, wallet_change=-bet)
            
            embed = await self.create_economy_embed("💸 Dealer Wins", discord.Color.red())
            embed.description = f"Dealer's score ({bot_score}) beats your score ({user_score})!"
            embed.add_field(name="📉 Loss", value=f"-{self.format_money(bet)}", inline=True)
            
        else:
            # Tie
            embed = await self.create_economy_embed("🤝 Push", discord.Color.blue())
            embed.description = f"It's a tie! Both have {user_score}. Your bet is returned."
        
        embed.add_field(name="Your Hand", value=f"{user_cards_final}\nScore: {user_score}", inline=True)
        embed.add_field(name="Dealer's Hand", value=f"{bot_cards_final}\nScore: {bot_score}", inline=True)
        
        await ctx.send(embed=embed)
    
    # ---------------- Social Commands ----------------
    @commands.command(name="pay", aliases=["give", "transfer"])
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Pay another user money with enhanced features."""
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
        user_data = await self.get_balance(ctx.author.id)
        if user_data["wallet"] < amount:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        try:
            success = await self.transfer_money(ctx.author.id, member.id, amount)
            
            if success:
                embed = await self.create_economy_embed("💸 Payment Successful", discord.Color.green())
                embed.description = f"{ctx.author.mention} paid {self.format_money(amount)} to {member.mention}"
                embed.set_footer(text=f"Transaction completed at {datetime.now().strftime('%H:%M:%S')}")
                
                logging.info(f"{ctx.author} paid {amount}£ to {member}")
            else:
                embed = await self.create_economy_embed("⚠️ Transfer Failed", discord.Color.red())
                embed.description = "The payment could not be processed."
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Payment failed: {e}")
            embed = await self.create_economy_embed("⚠️ Error", discord.Color.red())
            embed.description = "An error occurred while processing the payment."
            await ctx.send(embed=embed)
    
    # ---------------- Leaderboard ----------------
    @commands.command(name="leaderboard", aliases=["lb", "top", "rich"])
    async def leaderboard(self, ctx: commands.Context):
        """Show the wealth leaderboard with enhanced formatting."""
        try:
            data = await self.load_data()
            
            # Calculate total wealth for each user
            user_totals = []
            for uid, user_data in data.items():
                wallet = user_data.get("wallet", 0)
                bank = user_data.get("bank", 0)
                total = wallet + bank
                
                if total > 0:
                    user_totals.append((int(uid), total, user_data))
            
            # Sort by total wealth
            user_totals.sort(key=lambda x: x[1], reverse=True)
            
            if not user_totals:
                embed = await self.create_economy_embed("📊 Leaderboard")
                embed.description = "No users have any money yet! Be the first to earn some!"
                return await ctx.send(embed=embed)
            
            # Build leaderboard
            embed = await self.create_economy_embed("📊 Wealth Leaderboard")
            embed.description = "Top 10 richest users on the server"
            
            medals = ["🥇", "🥈", "🥉"]
            emojis = ["💎", "💰", "🏦", "💵", "💴", "💶", "💷", "🪙", "💳", "📈"]
            
            leaderboard_text = ""
            for i, (uid, total, user_data) in enumerate(user_totals[:10]):
                user = self.bot.get_user(uid)
                username = user.display_name if user else f"User {uid}"
                
                medal = medals[i] if i < 3 else emojis[i]
                wallet = user_data.get("wallet", 0)
                bank = user_data.get("bank", 0)
                
                leaderboard_text += (
                    f"{medal} **{username}**\n"
                    f"　• Total: {self.format_money(total)}\n"
                    f"　• Wallet: {self.format_money(wallet)} | Bank: {self.format_money(bank)}\n\n"
                )
            
            embed.add_field(name="🏆 Top Wealth", value=leaderboard_text, inline=False)
            
            # Show user's position if they're not in top 10
            author_position = None
            for i, (uid, total, _) in enumerate(user_totals):
                if uid == ctx.author.id:
                    author_position = i + 1
                    break
            
            if author_position and author_position > 10:
                embed.add_field(
                    name="📈 Your Position", 
                    value=f"You are ranked **#{author_position}** out of {len(user_totals)} users", 
                    inline=False
                )
            
            embed.set_footer(text=f"Total tracked users: {len(user_totals)}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Leaderboard failed: {e}")
            embed = await self.create_economy_embed("⚠️ Error", discord.Color.red())
            embed.description = "An error occurred while loading the leaderboard."
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
