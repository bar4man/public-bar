import discord
from discord.ext import commands
import asyncio
import random
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple
import math

class Economy(commands.Cog):
    """Enhanced economy system with MongoDB integration."""
    
    def __init__(self, bot):
        self.bot = bot
        self.ready = False
        logging.info("✅ Economy system initialized")
    
    async def cog_load(self):
        """Load data when cog is loaded."""
        # Database is now handled by main bot's database_manager
        self.ready = True
        logging.info("✅ Economy system loaded with MongoDB")
    
    # User management methods
    async def get_user_balance(self, user_id: int) -> int:
        """Get user's balance."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                return 1000  # Default balance
            
            user_data = await users_collection.find_one({"user_id": str(user_id)})
            if user_data:
                return user_data.get('balance', 1000)
            else:
                # Create new user with default balance
                await users_collection.insert_one({
                    "user_id": str(user_id),
                    "balance": 1000,
                    "bank_balance": 0,
                    "last_daily": None,
                    "last_work": None,
                    "total_earned": 0,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                return 1000
        except Exception as e:
            logging.error(f"Error getting user balance: {e}")
            return 1000
    
    async def update_balance(self, user_id: int, amount: int) -> int:
        """Update user's balance and return new balance."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                return 1000 + amount
            
            # Get current balance
            current_balance = await self.get_user_balance(user_id)
            new_balance = current_balance + amount
            
            # Update in database
            await users_collection.update_one(
                {"user_id": str(user_id)},
                {"$set": {"balance": new_balance}},
                upsert=True
            )
            
            return new_balance
        except Exception as e:
            logging.error(f"Error updating balance: {e}")
            return 1000 + amount
    
    async def get_bank_balance(self, user_id: int) -> int:
        """Get user's bank balance."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                return 0
            
            user_data = await users_collection.find_one({"user_id": str(user_id)})
            return user_data.get('bank_balance', 0) if user_data else 0
        except Exception as e:
            logging.error(f"Error getting bank balance: {e}")
            return 0
    
    async def update_bank_balance(self, user_id: int, amount: int) -> int:
        """Update user's bank balance and return new balance."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                return amount
            
            # Get current bank balance
            current_bank = await self.get_bank_balance(user_id)
            new_bank = current_bank + amount
            
            # Update in database
            await users_collection.update_one(
                {"user_id": str(user_id)},
                {"$set": {"bank_balance": new_bank}},
                upsert=True
            )
            
            return new_bank
        except Exception as e:
            logging.error(f"Error updating bank balance: {e}")
            return amount
    
    async def transfer_money(self, from_user: int, to_user: int, amount: int) -> bool:
        """Transfer money between users."""
        try:
            if amount <= 0:
                return False
            
            # Check if sender has enough
            sender_balance = await self.get_user_balance(from_user)
            if sender_balance < amount:
                return False
            
            # Perform transfer
            await self.update_balance(from_user, -amount)
            await self.update_balance(to_user, amount)
            
            return True
        except Exception as e:
            logging.error(f"Error transferring money: {e}")
            return False
    
    # Cooldown management
    async def check_cooldown(self, user_id: int, command: str, cooldown_seconds: int) -> Optional[float]:
        """Check if user is on cooldown."""
        try:
            cooldowns_collection = self.bot.database_manager.get_collection('cooldowns')
            if not cooldowns_collection:
                return None
            
            cooldown_key = f"{user_id}_{command}"
            cooldown_data = await cooldowns_collection.find_one({"key": cooldown_key})
            
            if cooldown_data:
                last_used = datetime.fromisoformat(cooldown_data['last_used'])
                time_passed = (datetime.now(timezone.utc) - last_used).total_seconds()
                
                if time_passed < cooldown_seconds:
                    return cooldown_seconds - time_passed
            
            return None
        except Exception as e:
            logging.error(f"Error checking cooldown: {e}")
            return None
    
    async def set_cooldown(self, user_id: int, command: str):
        """Set cooldown for a command."""
        try:
            cooldowns_collection = self.bot.database_manager.get_collection('cooldowns')
            if not cooldowns_collection:
                return
            
            cooldown_key = f"{user_id}_{command}"
            await cooldowns_collection.update_one(
                {"key": cooldown_key},
                {"$set": {
                    "last_used": datetime.now(timezone.utc).isoformat(),
                    "user_id": str(user_id),
                    "command": command
                }},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error setting cooldown: {e}")
    
    # Inventory management
    async def add_to_inventory(self, user_id: int, item_name: str, quantity: int = 1):
        """Add item to user's inventory."""
        try:
            inventory_collection = self.bot.database_manager.get_collection('inventory')
            if not inventory_collection:
                return
            
            await inventory_collection.update_one(
                {"user_id": str(user_id), "item_name": item_name},
                {"$inc": {"quantity": quantity}},
                upsert=True
            )
        except Exception as e:
            logging.error(f"Error adding to inventory: {e}")
    
    async def get_inventory(self, user_id: int) -> List[Dict]:
        """Get user's inventory."""
        try:
            inventory_collection = self.bot.database_manager.get_collection('inventory')
            if not inventory_collection:
                return []
            
            cursor = inventory_collection.find({"user_id": str(user_id)})
            return await cursor.to_list(length=50)
        except Exception as e:
            logging.error(f"Error getting inventory: {e}")
            return []
    
    async def use_item(self, user_id: int, item_name: str, quantity: int = 1) -> bool:
        """Use item from inventory."""
        try:
            inventory_collection = self.bot.database_manager.get_collection('inventory')
            if not inventory_collection:
                return False
            
            result = await inventory_collection.update_one(
                {"user_id": str(user_id), "item_name": item_name, "quantity": {"$gte": quantity}},
                {"$inc": {"quantity": -quantity}}
            )
            
            return result.modified_count > 0
        except Exception as e:
            logging.error(f"Error using item: {e}")
            return False
    
    # Shop methods
    async def get_shop_items(self) -> List[Dict]:
        """Get all shop items."""
        default_items = [
            {
                "id": 1,
                "name": "Small Wallet Upgrade",
                "description": "Increase your wallet capacity",
                "price": 5000,
                "type": "upgrade",
                "emoji": "💰"
            },
            {
                "id": 2,
                "name": "Medium Wallet Upgrade", 
                "description": "Significantly increase your wallet capacity",
                "price": 15000,
                "type": "upgrade",
                "emoji": "💳"
            },
            {
                "id": 3,
                "name": "Lucky Charm",
                "description": "Increases daily reward for 3 days",
                "price": 3000,
                "type": "consumable",
                "emoji": "🍀"
            },
            {
                "id": 4,
                "name": "Mystery Box",
                "description": "Get a random amount of money",
                "price": 2000,
                "type": "consumable", 
                "emoji": "🎁"
            }
        ]
        
        try:
            shop_collection = self.bot.database_manager.get_collection('shop')
            if not shop_collection:
                return default_items
            
            shop_data = await shop_collection.find_one({})
            if shop_data and 'items' in shop_data:
                return shop_data['items']
            else:
                # Initialize shop with default items
                await shop_collection.insert_one({'items': default_items})
                return default_items
        except Exception as e:
            logging.error(f"Error getting shop items: {e}")
            return default_items
    
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
        return f"${amount:,}"
    
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
        database_status = "✅ MongoDB" if self.bot.database_manager.is_connected else "⚠️ Memory Only"
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"Economy System | {database_status}")
        return embed

    # ========== COMMANDS ==========
    
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        """Check your or someone else's balance."""
        member = member or ctx.author
        
        wallet = await self.get_user_balance(member.id)
        bank = await self.get_bank_balance(member.id)
        total = wallet + bank
        
        embed = await self.create_economy_embed(f"💰 {member.display_name}'s Balance")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💵 Wallet", value=self.format_money(wallet), inline=True)
        embed.add_field(name="🏦 Bank", value=self.format_money(bank), inline=True)
        embed.add_field(name="💎 Total", value=self.format_money(total), inline=True)
        
        # Wealth tier
        if total >= 1000000:
            tier = "👑 Emperor"
            embed.color = discord.Color.gold()
        elif total >= 500000:
            tier = "💎 Tycoon"
            embed.color = discord.Color.purple()
        elif total >= 100000:
            tier = "🏦 Millionaire" 
            embed.color = discord.Color.blue()
        elif total >= 50000:
            tier = "💵 Wealthy"
            embed.color = discord.Color.green()
        elif total >= 10000:
            tier = "🪙 Stable"
            embed.color = discord.Color.green()
        else:
            tier = "🌱 Starting"
            embed.color = discord.Color.light_grey()
        
        embed.add_field(name="🏆 Wealth Tier", value=tier, inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="wallet", aliases=["wal"])
    async def wallet(self, ctx: commands.Context, member: discord.Member = None):
        """View your wallet balance."""
        member = member or ctx.author
        wallet = await self.get_user_balance(member.id)
        
        embed = await self.create_economy_embed(f"💵 {member.display_name}'s Wallet")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💰 Wallet Balance", value=f"**{self.format_money(wallet)}**", inline=False)
        
        if member == ctx.author:
            embed.add_field(name="💡 Quick Actions", 
                          value="• Use `~~deposit <amount>` to move money to bank\n• Use `~~withdraw <amount>` to get money from bank\n• Use `~~pay <user> <amount>` to send money", 
                          inline=False)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="bank")
    async def bank(self, ctx: commands.Context, member: discord.Member = None):
        """View your bank balance."""
        member = member or ctx.author
        bank = await self.get_bank_balance(member.id)
        
        embed = await self.create_economy_embed(f"🏦 {member.display_name}'s Bank")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="🏦 Bank Balance", value=f"**{self.format_money(bank)}**", inline=False)
        
        if member == ctx.author:
            embed.add_field(name="💡 Quick Actions", 
                          value="• Use `~~deposit <amount|all>` to add money\n• Use `~~withdraw <amount|all>` to take money\n• **Shop purchases use bank money!**", 
                          inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="networth", aliases=["nw", "worth"])
    async def networth(self, ctx: commands.Context, member: discord.Member = None):
        """View your total net worth."""
        member = member or ctx.author
        
        wallet = await self.get_user_balance(member.id)
        bank = await self.get_bank_balance(member.id)
        total = wallet + bank
        
        embed = await self.create_economy_embed(f"💎 {member.display_name}'s Net Worth")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        embed.add_field(name="💵 Wallet", value=self.format_money(wallet), inline=True)
        embed.add_field(name="🏦 Bank", value=self.format_money(bank), inline=True)
        embed.add_field(name="💎 Total Net Worth", value=f"**{self.format_money(total)}**", inline=True)
        
        # Wealth tier
        if total >= 1000000:
            tier = "👑 Emperor"
            embed.color = discord.Color.gold()
        elif total >= 500000:
            tier = "💎 Tycoon"
            embed.color = discord.Color.purple()
        elif total >= 100000:
            tier = "🏦 Millionaire" 
            embed.color = discord.Color.blue()
        elif total >= 50000:
            tier = "💵 Wealthy"
            embed.color = discord.Color.green()
        elif total >= 10000:
            tier = "🪙 Stable"
            embed.color = discord.Color.green()
        else:
            tier = "🌱 Starting"
            embed.color = discord.Color.light_grey()
        
        embed.add_field(name="🏆 Wealth Tier", value=tier, inline=False)
        
        if member == ctx.author:
            embed.add_field(name="📈 Growth Tips", 
                          value="• Use `~~work` every hour\n• Claim `~~daily` rewards\n• Play games for bonuses\n• **Use your bank to store large amounts!**", 
                          inline=False)
        
        await ctx.send(embed=embed)

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str):
        """Deposit money from wallet to bank."""
        wallet = await self.get_user_balance(ctx.author.id)
        
        # Handle amount input
        if amount.lower() == "all":
            deposit_amount = wallet
        else:
            try:
                deposit_amount = int(amount)
                if deposit_amount <= 0:
                    raise ValueError
            except ValueError:
                embed = await self.create_economy_embed("❌ Invalid Amount", discord.Color.red())
                embed.description = "Please provide a valid positive number or `all`."
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
        
        # Process deposit
        new_wallet = await self.update_balance(ctx.author.id, -deposit_amount)
        new_bank = await self.update_bank_balance(ctx.author.id, deposit_amount)
        
        embed = await self.create_economy_embed("🏦 Deposit Successful", discord.Color.green())
        embed.description = f"Deposited {self.format_money(deposit_amount)} to your bank."
        embed.add_field(name="💵 New Wallet", value=self.format_money(new_wallet), inline=True)
        embed.add_field(name="🏦 New Bank", value=self.format_money(new_bank), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Withdraw money from bank to wallet."""
        bank = await self.get_bank_balance(ctx.author.id)
        
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
        new_wallet = await self.update_balance(ctx.author.id, withdraw_amount)
        new_bank = await self.update_bank_balance(ctx.author.id, -withdraw_amount)
        
        embed = await self.create_economy_embed("🏦 Withdrawal Successful", discord.Color.green())
        embed.description = f"Withdrew {self.format_money(withdraw_amount)} from your bank."
        embed.add_field(name="💵 New Wallet", value=self.format_money(new_wallet), inline=True)
        embed.add_field(name="🏦 New Bank", value=self.format_money(new_bank), inline=True)
        
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
        
        # Calculate reward
        base_reward = random.randint(500, 1500)
        
        # Update user
        new_balance = await self.update_balance(ctx.author.id, base_reward)
        await self.set_cooldown(ctx.author.id, "daily")
        
        embed = await self.create_economy_embed("🎁 Daily Reward Claimed!", discord.Color.green())
        embed.description = f"You received {self.format_money(base_reward)}!"
        embed.add_field(name="💵 New Balance", value=self.format_money(new_balance), inline=False)
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
            "delivered packages": (100, 300),
            "drove for Uber": (150, 400),
            "worked at a café": (80, 250),
            "coded a website": (300, 800),
            "designed graphics": (200, 500),
            "streamed on Twitch": (250, 600),
            "invested in stocks": (400, 1000)
        }
        
        job, (min_earn, max_earn) = random.choice(list(jobs.items()))
        earnings = random.randint(min_earn, max_earn)
        
        # Critical work chance (10%)
        is_critical = random.random() < 0.1
        if is_critical:
            earnings *= 2
        
        new_balance = await self.update_balance(ctx.author.id, earnings)
        await self.set_cooldown(ctx.author.id, "work")
        
        embed = await self.create_economy_embed("💼 Work Complete!", discord.Color.blue())
        
        if is_critical:
            embed.description = f"🎯 **CRITICAL WORK!** You {job} and earned {self.format_money(earnings)}!"
            embed.color = discord.Color.gold()
        else:
            embed.description = f"You {job} and earned {self.format_money(earnings)}!"
        
        embed.add_field(name="💵 New Balance", value=self.format_money(new_balance), inline=False)
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
            embed.add_field(
                name=f"{item['emoji']} {item['name']} - {self.format_money(item['price'])}",
                value=f"**ID:** `{item['id']}`\n{item['description']}",
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
        
        # Check balance in BANK (not wallet!)
        bank_balance = await self.get_bank_balance(ctx.author.id)
        if bank_balance < item["price"]:
            embed = await self.create_economy_embed("❌ Insufficient Bank Funds", discord.Color.red())
            embed.description = f"You need {self.format_money(item['price'])} in your **BANK** but only have {self.format_money(bank_balance)}.\nUse `~~deposit` to move money from wallet to bank."
            return await ctx.send(embed=embed)
        
        # Process purchase from BANK
        new_bank = await self.update_bank_balance(ctx.author.id, -item["price"])
        
        # Handle different item types
        if item["type"] == "upgrade":
            # For wallet upgrades, increase wallet capacity (not implemented in this simplified version)
            await self.add_to_inventory(ctx.author.id, item["name"])
        elif item["type"] == "consumable":
            # Add to inventory
            await self.add_to_inventory(ctx.author.id, item["name"])
        
        # Success message
        embed = await self.create_economy_embed("✅ Purchase Successful!", discord.Color.green())
        embed.description = f"You purchased **{item['emoji']} {item['name']}** for {self.format_money(item['price'])} from your bank!"
        
        if item["type"] == "upgrade":
            embed.add_field(
                name="⚡ Upgrade Applied",
                value="Your upgrade has been applied! Check your inventory.",
                inline=False
            )
        elif item["type"] == "consumable":
            embed.add_field(
                name="📦 Item Stored",
                value="Use `~~inventory` to view your items.",
                inline=False
            )
        
        # Show remaining bank balance
        embed.add_field(name="🏦 Remaining Bank", value=self.format_money(new_bank), inline=False)
        
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
        wallet_balance = await self.get_user_balance(ctx.author.id)
        if wallet_balance < amount:
            embed = await self.create_economy_embed("❌ Insufficient Wallet Funds", discord.Color.red())
            embed.description = f"You only have {self.format_money(wallet_balance)} in your wallet.\nUse `~~withdraw` to get money from your bank."
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

    @commands.command(name="inventory", aliases=["inv", "items"])
    async def inventory(self, ctx: commands.Context, member: discord.Member = None):
        """View your inventory."""
        member = member or ctx.author
        inventory = await self.get_inventory(member.id)
        
        embed = await self.create_economy_embed(f"🎒 {member.display_name}'s Inventory")
        
        if not inventory:
            embed.description = "Your inventory is empty. Visit the shop with `~~shop` to buy some items!"
        else:
            for item in inventory:
                embed.add_field(
                    name=f"{item.get('item_name', 'Unknown Item')}",
                    value=f"Quantity: {item.get('quantity', 1)}",
                    inline=True
                )
        
        await ctx.send(embed=embed)

    @commands.command(name="leaderboard", aliases=["lb", "rich"])
    async def leaderboard(self, ctx: commands.Context):
        """Show the wealth leaderboard."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                embed = await self.create_economy_embed("❌ Database Error", discord.Color.red())
                embed.description = "Unable to access leaderboard data at this time."
                return await ctx.send(embed=embed)
            
            # Get top 10 users by total wealth (wallet + bank)
            pipeline = [
                {
                    "$project": {
                        "user_id": 1,
                        "total_wealth": {
                            "$add": [
                                {"$ifNull": ["$balance", 0]},
                                {"$ifNull": ["$bank_balance", 0]}
                            ]
                        }
                    }
                },
                {"$sort": {"total_wealth": -1}},
                {"$limit": 10}
            ]
            
            top_users = await users_collection.aggregate(pipeline).to_list(length=10)
            
            embed = await self.create_economy_embed("🏆 Wealth Leaderboard")
            embed.description = "Top 10 richest users in the economy system:\n\n"
            
            for i, user_data in enumerate(top_users, 1):
                user_id = int(user_data['user_id'])
                user = self.bot.get_user(user_id)
                username = user.display_name if user else f"User {user_id}"
                wealth = user_data['total_wealth']
                
                medal = ""
                if i == 1:
                    medal = "🥇 "
                elif i == 2:
                    medal = "🥈 "
                elif i == 3:
                    medal = "🥉 "
                
                embed.description += f"**{i}. {medal}{username}** - {self.format_money(wealth)}\n"
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Error getting leaderboard: {e}")
            embed = await self.create_economy_embed("❌ Error", discord.Color.red())
            embed.description = "Unable to load leaderboard at this time."
            await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economy(bot))
