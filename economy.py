import discord
from discord.ext import commands
import motor.motor_asyncio
import asyncio
import random
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple

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
            "bank": 0,
            "bank_limit": 5000,
            "networth": 100,
            "daily_streak": 0,
            "last_daily": None,
            "total_earned": 0,
            "created_at": datetime.now(),
            "last_active": datetime.now()
        }
    
    async def update_user(self, user_id: int, update_data: Dict) -> bool:
        """Update user data and wait for completion."""
        if not self.connected:
            return False
            
        try:
            update_data["last_active"] = datetime.now()
            result = await self.db.users.update_one(
                {"user_id": user_id},
                {"$set": update_data}
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            logging.error(f"❌ Error updating user {user_id}: {e}")
            return False
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        """Update user's wallet and bank balance with proper database operations."""
        if not self.connected:
            user = self._get_default_user(user_id)
            user['wallet'] = max(0, user['wallet'] + wallet_change)
            user['bank'] = max(0, user['bank'] + bank_change)
            return user
            
        try:
            # Use atomic operations to update the database directly
            update_data = {
                "$inc": {
                    "wallet": wallet_change,
                    "bank": bank_change
                },
                "$set": {
                    "last_active": datetime.now()
                }
            }
            
            # Ensure values don't go negative
            if wallet_change < 0:
                update_data["$inc"]["wallet"] = max(wallet_change, -await self.get_user_wallet(user_id))
            if bank_change < 0:
                update_data["$inc"]["bank"] = max(bank_change, -await self.get_user_bank(user_id))
            
            # Perform the update
            result = await self.db.users.update_one(
                {"user_id": user_id},
                update_data,
                upsert=True  # Create user if doesn't exist
            )
            
            # Get the updated user data
            user = await self.get_user(user_id)
            
            # Ensure bank doesn't exceed limit and update networth
            if user['bank'] > user['bank_limit']:
                user['bank'] = user['bank_limit']
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {"$set": {"bank": user['bank_limit']}}
                )
            
            user['networth'] = user['wallet'] + user['bank']
            
            # Update networth in database
            await self.db.users.update_one(
                {"user_id": user_id},
                {"$set": {"networth": user['networth']}}
            )
            
            # Update total earned if we added money
            if wallet_change > 0 or bank_change > 0:
                await self.db.users.update_one(
                    {"user_id": user_id},
                    {"$inc": {"total_earned": wallet_change + bank_change}}
                )
                user['total_earned'] += (wallet_change + bank_change)
            
            logging.info(f"💰 Updated balance for user {user_id}: +{wallet_change} wallet, +{bank_change} bank")
            return user
            
        except Exception as e:
            logging.error(f"❌ Error updating balance for user {user_id}: {e}")
            return await self.get_user(user_id)
    
    async def get_user_wallet(self, user_id: int) -> int:
        """Get just the wallet amount."""
        user = await self.get_user(user_id)
        return user.get('wallet', 100)
    
    async def get_user_bank(self, user_id: int) -> int:
        """Get just the bank amount."""
        user = await self.get_user(user_id)
        return user.get('bank', 0)
    
    # Inventory management
    async def add_to_inventory(self, user_id: int, item: Dict) -> bool:
        """Add item to user's inventory."""
        if not self.connected:
            return False
            
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
            result = await self.db.inventory.insert_one(inventory_item)
            return result.acknowledged
        except Exception as e:
            logging.error(f"❌ Error adding to inventory for user {user_id}: {e}")
            return False
    
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
    
    async def set_cooldown(self, user_id: int, command: str) -> bool:
        """Set cooldown for a command."""
        if not self.connected:
            return False
            
        try:
            result = await self.db.cooldowns.update_one(
                {"user_id": user_id, "command": command},
                {
                    "$set": {
                        "created_at": datetime.now(),
                        "expires_at": datetime.now() + timedelta(days=1)
                    }
                },
                upsert=True
            )
            return result.acknowledged
        except Exception as e:
            logging.error(f"❌ Error setting cooldown for user {user_id}: {e}")
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
                "id": 1, "name": "💰 Small Bank Upgrade", "price": 2000,
                "description": "Increase your bank limit by 5,000£",
                "type": "upgrade", "effect": {"bank_limit": 5000}, "emoji": "💰", "stock": -1
            },
            {
                "id": 2, "name": "🏦 Medium Bank Upgrade", "price": 5000,
                "description": "Increase your bank limit by 15,000£", 
                "type": "upgrade", "effect": {"bank_limit": 15000}, "emoji": "🏦", "stock": -1
            },
            {
                "id": 3, "name": "💎 Large Bank Upgrade", "price": 15000,
                "description": "Increase your bank limit by 50,000£",
                "type": "upgrade", "effect": {"bank_limit": 50000}, "emoji": "💎", "stock": -1
            },
            {
                "id": 4, "name": "🎩 Lucky Hat", "price": 3000,
                "description": "Increases daily reward by 20% for 7 days",
                "type": "consumable", "effect": {"daily_bonus": 1.2, "duration": 7}, "emoji": "🎩", "stock": -1
            },
            {
                "id": 5, "name": "🍀 Lucky Charm", "price": 2500,
                "description": "Increases work earnings by 30% for 5 days",
                "type": "consumable", "effect": {"work_bonus": 1.3, "duration": 5}, "emoji": "🍀", "stock": -1
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
    """Enhanced economy system with MongoDB persistence."""
    
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
        """Get user data directly from database."""
        return await db.get_user(user_id)
    
    async def update_balance(self, user_id: int, wallet_change: int = 0, bank_change: int = 0) -> Dict:
        """Update user's wallet and bank balance."""
        return await db.update_balance(user_id, wallet_change, bank_change)
    
    async def transfer_money(self, from_user: int, to_user: int, amount: int) -> bool:
        """Transfer money between users."""
        from_user_data = await db.get_user(from_user)
        
        if from_user_data['wallet'] < amount:
            return False
        
        # Use atomic operations for both users
        try:
            # Deduct from sender
            await db.update_balance(from_user, wallet_change=-amount)
            # Add to receiver
            await db.update_balance(to_user, wallet_change=amount)
            return True
        except Exception as e:
            logging.error(f"❌ Error transferring money: {e}")
            return False
    
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
        user_data = await self.get_user(member.id)
        
        embed = await self.create_economy_embed(f"💵 {member.display_name}'s Wallet")
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💰 Wallet Balance", value=f"**{self.format_money(user_data['wallet'])}**", inline=False)
        
        if member == ctx.author:
            embed.add_field(name="💡 Quick Actions", 
                          value="• Use `~~deposit <amount>` to move money to bank\n• Use `~~withdraw <amount>` to get money from bank", 
                          inline=False)
        
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
        base_reward = random.randint(500, 1000)
        streak = user_data.get("daily_streak", 0)
        
        # Streak bonus (max 7 days for 50% bonus)
        streak_bonus = min(streak, 7) * 50
        total_reward = base_reward + streak_bonus
        
        # Update user in database
        result = await self.update_balance(ctx.author.id, wallet_change=total_reward)
        
        # Update streak and last daily
        await db.update_user(ctx.author.id, {
            "daily_streak": streak + 1,
            "last_daily": datetime.now().isoformat()
        })
        
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

    @commands.command(name="debug_user")
    async def debug_user(self, ctx: commands.Context, member: discord.Member = None):
        """Debug command to check user data."""
        member = member or ctx.author
        user_data = await self.get_user(member.id)
        
        embed = await self.create_economy_embed(f"🐛 Debug: {member.display_name}", discord.Color.blue())
        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.add_field(name="Wallet", value=user_data.get('wallet', 'N/A'), inline=True)
        embed.add_field(name="Bank", value=user_data.get('bank', 'N/A'), inline=True)
        embed.add_field(name="Database", value="Connected" if self.ready else "Disconnected", inline=True)
        embed.add_field(name="Last Active", value=str(user_data.get('last_active', 'N/A')), inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
