import discord
from discord.ext import commands
import json
import aiofiles
import asyncio
import os
import glob
import random
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple

class JSONDatabase:
    """JSON-based database with backup system for economy data."""
    
    def __init__(self):
        self.data_dir = "data"
        self.primary_file = f"{self.data_dir}/economy_data.json"
        self.backup_files = [
            f"{self.data_dir}/backup_economy_1.json",
            f"{self.data_dir}/backup_economy_2.json", 
            f"{self.data_dir}/backup_economy_3.json"
        ]
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Ensure data directory exists."""
        os.makedirs(self.data_dir, exist_ok=True)
    
    async def load_data(self):
        """Load data from primary file or backups."""
        # Try primary file first
        if os.path.exists(self.primary_file):
            try:
                async with aiofiles.open(self.primary_file, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    logging.info("✅ Loaded data from primary file")
                    return data
            except Exception as e:
                logging.warning(f"Primary file corrupted: {e}")
        
        # Try backups in order
        for backup_file in self.backup_files:
            if os.path.exists(backup_file):
                try:
                    async with aiofiles.open(backup_file, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                        logging.info(f"✅ Loaded data from backup: {backup_file}")
                        # Restore to primary file
                        await self._save_to_file(self.primary_file, data)
                        return data
                except Exception as e:
                    logging.warning(f"Backup file corrupted {backup_file}: {e}")
                    continue
        
        # Return empty data structure if all fails
        logging.info("🆕 Creating new empty database")
        return self._get_empty_data()
    
    def _get_empty_data(self):
        """Return empty data structure."""
        return {
            "users": {},
            "inventory": {},
            "shop": {
                "items": [
                    {
                        "id": 1,
                        "name": "💰 Small Bank Upgrade",
                        "description": "Increase your bank limit by 5,000£",
                        "price": 2000,
                        "type": "upgrade",
                        "effect": {"bank_limit": 5000},
                        "emoji": "💰",
                        "stock": -1
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
                    }
                ]
            },
            "cooldowns": {},
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "last_save": None,
                "total_users": 0,
                "total_money": 0
            }
        }
    
    async def save_data(self, data):
        """Save data with multiple backups."""
        data['metadata']['last_save'] = datetime.now().isoformat()
        data['metadata']['total_users'] = len(data['users'])
        data['metadata']['total_money'] = sum(
            user_data.get('wallet', 0) + user_data.get('bank', 0) 
            for user_data in data['users'].values()
        )
        
        try:
            # Save to primary file
            await self._save_to_file(self.primary_file, data)
            
            # Rotate backups
            await self._rotate_backups(data)
            
            logging.info("💾 Data saved successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ Save failed: {e}")
            return False
    
    async def _save_to_file(self, filepath, data):
        """Save data to a specific file."""
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, indent=2, ensure_ascii=False))
    
    async def _rotate_backups(self, data):
        """Rotate backup files (keep last 3)."""
        # Remove oldest backup if it exists
        if os.path.exists(self.backup_files[2]):
            os.remove(self.backup_files[2])
        
        # Shift backups
        for i in range(len(self.backup_files)-2, -1, -1):
            if os.path.exists(self.backup_files[i]):
                os.rename(self.backup_files[i], self.backup_files[i+1])
        
        # Create new backup
        await self._save_to_file(self.backup_files[0], data)
    
    async def start_auto_save(self, economy_cog):
        """Start auto-saving every 10 minutes."""
        while True:
            await asyncio.sleep(600)  # 10 minutes
            try:
                # Get current data from economy cog
                if hasattr(economy_cog, 'data'):
                    await self.save_data(economy_cog.data)
                    logging.info("🔄 Auto-save completed")
            except Exception as e:
                logging.error(f"Auto-save failed: {e}")
    
    def get_stats(self, data):
        """Get database statistics."""
        return {
            'total_users': len(data['users']),
            'total_money': sum(
                user_data.get('wallet', 0) + user_data.get('bank', 0) 
                for user_data in data['users'].values()
            ),
            'last_save': data['metadata'].get('last_save'),
            'created_at': data['metadata'].get('created_at')
        }

# Global database instance
db = JSONDatabase()

class Economy(commands.Cog):
    """Enhanced economy system with JSON database."""
    
    def __init__(self, bot):
        self.bot = bot
        self.data = None
        self.lock = asyncio.Lock()
        self._ensure_directories()
        
    def _ensure_directories(self):
        """Ensure necessary directories exist."""
        os.makedirs("data", exist_ok=True)
    
    async def cog_load(self):
        """Load data when cog is loaded."""
        await self.load_data()
        # Start auto-save task
        asyncio.create_task(db.start_auto_save(self))
        logging.info("✅ Economy system loaded with JSON database")
    
    async def load_data(self):
        """Load economy data."""
        async with self.lock:
            self.data = await db.load_data()
    
    async def save_data(self):
        """Save economy data."""
        async with self.lock:
            await db.save_data(self.data)
    
    # User management methods
    def get_user(self, user_id: int) -> Dict:
        """Get user data or create if doesn't exist."""
        user_id_str = str(user_id)
        if user_id_str not in self.data['users']:
            self.data['users'][user_id_str] = {
                "wallet": 100,
                "bank": 0,
                "bank_limit": 5000,
                "networth": 100,
                "daily_streak": 0,
                "last_daily": None,
                "total_earned": 0,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat()
            }
        return self.data['users'][user_id_str]
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        """Update user's wallet and bank balance."""
        user = self.get_user(user_id)
        
        user['wallet'] = max(0, user['wallet'] + wallet_change)
        user['bank'] = max(0, user['bank'] + bank_change)
        
        # Ensure bank doesn't exceed limit
        if user['bank'] > user['bank_limit']:
            user['bank'] = user['bank_limit']
        
        user['networth'] = user['wallet'] + user['bank']
        user['last_active'] = datetime.now().isoformat()
        
        if wallet_change > 0 or bank_change > 0:
            user['total_earned'] += (wallet_change + bank_change)
        
        # Auto-save for significant changes
        if abs(wallet_change) > 500 or abs(bank_change) > 500:
            asyncio.create_task(self.save_data())
        
        return user
    
    async def transfer_money(self, from_user: int, to_user: int, amount: int) -> bool:
        """Transfer money between users."""
        from_user_data = self.get_user(from_user)
        to_user_data = self.get_user(to_user)
        
        if from_user_data['wallet'] < amount:
            return False
        
        from_user_data['wallet'] -= amount
        to_user_data['wallet'] += amount
        
        # Update networth
        from_user_data['networth'] = from_user_data['wallet'] + from_user_data['bank']
        to_user_data['networth'] = to_user_data['wallet'] + to_user_data['bank']
        
        asyncio.create_task(self.save_data())
        return True
    
    # Cooldown management
    async def check_cooldown(self, user_id: int, command: str, cooldown_seconds: int) -> Optional[float]:
        """Check if user is on cooldown."""
        cooldown_key = f"{user_id}_{command}"
        last_used = self.data['cooldowns'].get(cooldown_key)
        
        if last_used:
            last_used_time = datetime.fromisoformat(last_used)
            time_passed = (datetime.now() - last_used_time).total_seconds()
            
            if time_passed < cooldown_seconds:
                return cooldown_seconds - time_passed
        
        return None
    
    async def set_cooldown(self, user_id: int, command: str):
        """Set cooldown for a command."""
        cooldown_key = f"{user_id}_{command}"
        self.data['cooldowns'][cooldown_key] = datetime.now().isoformat()
    
    # Inventory management
    async def add_to_inventory(self, user_id: int, item: Dict):
        """Add item to user's inventory."""
        user_id_str = str(user_id)
        if user_id_str not in self.data['inventory']:
            self.data['inventory'][user_id_str] = []
        
        self.data['inventory'][user_id_str].append({
            **item,
            "purchased_at": datetime.now().isoformat()
        })
        
        asyncio.create_task(self.save_data())
    
    async def get_inventory(self, user_id: int) -> List:
        """Get user's inventory."""
        user_id_str = str(user_id)
        return self.data['inventory'].get(user_id_str, [])
    
    async def use_item(self, user_id: int, item_index: int) -> bool:
        """Use item from inventory."""
        user_id_str = str(user_id)
        if user_id_str in self.data['inventory'] and item_index < len(self.data['inventory'][user_id_str]):
            self.data['inventory'][user_id_str].pop(item_index)
            asyncio.create_task(self.save_data())
            return True
        return False
    
    # Shop methods
    def get_shop_items(self) -> List:
        """Get all shop items."""
        return self.data['shop']['items']
    
    def get_shop_item(self, item_id: int) -> Optional[Dict]:
        """Get specific shop item."""
        for item in self.data['shop']['items']:
            if item['id'] == item_id:
                return item
        return None
    
    # Utility methods
    def format_money(self, amount: int) -> str:
        """Format money with commas and currency symbol."""
        return f"{amount:,}£"
    
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
    
    async def create_economy_embed(self, title: str, color: discord.Color = discord.Color.gold()) -> discord.Embed:
        """Create a standardized economy embed."""
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text="Economy System | JSON Database")
        return embed

    # ========== COMMANDS ==========
    
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        """Check your or someone else's balance."""
        member = member or ctx.author
        user_data = self.get_user(member.id)
        
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
    
    @commands.command(name="wallet", aliases=["wal"])
    async def wallet(self, ctx: commands.Context, member: discord.Member = None):
        """View your wallet balance."""
        member = member or ctx.author
        user_data = self.get_user(member.id)
        
        embed = await self.create_economy_embed(f"💵 {member.display_name}'s Wallet")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💰 Wallet Balance", value=f"**{self.format_money(user_data['wallet'])}**", inline=False)
        
        if member == ctx.author:
            embed.add_field(name="💡 Quick Actions", 
                          value="• Use `~~deposit <amount>` to move money to bank\n• Use `~~withdraw <amount>` to get money from bank", 
                          inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="bank")
    async def bank(self, ctx: commands.Context, member: discord.Member = None):
        """View your bank balance."""
        member = member or ctx.author
        user_data = self.get_user(member.id)
        
        bank = user_data["bank"]
        bank_limit = user_data["bank_limit"]
        bank_usage = (bank / bank_limit) * 100 if bank_limit > 0 else 0
        
        embed = await self.create_economy_embed(f"🏦 {member.display_name}'s Bank")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="🏦 Bank Balance", value=f"**{self.format_money(bank)} / {self.format_money(bank_limit)}**", inline=False)
        
        # Bank usage bar
        bars = 10
        filled_bars = min(bars, int(bank_usage / 10))
        bar = "█" * filled_bars + "░" * (bars - filled_bars)
        embed.add_field(name="📊 Bank Usage", value=f"`{bar}` {bank_usage:.1f}%", inline=False)
        
        if member == ctx.author:
            embed.add_field(name="💡 Quick Actions", 
                          value="• Use `~~deposit <amount|all>` to add money\n• Use `~~withdraw <amount|all>` to take money\n• Use `~~shop` to buy bank upgrades", 
                          inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="networth", aliases=["nw", "worth"])
    async def networth(self, ctx: commands.Context, member: discord.Member = None):
        """View your total net worth."""
        member = member or ctx.author
        user_data = self.get_user(member.id)
        
        wallet = user_data["wallet"]
        bank = user_data["bank"]
        total = wallet + bank
        
        embed = await self.create_economy_embed(f"💎 {member.display_name}'s Net Worth")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💵 Wallet", value=self.format_money(wallet), inline=True)
        embed.add_field(name="🏦 Bank", value=self.format_money(bank), inline=True)
        embed.add_field(name="💎 Total Net Worth", value=f"**{self.format_money(total)}**", inline=True)
        
        # Wealth tier
        if total >= 1000000:
            tier = "💰 Billionaire"
            color = discord.Color.gold()
        elif total >= 100000:
            tier = "💎 Millionaire" 
            color = discord.Color.purple()
        elif total >= 50000:
            tier = "🏦 Rich"
            color = discord.Color.blue()
        elif total >= 10000:
            tier = "💵 Well-off"
            color = discord.Color.green()
        elif total >= 1000:
            tier = "🪙 Stable"
            color = discord.Color.green()
        else:
            tier = "🌱 Starting"
            color = discord.Color.light_grey()
        
        embed.add_field(name="🏆 Wealth Tier", value=tier, inline=False)
        embed.color = color
        
        if member == ctx.author:
            embed.add_field(name="📈 Growth Tips", 
                          value="• Use `~~work` every hour\n• Claim `~~daily` rewards\n• Play games in `~~shop`\n• Buy upgrades from `~~shop`", 
                          inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str):
        """Deposit money from wallet to bank."""
        user_data = self.get_user(ctx.author.id)
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
        
        # Process deposit
        result = await self.update_balance(ctx.author.id, wallet_change=-deposit_amount, bank_change=deposit_amount)
        
        embed = await self.create_economy_embed("🏦 Deposit Successful", discord.Color.green())
        embed.description = f"Deposited {self.format_money(deposit_amount)} to your bank."
        embed.add_field(name="💵 New Wallet", value=self.format_money(result["wallet"]), inline=True)
        embed.add_field(name="🏦 New Bank", value=f"{self.format_money(result['bank'])} / {self.format_money(result['bank_limit'])}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Withdraw money from bank to wallet."""
        user_data = self.get_user(ctx.author.id)
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
        
        # Process withdrawal
        result = await self.update_balance(ctx.author.id, wallet_change=withdraw_amount, bank_change=-withdraw_amount)
        
        embed = await self.create_economy_embed("🏦 Withdrawal Successful", discord.Color.green())
        embed.description = f"Withdrew {self.format_money(withdraw_amount)} from your bank."
        embed.add_field(name="💵 New Wallet", value=self.format_money(result["wallet"]), inline=True)
        embed.add_field(name="🏦 New Bank", value=f"{self.format_money(result['bank'])} / {self.format_money(result['bank_limit'])}", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context):
        """Claim your daily reward."""
        # Check cooldown
        remaining = await self.check_cooldown(ctx.author.id, "daily", 24 * 3600)
        if remaining:
            embed = await self.create_economy_embed("⏰ Daily Already Claimed", discord.Color.orange())
            embed.description = f"You can claim your daily reward again in **{self.format_time(remaining)}**"
            return await ctx.send(embed=embed)
        
        user_data = self.get_user(ctx.author.id)
        
        # Calculate reward with streak bonus
        base_reward = random.randint(500, 1000)
        streak = user_data.get("daily_streak", 0)
        
        # Streak bonus (max 7 days for 50% bonus)
        streak_bonus = min(streak, 7) * 50
        total_reward = base_reward + streak_bonus
        
        # Update user
        user_data["daily_streak"] = streak + 1
        user_data["last_daily"] = datetime.now().isoformat()
        
        result = await self.update_balance(ctx.author.id, wallet_change=total_reward)
        await self.set_cooldown(ctx.author.id, "daily")
        
        embed = await self.create_economy_embed("🎁 Daily Reward Claimed!", discord.Color.green())
        embed.description = f"You received {self.format_money(total_reward)}!"
        
        breakdown = f"• Base: {self.format_money(base_reward)}\n• Streak Bonus: {self.format_money(streak_bonus)} (Day {streak + 1})"
        embed.add_field(name="💰 Breakdown", value=breakdown, inline=False)
        embed.add_field(name="💵 New Balance", value=self.format_money(result["wallet"]), inline=False)
        embed.set_footer(text="Come back in 24 hours for your next reward!")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="work")
    async def work(self, ctx: commands.Context):
        """Work to earn money."""
        # Check cooldown
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
            "streamed on Twitch": (90, 200),
            "invested in stocks": (150, 300)
        }
        
        job, (min_earn, max_earn) = random.choice(list(jobs.items()))
        earnings = random.randint(min_earn, max_earn)
        
        # Critical work chance (10%)
        is_critical = random.random() < 0.1
        if is_critical:
            earnings *= 2
        
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
    
    @commands.command(name="crime", aliases=["steal"])
    @commands.cooldown(1, 7200, commands.BucketType.user)
    async def crime(self, ctx: commands.Context):
        """Commit a crime for high risk, high reward."""
        success_chance = 0.6  # 60% success rate
        
        if random.random() < success_chance:
            # Successful crime
            earnings = random.randint(200, 800)
            crimes = [
                "hacked a rich person's bank account",
                "successfully pulled off a heist",
                "sold rare items on the black market",
                "won big at an illegal casino"
            ]
            crime = random.choice(crimes)
            
            await self.update_balance(ctx.author.id, wallet_change=earnings)
            
            embed = await self.create_economy_embed("💰 Crime Successful!", discord.Color.green())
            embed.description = f"You {crime} and earned {self.format_money(earnings)}!"
            
        else:
            # Failed crime - lose money
            loss = random.randint(100, 400)
            user_data = self.get_user(ctx.author.id)
            actual_loss = min(loss, user_data["wallet"])
            
            failures = [
                "got caught shoplifting and had to pay a fine",
                "failed to hack the bank's security system",
                "were arrested and had to post bail",
                "got scammed in a shady deal"
            ]
            failure = random.choice(failures)
            
            await self.update_balance(ctx.author.id, wallet_change=-actual_loss)
            
            embed = await self.create_economy_embed("🚓 Crime Failed!", discord.Color.red())
            embed.description = f"You {failure} and lost {self.format_money(actual_loss)}!"
        
        await ctx.send(embed=embed)

    @commands.command(name="shop", aliases=["store"])
    async def shop(self, ctx: commands.Context):
        """Browse the shop for upgrades and items."""
        shop_items = self.get_shop_items()
        
        if not shop_items:
            embed = await self.create_economy_embed("🛍️ Shop")
            embed.description = "The shop is currently empty. Check back later!"
            return await ctx.send(embed=embed)
        
        embed = await self.create_economy_embed("🛍️ Economy Shop")
        embed.description = "Use `~~buy <item_id>` to purchase items!\n\n"
        
        for item in shop_items:
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
        item = self.get_shop_item(item_id)
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
        user_data = self.get_user(ctx.author.id)
        if user_data["wallet"] < item["price"]:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You need {self.format_money(item['price'])} but only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Process purchase
        await self.update_balance(ctx.author.id, wallet_change=-item["price"])
        
        # Handle different item types
        if item["type"] == "upgrade":
            # Apply upgrade immediately
            effect = item["effect"]
            if "bank_limit" in effect:
                user_data["bank_limit"] += effect["bank_limit"]
                await self.save_data()
        
        elif item["type"] in ["consumable", "permanent"]:
            # Add to inventory
            await self.add_to_inventory(ctx.author.id, {
                "id": item["id"],
                "name": item["name"],
                "type": item["type"],
                "effect": item["effect"],
                "emoji": item["emoji"]
            })
        
        # Update shop stock
        if item.get("stock", -1) > 0:
            item["stock"] -= 1
        
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
    
    @commands.command(name="inventory", aliases=["inv", "items"])
    async def inventory(self, ctx: commands.Context, member: discord.Member = None):
        """View your inventory or another user's inventory."""
        member = member or ctx.author
        inventory = await self.get_inventory(member.id)
        
        embed = await self.create_economy_embed(f"🎒 {member.display_name}'s Inventory")
        
        if not inventory:
            embed.description = "No items in inventory. Visit the shop with `~~shop`!"
            return await ctx.send(embed=embed)
        
        # Group items by type
        consumables = [item for item in inventory if item["type"] == "consumable"]
        permanent = [item for item in inventory if item["type"] == "permanent"]
        
        if consumables:
            consumable_text = ""
            for i, item in enumerate(consumables):
                consumable_text += f"`{i+1}.` {item['emoji']} **{item['name']}**\n"
            embed.add_field(name="🎁 Consumables", value=consumable_text, inline=False)
        
        if permanent:
            permanent_text = ""
            for item in permanent:
                permanent_text += f"{item['emoji']} **{item['name']}**\n"
            embed.add_field(name="💎 Permanent Items", value=permanent_text, inline=False)
        
        if member == ctx.author and consumables:
            embed.add_field(
                name="🔧 Usage",
                value="Use `~~use <item_number>` to use consumable items.",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="use")
    async def use_item(self, ctx: commands.Context, item_number: int):
        """Use a consumable item from your inventory."""
        inventory = await self.get_inventory(ctx.author.id)
        consumables = [item for item in inventory if item["type"] == "consumable"]
        
        if item_number < 1 or item_number > len(consumables):
            embed = await self.create_economy_embed("❌ Invalid Item Number", discord.Color.red())
            embed.description = f"Please choose a number between 1 and {len(consumables)}."
            return await ctx.send(embed=embed)
        
        item = consumables[item_number - 1]
        item_index = inventory.index(item)
        
        # Apply item effects
        effect = item["effect"]
        result_text = ""
        
        if "daily_bonus" in effect:
            result_text = f"Daily rewards are now increased by 20% for {effect['duration']} days! ✨"
        
        elif "work_bonus" in effect:
            result_text = f"Work earnings are now increased by 30% for {effect['duration']} days! 💼"
        
        elif "mystery_box" in effect:
            reward = random.randint(500, 5000)
            await self.update_balance(ctx.author.id, wallet_change=reward)
            result_text = f"You opened the mystery box and found {self.format_money(reward)}! 🎉"
        
        # Remove item from inventory
        await self.use_item(ctx.author.id, item_index)
        
        embed = await self.create_economy_embed(f"✅ {item['emoji']} {item['name']} Used!", discord.Color.green())
        embed.description = result_text
        await ctx.send(embed=embed)

    @commands.command(name="pay", aliases=["give", "transfer"])
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Pay another user money."""
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
        user_data = self.get_user(ctx.author.id)
        if user_data["wallet"] < amount:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet."
            return await ctx.send(embed=embed)
        
        # Process transfer
        success = await self.transfer_money(ctx.author.id, member.id, amount)
        
        if success:
            embed = await self.create_economy_embed("💸 Payment Successful", discord.Color.green())
            embed.description = f"{ctx.author.mention} paid {self.format_money(amount)} to {member.mention}"
            embed.set_footer(text=f"Transaction completed at {datetime.now().strftime('%H:%M:%S')}")
        else:
            embed = await self.create_economy_embed("⚠️ Transfer Failed", discord.Color.red())
            embed.description = "The payment could not be processed."
        
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb", "top", "rich"])
    async def leaderboard(self, ctx: commands.Context):
        """Show the wealth leaderboard."""
        users_data = self.data['users']
        
        if not users_data:
            embed = await self.create_economy_embed("📊 Leaderboard")
            embed.description = "No users have any money yet! Be the first to earn some!"
            return await ctx.send(embed=embed)
        
        # Calculate total wealth for each user
        user_totals = []
        for user_id, user_data in users_data.items():
            total = user_data.get("wallet", 0) + user_data.get("bank", 0)
            if total > 0:
                user_totals.append((int(user_id), total, user_data))
        
        # Sort by total wealth
        user_totals.sort(key=lambda x: x[1], reverse=True)
        
        embed = await self.create_economy_embed("📊 Wealth Leaderboard")
        embed.description = "Top 10 richest users on the server"
        
        medals = ["🥇", "🥈", "🥉"]
        emojis = ["💎", "💰", "🏦", "💵", "💴", "💶", "💷", "🪙", "💳", "📈"]
        
        leaderboard_text = ""
        for i, (user_id, total, user_data) in enumerate(user_totals[:10]):
            user = self.bot.get_user(user_id)
            username = user.display_name if user else f"User {user_id}"
            
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
        for i, (user_id, total, _) in enumerate(user_totals):
            if user_id == ctx.author.id:
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
    
    @commands.command(name="economystats", aliases=["estats"])
    @commands.has_permissions(administrator=True)
    async def economy_stats(self, ctx: commands.Context):
        """View economy system statistics (Admin only)."""
        stats = db.get_stats(self.data)
        
        embed = await self.create_economy_embed("📊 Economy System Statistics", discord.Color.blue())
        
        embed.add_field(name="👥 Total Users", value=stats['total_users'], inline=True)
        embed.add_field(name="💰 Total Money in Circulation", value=self.format_money(stats['total_money']), inline=True)
        embed.add_field(name="📅 System Created", value=datetime.fromisoformat(stats['created_at']).strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="💾 Last Save", value=datetime.fromisoformat(stats['last_save']).strftime("%H:%M:%S") if stats['last_save'] else "Never", inline=True)
        
        # Calculate average wealth
        avg_wealth = stats['total_money'] // stats['total_users'] if stats['total_users'] > 0 else 0
        embed.add_field(name="📈 Average Wealth", value=self.format_money(avg_wealth), inline=True)
        
        # Backup status
        backup_files = []
        for backup_file in db.backup_files:
            if os.path.exists(backup_file):
                backup_files.append("✅")
            else:
                backup_files.append("❌")
        
        embed.add_field(name="💾 Backup Status", value=" ".join(backup_files), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="saveeconomy", aliases=["forcedsave"])
    @commands.has_permissions(administrator=True)
    async def force_save(self, ctx: commands.Context):
        """Force save economy data (Admin only)."""
        await self.save_data()
        embed = await self.create_economy_embed("💾 Manual Save", discord.Color.green())
        embed.description = "Economy data has been manually saved with backup rotation."
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
