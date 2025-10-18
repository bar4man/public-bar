import discord
from discord.ext import commands
import motor.motor_asyncio
import asyncio
import random
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
import math

class MongoDB:
    """MongoDB database for economy data with persistence."""
    
    def __init__(self):
        self.client = None
        self.db = None
        self.connected = False
    
    async def connect(self):
        """Connect to MongoDB Atlas."""
        try:
            connection_string = os.getenv('MONGODB_URI')
            if not connection_string:
                logging.error("❌ MONGODB_URI environment variable not set")
                return False
            
            self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
            self.db = self.client.economy_bot
            
            # Test connection
            await self.client.admin.command('ping')
            self.connected = True
            logging.info("✅ Connected to MongoDB Atlas successfully")
            return True
            
        except Exception as e:
            logging.error(f"❌ MongoDB connection failed: {e}")
            self.connected = False
            return False
    
    async def initialize_collections(self):
        """Initialize collections with default data."""
        if not self.connected:
            return False
            
        try:
            # Create indexes
            await self.db.users.create_index("user_id", unique=True)
            await self.db.inventory.create_index([("user_id", 1), ("item_id", 1)])
            await self.db.cooldowns.create_index("created_at", expireAfterSeconds=86400)  # 24h TTL
            
            # Initialize shop if empty
            shop_count = await self.db.shop.count_documents({})
            if shop_count == 0:
                default_shop = {
                    "items": [
                        {
                            "id": 1,
                            "name": "💰 Small Wallet Upgrade",
                            "description": "Increase your wallet limit by 5,000£",
                            "price": 2000,
                            "type": "upgrade",
                            "effect": {"wallet_limit": 5000},
                            "emoji": "💰",
                            "stock": -1
                        },
                        {
                            "id": 2,
                            "name": "💳 Medium Wallet Upgrade", 
                            "description": "Increase your wallet limit by 15,000£",
                            "price": 8000,
                            "type": "upgrade",
                            "effect": {"wallet_limit": 15000},
                            "emoji": "💳",
                            "stock": -1
                        },
                        {
                            "id": 3,
                            "name": "💎 Large Wallet Upgrade",
                            "description": "Increase your wallet limit by 50,000£", 
                            "price": 25000,
                            "type": "upgrade",
                            "effect": {"wallet_limit": 50000},
                            "emoji": "💎",
                            "stock": -1
                        },
                        {
                            "id": 4,
                            "name": "🏦 Small Bank Upgrade",
                            "description": "Increase your bank limit by 50,000£",
                            "price": 5000,
                            "type": "upgrade",
                            "effect": {"bank_limit": 50000},
                            "emoji": "🏦",
                            "stock": -1
                        },
                        {
                            "id": 5,
                            "name": "🏛️ Medium Bank Upgrade",
                            "description": "Increase your bank limit by 150,000£",
                            "price": 15000,
                            "type": "upgrade",
                            "effect": {"bank_limit": 150000},
                            "emoji": "🏛️",
                            "stock": -1
                        },
                        {
                            "id": 6,
                            "name": "🎯 Large Bank Upgrade",
                            "description": "Increase your bank limit by 500,000£",
                            "price": 50000,
                            "type": "upgrade",
                            "effect": {"bank_limit": 500000},
                            "emoji": "🎯",
                            "stock": -1
                        },
                        {
                            "id": 7,
                            "name": "🎩 Lucky Hat",
                            "description": "Increases daily reward by 20% for 7 days",
                            "price": 3000,
                            "type": "consumable",
                            "effect": {"daily_bonus": 1.2, "duration": 7},
                            "emoji": "🎩",
                            "stock": -1
                        },
                        {
                            "id": 8,
                            "name": "🍀 Lucky Charm",
                            "description": "Increases work earnings by 30% for 5 days",
                            "price": 2500,
                            "type": "consumable",
                            "effect": {"work_bonus": 1.3, "duration": 5},
                            "emoji": "🍀",
                            "stock": -1
                        },
                        {
                            "id": 9,
                            "name": "🎁 Mystery Box",
                            "description": "Get a random amount of money between 500-5000£",
                            "price": 1000,
                            "type": "consumable", 
                            "effect": {"mystery_box": True},
                            "emoji": "🎁",
                            "stock": -1
                        }
                    ],
                    "created_at": datetime.now()
                }
                await self.db.shop.insert_one(default_shop)
                logging.info("✅ Default shop items created")
            
            logging.info("✅ MongoDB collections initialized")
            return True
            
        except Exception as e:
            logging.error(f"❌ MongoDB initialization failed: {e}")
            return False
    
    # User management
    async def get_user(self, user_id: int) -> Dict:
        """Get user data or create if doesn't exist."""
        if not self.connected:
            return self._get_default_user(user_id)
            
        try:
            user = await self.db.users.find_one({"user_id": user_id})
            if not user:
                user = self._get_default_user(user_id)
                await self.db.users.insert_one(user)
                logging.info(f"👤 New user created in MongoDB: {user_id}")
            return user
        except Exception as e:
            logging.error(f"❌ Error getting user {user_id}: {e}")
            return self._get_default_user(user_id)
    
    def _get_default_user(self, user_id: int) -> Dict:
        """Return default user structure."""
        return {
            "user_id": user_id,
            "wallet": 100,
            "wallet_limit": 50000,  # Default wallet limit: 50k
            "bank": 0,
            "bank_limit": 500000,   # Default bank limit: 500k
            "networth": 100,
            "daily_streak": 0,
            "last_daily": None,
            "total_earned": 0,
            "created_at": datetime.now(),
            "last_active": datetime.now()
        }
    
    async def update_user(self, user_id: int, update_data: Dict):
        """Update user data."""
        if not self.connected:
            return
            
        update_data["last_active"] = datetime.now()
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        """Update user's wallet and bank balance with limits."""
        user = await self.get_user(user_id)
        
        # Update wallet with limit check
        new_wallet = user['wallet'] + wallet_change
        if new_wallet > user['wallet_limit']:
            # If adding money would exceed wallet limit, put excess in bank
            excess = new_wallet - user['wallet_limit']
            user['wallet'] = user['wallet_limit']
            bank_change += excess  # Add excess to bank
        else:
            user['wallet'] = max(0, new_wallet)
        
        # Update bank with limit check
        new_bank = user['bank'] + bank_change
        if new_bank > user['bank_limit']:
            user['bank'] = user['bank_limit']
        else:
            user['bank'] = max(0, new_bank)
        
        user['networth'] = user['wallet'] + user['bank']
        user['last_active'] = datetime.now()
        
        if wallet_change > 0 or bank_change > 0:
            user['total_earned'] += (wallet_change + bank_change)
        
        await self.update_user(user_id, user)
        return user
    
    async def transfer_money(self, from_user: int, to_user: int, amount: int) -> bool:
        """Transfer money between users (wallet to wallet)."""
        from_user_data = await self.get_user(from_user)
        to_user_data = await self.get_user(to_user)
        
        # Check if sender has enough in wallet
        if from_user_data['wallet'] < amount:
            return False
        
        # Check if receiver has wallet space
        if to_user_data['wallet'] + amount > to_user_data['wallet_limit']:
            return False
        
        from_user_data['wallet'] -= amount
        to_user_data['wallet'] += amount
        
        # Update networth
        from_user_data['networth'] = from_user_data['wallet'] + from_user_data['bank']
        to_user_data['networth'] = to_user_data['wallet'] + to_user_data['bank']
        
        # Save both users
        await self.update_user(from_user, from_user_data)
        await self.update_user(to_user, to_user_data)
        
        return True
    
    # Cooldown management
    async def check_cooldown(self, user_id: int, command: str, cooldown_seconds: int) -> Optional[float]:
        """Check if user is on cooldown."""
        if not self.connected:
            return None
            
        try:
            cooldown = await self.db.cooldowns.find_one({
                "user_id": user_id,
                "command": command
            })
            
            if cooldown:
                last_used = cooldown['created_at']
                time_passed = (datetime.now() - last_used).total_seconds()
                
                if time_passed < cooldown_seconds:
                    return cooldown_seconds - time_passed
            
            return None
        except Exception as e:
            logging.error(f"❌ Error checking cooldown for user {user_id}: {e}")
            return None
    
    async def set_cooldown(self, user_id: int, command: str):
        """Set cooldown for a command."""
        if not self.connected:
            return
            
        try:
            await self.db.cooldowns.update_one(
                {"user_id": user_id, "command": command},
                {
                    "$set": {
                        "created_at": datetime.now(),
                        "expires_at": datetime.now() + timedelta(days=1)
                    }
                },
                upsert=True
            )
        except Exception as e:
            logging.error(f"❌ Error setting cooldown for user {user_id}: {e}")
    
    # Inventory management
    async def add_to_inventory(self, user_id: int, item: Dict):
        """Add item to user's inventory."""
        if not self.connected:
            return
            
        try:
            inventory_item = {
                "user_id": user_id,
                "item_id": item["id"],
                "name": item["name"],
                "type": item["type"],
                "effect": item["effect"],
                "emoji": item["emoji"],
                "purchased_at": datetime.now()
            }
            await self.db.inventory.insert_one(inventory_item)
        except Exception as e:
            logging.error(f"❌ Error adding to inventory for user {user_id}: {e}")
    
    async def get_inventory(self, user_id: int) -> List:
        """Get user's inventory."""
        if not self.connected:
            return []
            
        try:
            cursor = self.db.inventory.find({"user_id": user_id})
            return await cursor.to_list(length=100)
        except Exception as e:
            logging.error(f"❌ Error getting inventory for user {user_id}: {e}")
            return []
    
    async def use_item(self, user_id: int, item_id: int) -> bool:
        """Use item from inventory."""
        if not self.connected:
            return False
            
        try:
            result = await self.db.inventory.delete_one({"user_id": user_id, "item_id": item_id})
            return result.deleted_count > 0
        except Exception as e:
            logging.error(f"❌ Error using item for user {user_id}: {e}")
            return False
    
    # Shop methods
    async def get_shop_items(self) -> List:
        """Get all shop items."""
        if not self.connected:
            return self._get_default_shop_items()
            
        try:
            shop = await self.db.shop.find_one({})
            return shop.get('items', []) if shop else self._get_default_shop_items()
        except Exception as e:
            logging.error(f"❌ Error getting shop items: {e}")
            return self._get_default_shop_items()
    
    def _get_default_shop_items(self) -> List:
        """Return default shop items for fallback."""
        return [
            {
                "id": 1, "name": "💰 Small Wallet Upgrade", "price": 2000,
                "description": "Increase your wallet limit by 5,000£",
                "type": "upgrade", "effect": {"wallet_limit": 5000}, "emoji": "💰", "stock": -1
            },
            {
                "id": 2, "name": "💳 Medium Wallet Upgrade", "price": 8000,
                "description": "Increase your wallet limit by 15,000£", 
                "type": "upgrade", "effect": {"wallet_limit": 15000}, "emoji": "💳", "stock": -1
            },
            {
                "id": 3, "name": "💎 Large Wallet Upgrade", "price": 25000,
                "description": "Increase your wallet limit by 50,000£",
                "type": "upgrade", "effect": {"wallet_limit": 50000}, "emoji": "💎", "stock": -1
            },
            {
                "id": 4, "name": "🏦 Small Bank Upgrade", "price": 5000,
                "description": "Increase your bank limit by 50,000£",
                "type": "upgrade", "effect": {"bank_limit": 50000}, "emoji": "🏦", "stock": -1
            },
            {
                "id": 5, "name": "🏛️ Medium Bank Upgrade", "price": 15000,
                "description": "Increase your bank limit by 150,000£",
                "type": "upgrade", "effect": {"bank_limit": 150000}, "emoji": "🏛️", "stock": -1
            },
            {
                "id": 6, "name": "🎯 Large Bank Upgrade", "price": 50000,
                "description": "Increase your bank limit by 500,000£",
                "type": "upgrade", "effect": {"bank_limit": 500000}, "emoji": "🎯", "stock": -1
            },
            {
                "id": 7, "name": "🎩 Lucky Hat", "price": 3000,
                "description": "Increases daily reward by 20% for 7 days",
                "type": "consumable", "effect": {"daily_bonus": 1.2, "duration": 7}, "emoji": "🎩", "stock": -1
            },
            {
                "id": 8, "name": "🍀 Lucky Charm", "price": 2500,
                "description": "Increases work earnings by 30% for 5 days",
                "type": "consumable", "effect": {"work_bonus": 1.3, "duration": 5}, "emoji": "🍀", "stock": -1
            },
            {
                "id": 9, "name": "🎁 Mystery Box", "price": 1000,
                "description": "Get a random amount of money between 500-5000£",
                "type": "consumable", "effect": {"mystery_box": True}, "emoji": "🎁", "stock": -1
            }
        ]
    
    async def get_stats(self):
        """Get database statistics."""
        if not self.connected:
            return {"total_users": 0, "total_money": 0, "database": "disconnected"}
            
        try:
            total_users = await self.db.users.count_documents({})
            
            pipeline = [
                {
                    "$group": {
                        "_id": None,
                        "total_money": {
                            "$sum": {
                                "$add": ["$wallet", "$bank"]
                            }
                        }
                    }
                }
            ]
            
            result = await self.db.users.aggregate(pipeline).to_list(length=1)
            total_money = result[0]['total_money'] if result else 0
            
            return {
                "total_users": total_users,
                "total_money": total_money,
                "database": "mongodb"
            }
        except Exception as e:
            logging.error(f"❌ Error getting stats: {e}")
            return {"total_users": 0, "total_money": 0, "database": "error"}

# Global database instance
db = MongoDB()

class Economy(commands.Cog):
    """Enhanced economy system with rebalanced bank/wallet system."""
    
    def __init__(self, bot):
        self.bot = bot
        self.ready = False
        logging.info("✅ Economy system initialized")
    
    async def cog_load(self):
        """Load data when cog is loaded."""
        # Connect to MongoDB
        success = await db.connect()
        if success:
            await db.initialize_collections()
            self.ready = True
            logging.info("✅ Economy system loaded with MongoDB")
        else:
            logging.error("❌ Economy system using fallback mode (no persistence)")
            self.ready = False
    
    # User management methods
    async def get_user(self, user_id: int) -> Dict:
        """Get user data."""
        return await db.get_user(user_id)
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        """Update user's wallet and bank balance."""
        return await db.update_balance(user_id, wallet_change, bank_change)
    
    async def transfer_money(self, from_user: int, to_user: int, amount: int) -> bool:
        """Transfer money between users."""
        return await db.transfer_money(from_user, to_user, amount)
    
    # Cooldown management
    async def check_cooldown(self, user_id: int, command: str, cooldown_seconds: int) -> Optional[float]:
        """Check if user is on cooldown."""
        return await db.check_cooldown(user_id, command, cooldown_seconds)
    
    async def set_cooldown(self, user_id: int, command: str):
        """Set cooldown for a command."""
        await db.set_cooldown(user_id, command)
    
    # Inventory management
    async def add_to_inventory(self, user_id: int, item: Dict):
        """Add item to user's inventory."""
        await db.add_to_inventory(user_id, item)
    
    async def get_inventory(self, user_id: int) -> List:
        """Get user's inventory."""
        return await db.get_inventory(user_id)
    
    async def use_item(self, user_id: int, item_index: int) -> bool:
        """Use item from inventory by index."""
        inventory = await self.get_inventory(user_id)
        if item_index < len(inventory):
            item = inventory[item_index]
            return await db.use_item(user_id, item['item_id'])
        return False
    
    # Shop methods
    async def get_shop_items(self) -> List:
        """Get all shop items."""
        return await db.get_shop_items()
    
    async def get_shop_item(self, item_id: int) -> Optional[Dict]:
        """Get specific shop item."""
        items = await self.get_shop_items()
        for item in items:
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
    
    def calculate_upgrade_cost(self, current_limit: int, upgrade_type: str) -> int:
        """Calculate scaling cost for upgrades."""
        base_cost = 1000 if upgrade_type == "wallet" else 2000
        multiplier = (current_limit / 50000) if upgrade_type == "wallet" else (current_limit / 500000)
        return int(base_cost * multiplier * 1.5)
    
    async def create_economy_embed(self, title: str, color: discord.Color = discord.Color.gold()) -> discord.Embed:
        """Create a standardized economy embed."""
        database_status = "✅ MongoDB" if self.ready else "⚠️ Memory Only"
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Economy System | {database_status}")
        return embed

    # ========== COMMANDS ==========
    
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        """Check your or someone else's balance."""
        member = member or ctx.author
        user_data = await self.get_user(member.id)
        
        wallet = user_data["wallet"]
        wallet_limit = user_data["wallet_limit"]
        bank = user_data["bank"]
        bank_limit = user_data["bank_limit"]
        total = wallet + bank
        
        wallet_usage = (wallet / wallet_limit) * 100 if wallet_limit > 0 else 0
        bank_usage = (bank / bank_limit) * 100 if bank_limit > 0 else 0
        
        embed = await self.create_economy_embed(f"💰 {member.display_name}'s Balance")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💵 Wallet", value=f"{self.format_money(wallet)} / {self.format_money(wallet_limit)}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{self.format_money(bank)} / {self.format_money(bank_limit)}", inline=True)
        embed.add_field(name="💎 Total", value=self.format_money(total), inline=True)
        
        # Usage bars
        wallet_bars = 10
        wallet_filled = min(wallet_bars, int(wallet_usage / 10))
        wallet_bar = "█" * wallet_filled + "░" * (wallet_bars - wallet_filled)
        
        bank_bars = 10
        bank_filled = min(bank_bars, int(bank_usage / 10))
        bank_bar = "█" * bank_filled + "░" * (bank_bars - bank_filled)
        
        embed.add_field(name="💵 Wallet Usage", value=f"`{wallet_bar}` {wallet_usage:.1f}%", inline=False)
        embed.add_field(name="🏦 Bank Usage", value=f"`{bank_bar}` {bank_usage:.1f}%", inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="wallet", aliases=["wal"])
    async def wallet(self, ctx: commands.Context, member: discord.Member = None):
        """View your wallet balance."""
        member = member or ctx.author
        user_data = await self.get_user(member.id)
        
        wallet = user_data["wallet"]
        wallet_limit = user_data["wallet_limit"]
        wallet_usage = (wallet / wallet_limit) * 100 if wallet_limit > 0 else 0
        
        embed = await self.create_economy_embed(f"💵 {member.display_name}'s Wallet")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💰 Wallet Balance", value=f"**{self.format_money(wallet)} / {self.format_money(wallet_limit)}**", inline=False)
        
        # Usage bar
        bars = 10
        filled_bars = min(bars, int(wallet_usage / 10))
        bar = "█" * filled_bars + "░" * (bars - filled_bars)
        embed.add_field(name="📊 Wallet Usage", value=f"`{bar}` {wallet_usage:.1f}%", inline=False)
        
        if member == ctx.author:
            embed.add_field(name="💡 Quick Actions", 
                          value="• Use `~~deposit <amount>` to move money to bank\n• Use `~~withdraw <amount>` to get money from bank\n• Use `~~upgrade wallet` to increase wallet limit", 
                          inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="bank")
    async def bank(self, ctx: commands.Context, member: discord.Member = None):
        """View your bank balance."""
        member = member or ctx.author
        user_data = await self.get_user(member.id)
        
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
                          value="• Use `~~deposit <amount|all>` to add money\n• Use `~~withdraw <amount|all>` to take money\n• Use `~~upgrade bank` to increase bank limit\n• **Shop purchases use bank money!**", 
                          inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="networth", aliases=["nw", "worth"])
    async def networth(self, ctx: commands.Context, member: discord.Member = None):
        """View your total net worth."""
        member = member or ctx.author
        user_data = await self.get_user(member.id)
        
        wallet = user_data["wallet"]
        bank = user_data["bank"]
        total = wallet + bank
        
        embed = await self.create_economy_embed(f"💎 {member.display_name}'s Net Worth")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💵 Wallet", value=self.format_money(wallet), inline=True)
        embed.add_field(name="🏦 Bank", value=self.format_money(bank), inline=True)
        embed.add_field(name="💎 Total Net Worth", value=f"**{self.format_money(total)}**", inline=True)
        
        # Wealth tier
        if total >= 10000000:
            tier = "👑 Emperor"
            color = discord.Color.gold()
        elif total >= 5000000:
            tier = "💎 Tycoon"
            color = discord.Color.purple()
        elif total >= 1000000:
            tier = "🏦 Millionaire" 
            color = discord.Color.blue()
        elif total >= 500000:
            tier = "💵 Wealthy"
            color = discord.Color.green()
        elif total >= 100000:
            tier = "🪙 Stable"
            color = discord.Color.green()
        else:
            tier = "🌱 Starting"
            color = discord.Color.light_grey()
        
        embed.add_field(name="🏆 Wealth Tier", value=tier, inline=False)
        embed.color = color
        
        if member == ctx.author:
            embed.add_field(name="📈 Growth Tips", 
                          value="• Use `~~work` every hour\n• Claim `~~daily` rewards\n• Play games for bonuses\n• **Upgrade your bank to store more money!**", 
                          inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str):
        """Deposit money from wallet to bank."""
        user_data = await self.get_user(ctx.author.id)
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
        embed.add_field(name="💵 New Wallet", value=f"{self.format_money(result['wallet'])} / {self.format_money(result['wallet_limit'])}", inline=True)
        embed.add_field(name="🏦 New Bank", value=f"{self.format_money(result['bank'])} / {self.format_money(result['bank_limit'])}", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Withdraw money from bank to wallet."""
        user_data = await self.get_user(ctx.author.id)
        wallet = user_data["wallet"]
        bank = user_data["bank"]
        wallet_limit = user_data["wallet_limit"]
        
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
        
        if wallet + withdraw_amount > wallet_limit:
            embed = await self.create_economy_embed("❌ Wallet Limit Exceeded", discord.Color.red())
            embed.description = f"Your wallet can only hold {self.format_money(wallet_limit)}. You have {self.format_money(wallet)} already."
            return await ctx.send(embed=embed)
        
        # Process withdrawal
        result = await self.update_balance(ctx.author.id, wallet_change=withdraw_amount, bank_change=-withdraw_amount)
        
        embed = await self.create_economy_embed("🏦 Withdrawal Successful", discord.Color.green())
        embed.description = f"Withdrew {self.format_money(withdraw_amount)} from your bank."
        embed.add_field(name="💵 New Wallet", value=f"{self.format_money(result['wallet'])} / {self.format_money(result['wallet_limit'])}", inline=True)
        embed.add_field(name="🏦 New Bank", value=f"{self.format_money(result['bank'])} / {self.format_money(result['bank_limit'])}", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name="upgrade")
    async def upgrade(self, ctx: commands.Context, upgrade_type: str = None):
        """Upgrade your wallet or bank limits with scaling costs."""
        if not upgrade_type or upgrade_type.lower() not in ["wallet", "bank"]:
            embed = await self.create_economy_embed("🛠️ Upgrade System", discord.Color.blue())
            embed.description = "Upgrade your wallet or bank limits with scaling costs.\n\n**Usage:** `~~upgrade wallet` or `~~upgrade bank`"
            embed.add_field(
                name="💵 Wallet Upgrades", 
                value="• Increases how much cash you can carry\n• Essential for transfers and payments\n• Starts at 50k, scales infinitely",
                inline=False
            )
            embed.add_field(
                name="🏦 Bank Upgrades", 
                value="• Increases your storage capacity\n• **Required for shop purchases**\n• Starts at 500k, scales infinitely",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        upgrade_type = upgrade_type.lower()
        user_data = await self.get_user(ctx.author.id)
        
        current_limit = user_data[f"{upgrade_type}_limit"]
        upgrade_cost = self.calculate_upgrade_cost(current_limit, upgrade_type)
        
        # Check if user has enough money in bank for the upgrade
        if user_data["bank"] < upgrade_cost:
            embed = await self.create_economy_embed("❌ Insufficient Funds", discord.Color.red())
            embed.description = f"You need {self.format_money(upgrade_cost)} in your bank for this upgrade, but you only have {self.format_money(user_data['bank'])}."
            embed.add_field(name="💡 Tip", value="Make sure the money is in your **bank**, not your wallet!", inline=False)
            return await ctx.send(embed=embed)
        
        # Calculate new limit (10% increase)
        new_limit = int(current_limit * 1.1)
        
        # Process upgrade
        result = await self.update_balance(ctx.author.id, bank_change=-upgrade_cost)
        result[f"{upgrade_type}_limit"] = new_limit
        await db.update_user(ctx.author.id, result)
        
        embed = await self.create_economy_embed("✅ Upgrade Successful!", discord.Color.green())
        
        if upgrade_type == "wallet":
            embed.description = f"Upgraded your wallet from {self.format_money(current_limit)} to {self.format_money(new_limit)}!"
            embed.add_field(name="💵 New Wallet Limit", value=self.format_money(new_limit), inline=True)
        else:
            embed.description = f"Upgraded your bank from {self.format_money(current_limit)} to {self.format_money(new_limit)}!"
            embed.add_field(name="🏦 New Bank Limit", value=self.format_money(new_limit), inline=True)
        
        embed.add_field(name="💰 Cost", value=self.format_money(upgrade_cost), inline=True)
        embed.add_field(name="🏦 Remaining Bank", value=self.format_money(result["bank"]), inline=True)
        
        # Show next upgrade cost
        next_cost = self.calculate_upgrade_cost(new_limit, upgrade_type)
        embed.add_field(name="📈 Next Upgrade", value=f"Will cost {self.format_money(next_cost)}", inline=False)
        
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
        
        user_data = await self.get_user(ctx.author.id)
        
        # Calculate reward with streak bonus
        base_reward = random.randint(1000, 2000)  # Increased for new economy
        streak = user_data.get("daily_streak", 0)
        
        # Streak bonus (max 7 days for 50% bonus)
        streak_bonus = min(streak, 7) * 100
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
        embed.add_field(name="💵 New Balance", value=f"{self.format_money(result['wallet'])} / {self.format_money(result['wallet_limit'])}", inline=False)
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
        
        # Job types with different earnings (increased for new economy)
        jobs = {
            "delivered packages": (100, 200),
            "drove for Uber": (120, 240),
            "worked at a café": (80, 160),
            "coded a website": (200, 500),
            "designed graphics": (160, 300),
            "streamed on Twitch": (180, 400),
            "invested in stocks": (300, 600)
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
        
        embed.add_field(name="💵 New Balance", value=f"{self.format_money(result['wallet'])} / {self.format_money(result['wallet_limit'])}", inline=False)
        embed.set_footer(text="You can work again in 1 hour!")
        
        await ctx.send(embed=embed)

    @commands.command(name="shop", aliases=["store"])
    async def shop(self, ctx: commands.Context):
        """Browse the shop for upgrades and items."""
        shop_items = await self.get_shop_items()
        
        if not shop_items:
            embed = await self.create_economy_embed("🛍️ Shop")
            embed.description = "The shop is currently empty. Check back later!"
            return await ctx.send(embed=embed)
        
        embed = await self.create_economy_embed("🛍️ Economy Shop")
        embed.description = "**Important:** All shop purchases use money from your **BANK**!\nUse `~~deposit` to move money to your bank first.\n\n"
        
        for item in shop_items:
            stock_info = "∞" if item.get("stock", -1) == -1 else f"{item['stock']} left"
            embed.add_field(
                name=f"{item['emoji']} {item['name']} - {self.format_money(item['price'])}",
                value=f"**ID:** `{item['id']}` | **Stock:** {stock_info}\n{item['description']}",
                inline=False
            )
        
        embed.add_field(
            name="💡 How to Buy",
            value="Use `~~buy <item_id>` to purchase an item.\nExample: `~~buy 1`\n**Remember:** You need the money in your **BANK**!",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="buy", aliases=["purchase"])
    async def buy(self, ctx: commands.Context, item_id: int):
        """Purchase an item from the shop using BANK money."""
        item = await self.get_shop_item(item_id)
        if not item:
            embed = await self.create_economy_embed("❌ Item Not Found", discord.Color.red())
            embed.description = f"No item found with ID `{item_id}`. Use `~~shop` to see available items."
            return await ctx.send(embed=embed)
        
        # Check stock
        if item.get("stock", -1) == 0:
            embed = await self.create_economy_embed("❌ Out of Stock", discord.Color.red())
            embed.description = f"**{item['name']}** is out of stock! Check back later."
            return await ctx.send(embed=embed)
        
        # Check balance in BANK (not wallet!)
        user_data = await self.get_user(ctx.author.id)
        if user_data["bank"] < item["price"]:
            embed = await self.create_economy_embed("❌ Insufficient Bank Funds", discord.Color.red())
            embed.description = f"You need {self.format_money(item['price'])} in your **BANK** but only have {self.format_money(user_data['bank'])}.\nUse `~~deposit` to move money from wallet to bank."
            return await ctx.send(embed=embed)
        
        # Process purchase from BANK
        await self.update_balance(ctx.author.id, bank_change=-item["price"])
        
        # Handle different item types
        if item["type"] == "upgrade":
            # Apply upgrade immediately
            effect = item["effect"]
            if "bank_limit" in effect:
                user_data["bank_limit"] += effect["bank_limit"]
            elif "wallet_limit" in effect:
                user_data["wallet_limit"] += effect["wallet_limit"]
            await db.update_user(ctx.author.id, user_data)
        
        elif item["type"] in ["consumable", "permanent"]:
            # Add to inventory
            await self.add_to_inventory(ctx.author.id, item)
        
        # Update shop stock
        if item.get("stock", -1) > 0:
            item["stock"] -= 1
        
        # Success message
        embed = await self.create_economy_embed("✅ Purchase Successful!", discord.Color.green())
        embed.description = f"You purchased **{item['emoji']} {item['name']}** for {self.format_money(item['price'])} from your bank!"
        
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
        
        # Show remaining bank balance
        user_data = await self.get_user(ctx.author.id)
        embed.add_field(name="🏦 Remaining Bank", value=f"{self.format_money(user_data['bank'])} / {self.format_money(user_data['bank_limit'])}", inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="pay", aliases=["give", "transfer"])
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Pay another user money from your WALLET."""
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
        
        # Check if user has enough money in WALLET
        user_data = await self.get_user(ctx.author.id)
        if user_data["wallet"] < amount:
            embed = await self.create_economy_embed("❌ Insufficient Wallet Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(user_data['wallet'])} in your wallet.\nUse `~~withdraw` to get money from your bank."
            return await ctx.send(embed=embed)
        
        # Check if receiver has wallet space
        receiver_data = await self.get_user(member.id)
        if receiver_data["wallet"] + amount > receiver_data["wallet_limit"]:
            embed = await self.create_economy_embed("❌ Receiver Wallet Full", discord.Color.red())
            embed.description = f"{member.display_name}'s wallet is full! They need to upgrade their wallet limit or deposit to bank."
            return await ctx.send(embed=embed)
        
        # Process transfer (wallet to wallet)
        success = await self.transfer_money(ctx.author.id, member.id, amount)
        
        if success:
            embed = await self.create_economy_embed("💸 Payment Successful", discord.Color.green())
            embed.description = f"{ctx.author.mention} paid {self.format_money(amount)} to {member.mention} from their wallet!"
            embed.add_field(name="🔒 Security Note", value="All payments use wallet money. Shop purchases use bank money.", inline=False)
            embed.set_footer(text=f"Transaction completed at {datetime.now().strftime('%H:%M:%S')}")
        else:
            embed = await self.create_economy_embed("⚠️ Transfer Failed", discord.Color.red())
            embed.description = "The payment could not be processed."
        
        await ctx.send(embed=embed)

    # ... (keep the rest of the commands like inventory, use, leaderboard, etc. the same)

async def setup(bot):
    await bot.add_cog(Economy(bot))
