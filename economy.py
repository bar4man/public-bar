import discord
from discord.ext import commands, tasks
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
import math

class Economy(commands.Cog):
    """Enhanced economy system with MongoDB integration."""
    
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns: Dict[int, Dict[str, datetime]] = {}
        self.work_jobs: List[str] = [
            "worked as a software developer", "delivered food", "streamed on Twitch",
            "sold artwork", "wrote a blog post", "did freelance work",
            "performed at a concert", "sold items online", "invested in stocks",
            "won a gaming tournament", "created a YouTube video", "did consulting work",
            "sold crafts", "performed magic tricks", "wrote code for a client",
            "designed a website", "gave music lessons", "walked dogs",
            "babysat", "tutored students", "did yard work", "cleaned houses",
            "drove for Uber", "sold baked goods", "performed in a play"
        ]
        
        self.crime_activities: List[Tuple[str, int, int]] = [
            ("pickpocket someone", 50, 80),
            ("hack a small website", 100, 200),
            ("sell fake items", 150, 300),
            ("rob a convenience store", 300, 600),
            ("hack a bank (very risky!)", 500, 1000),
            ("steal a car", 400, 800),
            ("sell confidential information", 600, 1200),
            ("pull off a heist", 800, 1600),
            ("hack a government server (extremely risky!)", 1000, 2000)
        ]
        
        self.shop_items: List[Dict] = [
            {"id": 1, "name": "🍎 Apple", "description": "A healthy snack", "price": 50, "type": "consumable"},
            {"id": 2, "name": "💧 Water Bottle", "description": "Stay hydrated", "price": 30, "type": "consumable"},
            {"id": 3, "name": "🍔 Burger", "description": "A delicious meal", "price": 100, "type": "consumable"},
            {"id": 4, "name": "🎣 Fishing Rod", "description": "For fishing activities", "price": 500, "type": "tool"},
            {"id": 5, "name": "⛏️ Pickaxe", "description": "For mining activities", "price": 800, "type": "tool"},
            {"id": 6, "name": "💎 Diamond", "description": "A rare gemstone", "price": 2000, "type": "collectible"},
            {"id": 7, "name": "🏆 Trophy", "description": "Show off your achievements", "price": 5000, "type": "collectible"},
            {"id": 8, "name": "🎮 Gaming Console", "description": "For entertainment", "price": 3000, "type": "collectible"},
            {"id": 9, "name": "📱 Smartphone", "description": "Modern communication device", "price": 2500, "type": "collectible"},
            {"id": 10, "name": "💼 Briefcase", "description": "Carry your items in style", "price": 1500, "type": "collectible"}
        ]
        
        # Start background tasks
        self.cleanup_cooldowns.start()
    
    def cog_unload(self):
        """Cleanup when cog is unloaded."""
        self.cleanup_cooldowns.cancel()
    
    # -------------------- Utility Methods --------------------
    async def get_user_data(self, user_id: int) -> Dict:
        """Get user data from MongoDB."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                return self._get_default_user_data(user_id)
            
            user_data = await users_collection.find_one({"user_id": str(user_id)})
            if not user_data:
                return self._get_default_user_data(user_id)
            
            return user_data
        except Exception as e:
            logging.error(f"Error getting user data for {user_id}: {e}")
            return self._get_default_user_data(user_id)
    
    def _get_default_user_data(self, user_id: int) -> Dict:
        """Get default user data structure."""
        return {
            "user_id": str(user_id),
            "balance": 1000,
            "bank_balance": 0,
            "last_daily": None,
            "last_work": None,
            "last_crime": None,
            "total_earned": 0,
            "inventory": []
        }
    
    async def update_user_data(self, user_id: int, update_data: Dict):
        """Update user data in MongoDB."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                return False
            
            await users_collection.update_one(
                {"user_id": str(user_id)},
                {"$set": update_data},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error updating user data for {user_id}: {e}")
            return False
    
    async def add_to_inventory(self, user_id: int, item_id: int, quantity: int = 1):
        """Add item to user's inventory."""
        try:
            inventory_collection = self.bot.database_manager.get_collection('inventory')
            if not inventory_collection:
                return False
            
            await inventory_collection.update_one(
                {"user_id": str(user_id), "item_id": item_id},
                {"$inc": {"quantity": quantity}},
                upsert=True
            )
            return True
        except Exception as e:
            logging.error(f"Error adding to inventory for {user_id}: {e}")
            return False
    
    async def get_inventory(self, user_id: int) -> List[Dict]:
        """Get user's inventory."""
        try:
            inventory_collection = self.bot.database_manager.get_collection('inventory')
            if not inventory_collection:
                return []
            
            cursor = inventory_collection.find({"user_id": str(user_id)})
            inventory = await cursor.to_list(length=None)
            return inventory
        except Exception as e:
            logging.error(f"Error getting inventory for {user_id}: {e}")
            return []
    
    def format_money(self, amount: int) -> str:
        """Format money with commas."""
        return f"${amount:,}"
    
    def is_on_cooldown(self, user_id: int, action: str, cooldown_seconds: int) -> Tuple[bool, Optional[timedelta]]:
        """Check if user is on cooldown for an action."""
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
        
        last_used = self.cooldowns[user_id].get(action)
        if not last_used:
            return False, None
        
        time_passed = datetime.now(timezone.utc) - last_used
        if time_passed.total_seconds() < cooldown_seconds:
            time_left = timedelta(seconds=cooldown_seconds) - time_passed
            return True, time_left
        
        return False, None
    
    def set_cooldown(self, user_id: int, action: str):
        """Set cooldown for an action."""
        if user_id not in self.cooldowns:
            self.cooldowns[user_id] = {}
        
        self.cooldowns[user_id][action] = datetime.now(timezone.utc)
    
    # -------------------- Background Tasks --------------------
    @tasks.loop(hours=1)
    async def cleanup_cooldowns(self):
        """Clean up old cooldowns to prevent memory leaks."""
        current_time = datetime.now(timezone.utc)
        expired_users = []
        
        for user_id, cooldowns in self.cooldowns.items():
            # Remove expired cooldowns (older than 24 hours)
            expired_actions = []
            for action, last_used in cooldowns.items():
                if (current_time - last_used).total_seconds() > 86400:  # 24 hours
                    expired_actions.append(action)
            
            for action in expired_actions:
                del cooldowns[action]
            
            # Remove user if no cooldowns left
            if not cooldowns:
                expired_users.append(user_id)
        
        for user_id in expired_users:
            del self.cooldowns[user_id]
    
    # -------------------- Balance Commands --------------------
    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        """Check your or another user's balance."""
        member = member or ctx.author
        user_data = await self.get_user_data(member.id)
        
        embed = discord.Embed(
            title=f"💰 {member.display_name}'s Balance",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="💵 Wallet",
            value=self.format_money(user_data.get('balance', 1000)),
            inline=True
        )
        embed.add_field(
            name="🏦 Bank",
            value=self.format_money(user_data.get('bank_balance', 0)),
            inline=True
        )
        embed.add_field(
            name="📈 Net Worth",
            value=self.format_money(user_data.get('balance', 1000) + user_data.get('bank_balance', 0)),
            inline=True
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="dailies", aliases=["daily"])
    async def daily(self, ctx: commands.Context):
        """Claim your daily reward."""
        user_id = ctx.author.id
        
        # Check cooldown
        on_cooldown, time_left = self.is_on_cooldown(user_id, "daily", 86400)  # 24 hours
        if on_cooldown:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            
            embed = discord.Embed(
                title="⏰ Daily Cooldown",
                description=f"You can claim your daily reward again in **{hours}h {minutes}m**.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        # Calculate daily reward (base + bonus)
        base_reward = 500
        streak_bonus = random.randint(50, 200)
        total_reward = base_reward + streak_bonus
        
        # Update user balance
        user_data = await self.get_user_data(user_id)
        new_balance = user_data.get('balance', 1000) + total_reward
        total_earned = user_data.get('total_earned', 0) + total_reward
        
        success = await self.update_user_data(user_id, {
            "balance": new_balance,
            "total_earned": total_earned,
            "last_daily": datetime.now(timezone.utc).isoformat()
        })
        
        if not success:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to process daily reward. Please try again.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Set cooldown
        self.set_cooldown(user_id, "daily")
        
        embed = discord.Embed(
            title="🎁 Daily Reward Claimed!",
            description=f"You received **{self.format_money(total_reward)}**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Base Reward", value=self.format_money(base_reward), inline=True)
        embed.add_field(name="Bonus", value=self.format_money(streak_bonus), inline=True)
        embed.add_field(name="New Balance", value=self.format_money(new_balance), inline=True)
        
        await ctx.send(embed=embed)
    
    # -------------------- Work System --------------------
    @commands.command(name="work")
    async def work(self, ctx: commands.Context):
        """Work to earn money with a cooldown."""
        user_id = ctx.author.id
        
        # Check cooldown (1 hour)
        on_cooldown, time_left = self.is_on_cooldown(user_id, "work", 3600)
        if on_cooldown:
            minutes = int(time_left.total_seconds() // 60)
            seconds = int(time_left.total_seconds() % 60)
            
            embed = discord.Embed(
                title="⏰ Work Cooldown",
                description=f"You can work again in **{minutes}m {seconds}s**.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        # Calculate work reward
        job = random.choice(self.work_jobs)
        base_earnings = random.randint(100, 300)
        bonus = random.randint(0, 100)  # Random bonus
        total_earnings = base_earnings + bonus
        
        # Update user balance
        user_data = await self.get_user_data(user_id)
        new_balance = user_data.get('balance', 1000) + total_earnings
        total_earned = user_data.get('total_earned', 0) + total_earnings
        
        success = await self.update_user_data(user_id, {
            "balance": new_balance,
            "total_earned": total_earned,
            "last_work": datetime.now(timezone.utc).isoformat()
        })
        
        if not success:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to process work payment. Please try again.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Set cooldown
        self.set_cooldown(user_id, "work")
        
        embed = discord.Embed(
            title="💼 Work Completed",
            description=f"You {job} and earned **{self.format_money(total_earnings)}**!",
            color=discord.Color.blue()
        )
        embed.add_field(name="Base Earnings", value=self.format_money(base_earnings), inline=True)
        if bonus > 0:
            embed.add_field(name="Bonus", value=self.format_money(bonus), inline=True)
        embed.add_field(name="New Balance", value=self.format_money(new_balance), inline=True)
        
        await ctx.send(embed=embed)
    
    # -------------------- Crime System --------------------
    @commands.command(name="crime")
    async def crime(self, ctx: commands.Context):
        """Commit a crime for high rewards but with risk of failure."""
        user_id = ctx.author.id
        
        # Check cooldown (2 hours)
        on_cooldown, time_left = self.is_on_cooldown(user_id, "crime", 7200)
        if on_cooldown:
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            
            embed = discord.Embed(
                title="⏰ Crime Cooldown",
                description=f"You can attempt another crime in **{hours}h {minutes}m**.",
                color=discord.Color.orange()
            )
            return await ctx.send(embed=embed)
        
        # Choose a crime
        crime_name, min_reward, max_reward = random.choice(self.crime_activities)
        success_chance = random.randint(1, 100)
        
        # Determine outcome
        if success_chance <= 60:  # 60% success rate
            # Success
            earnings = random.randint(min_reward, max_reward)
            
            user_data = await self.get_user_data(user_id)
            new_balance = user_data.get('balance', 1000) + earnings
            total_earned = user_data.get('total_earned', 0) + earnings
            
            success = await self.update_user_data(user_id, {
                "balance": new_balance,
                "total_earned": total_earned,
                "last_crime": datetime.now(timezone.utc).isoformat()
            })
            
            if not success:
                embed = discord.Embed(
                    title="❌ Error",
                    description="Failed to process crime earnings. Please try again.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
            embed = discord.Embed(
                title="🎭 Crime Successful!",
                description=f"You successfully {crime_name} and earned **{self.format_money(earnings)}**!",
                color=discord.Color.green()
            )
            embed.add_field(name="New Balance", value=self.format_money(new_balance), inline=True)
            
        else:
            # Failure - fine the user
            fine = random.randint(50, 200)
            
            user_data = await self.get_user_data(user_id)
            current_balance = user_data.get('balance', 1000)
            actual_fine = min(fine, current_balance)  # Can't go negative
            
            if actual_fine > 0:
                new_balance = current_balance - actual_fine
                await self.update_user_data(user_id, {
                    "balance": new_balance,
                    "last_crime": datetime.now(timezone.utc).isoformat()
                })
            
            embed = discord.Embed(
                title="🚨 Crime Failed!",
                description=f"You got caught trying to {crime_name}!",
                color=discord.Color.red()
            )
            if actual_fine > 0:
                embed.add_field(name="Fine Paid", value=self.format_money(actual_fine), inline=True)
                embed.add_field(name="New Balance", value=self.format_money(new_balance), inline=True)
            else:
                embed.add_field(name="Lucky Break", value="You had no money to fine!", inline=True)
        
        # Set cooldown regardless of outcome
        self.set_cooldown(user_id, "crime")
        
        await ctx.send(embed=embed)
    
    # -------------------- Banking System --------------------
    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str = None):
        """Deposit money into your bank account."""
        user_id = ctx.author.id
        user_data = await self.get_user_data(user_id)
        
        wallet = user_data.get('balance', 1000)
        bank = user_data.get('bank_balance', 0)
        
        if amount is None:
            embed = discord.Embed(
                title="❌ Specify Amount",
                description="Please specify an amount to deposit. Use `all` to deposit everything.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if amount.lower() == "all":
            deposit_amount = wallet
        elif amount.lower() == "half":
            deposit_amount = wallet // 2
        else:
            try:
                deposit_amount = int(amount)
                if deposit_amount <= 0:
                    embed = discord.Embed(
                        title="❌ Invalid Amount",
                        description="Amount must be positive.",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please specify a valid number, 'all', or 'half'.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        if deposit_amount > wallet:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have {self.format_money(wallet)} in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if deposit_amount == 0:
            embed = discord.Embed(
                title="❌ Nothing to Deposit",
                description="You have no money in your wallet to deposit.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Update balances
        new_wallet = wallet - deposit_amount
        new_bank = bank + deposit_amount
        
        success = await self.update_user_data(user_id, {
            "balance": new_wallet,
            "bank_balance": new_bank
        })
        
        if not success:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to process deposit. Please try again.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="🏦 Deposit Successful",
            description=f"Deposited **{self.format_money(deposit_amount)}** into your bank account.",
            color=discord.Color.green()
        )
        embed.add_field(name="💵 New Wallet", value=self.format_money(new_wallet), inline=True)
        embed.add_field(name="🏦 New Bank", value=self.format_money(new_bank), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str = None):
        """Withdraw money from your bank account."""
        user_id = ctx.author.id
        user_data = await self.get_user_data(user_id)
        
        wallet = user_data.get('balance', 1000)
        bank = user_data.get('bank_balance', 0)
        
        if amount is None:
            embed = discord.Embed(
                title="❌ Specify Amount",
                description="Please specify an amount to withdraw. Use `all` to withdraw everything.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if amount.lower() == "all":
            withdraw_amount = bank
        elif amount.lower() == "half":
            withdraw_amount = bank // 2
        else:
            try:
                withdraw_amount = int(amount)
                if withdraw_amount <= 0:
                    embed = discord.Embed(
                        title="❌ Invalid Amount",
                        description="Amount must be positive.",
                        color=discord.Color.red()
                    )
                    return await ctx.send(embed=embed)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please specify a valid number, 'all', or 'half'.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        if withdraw_amount > bank:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have {self.format_money(bank)} in your bank.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if withdraw_amount == 0:
            embed = discord.Embed(
                title="❌ Nothing to Withdraw",
                description="You have no money in your bank to withdraw.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Update balances
        new_wallet = wallet + withdraw_amount
        new_bank = bank - withdraw_amount
        
        success = await self.update_user_data(user_id, {
            "balance": new_wallet,
            "bank_balance": new_bank
        })
        
        if not success:
            embed = discord.Embed(
                title="❌ Error",
                description="Failed to process withdrawal. Please try again.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="🏦 Withdrawal Successful",
            description=f"Withdrew **{self.format_money(withdraw_amount)}** from your bank account.",
            color=discord.Color.green()
        )
        embed.add_field(name="💵 New Wallet", value=self.format_money(new_wallet), inline=True)
        embed.add_field(name="🏦 New Bank", value=self.format_money(new_bank), inline=True)
        
        await ctx.send(embed=embed)
    
    # -------------------- Transfer System --------------------
    @commands.command(name="transfer", aliases=["pay"])
    async def transfer(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Transfer money to another user."""
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="You cannot transfer money to yourself.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Target",
                description="You cannot transfer money to bots.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be positive.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Get sender data
        sender_data = await self.get_user_data(ctx.author.id)
        sender_balance = sender_data.get('balance', 1000)
        
        if amount > sender_balance:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have {self.format_money(sender_balance)} in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Get receiver data
        receiver_data = await self.get_user_data(member.id)
        receiver_balance = receiver_data.get('balance', 1000)
        
        # Update balances
        new_sender_balance = sender_balance - amount
        new_receiver_balance = receiver_balance + amount
        
        # Update sender
        success1 = await self.update_user_data(ctx.author.id, {
            "balance": new_sender_balance
        })
        
        # Update receiver
        success2 = await self.update_user_data(member.id, {
            "balance": new_receiver_balance
        })
        
        if not success1 or not success2:
            embed = discord.Embed(
                title="❌ Transfer Failed",
                description="An error occurred during the transfer. Please try again.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="✅ Transfer Successful",
            description=f"You transferred **{self.format_money(amount)}** to {member.mention}.",
            color=discord.Color.green()
        )
        embed.add_field(name="Your New Balance", value=self.format_money(new_sender_balance), inline=True)
        embed.add_field(name=f"{member.display_name}'s Balance", value=self.format_money(new_receiver_balance), inline=True)
        
        await ctx.send(embed=embed)
    
    # -------------------- Shop System --------------------
    @commands.command(name="shop")
    async def shop(self, ctx: commands.Context, page: int = 1):
        """Browse the shop items."""
        items_per_page = 5
        total_pages = math.ceil(len(self.shop_items) / items_per_page)
        
        if page < 1 or page > total_pages:
            embed = discord.Embed(
                title="❌ Invalid Page",
                description=f"Please choose a page between 1 and {total_pages}.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_items = self.shop_items[start_idx:end_idx]
        
        embed = discord.Embed(
            title="🛍️ Shop",
            description="Use `!buy <item_id>` to purchase an item.",
            color=discord.Color.blue()
        )
        
        for item in page_items:
            embed.add_field(
                name=f"{item['name']} (ID: {item['id']}) - {self.format_money(item['price'])}",
                value=f"{item['description']} [{item['type'].title()}]",
                inline=False
            )
        
        embed.set_footer(text=f"Page {page}/{total_pages} • Use !shop <page> to browse more")
        
        await ctx.send(embed=embed)
    
    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, item_id: int = None, quantity: int = 1):
        """Buy an item from the shop."""
        if item_id is None:
            embed = discord.Embed(
                title="❌ Specify Item",
                description="Please specify an item ID to buy. Use `!shop` to see available items.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if quantity <= 0:
            embed = discord.Embed(
                title="❌ Invalid Quantity",
                description="Quantity must be at least 1.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Find the item
        item = next((i for i in self.shop_items if i['id'] == item_id), None)
        if not item:
            embed = discord.Embed(
                title="❌ Item Not Found",
                description=f"No item found with ID {item_id}. Use `!shop` to see available items.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        total_cost = item['price'] * quantity
        
        # Check if user has enough money
        user_data = await self.get_user_data(ctx.author.id)
        user_balance = user_data.get('balance', 1000)
        
        if total_cost > user_balance:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You need {self.format_money(total_cost)} but only have {self.format_money(user_balance)}.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Process purchase
        new_balance = user_balance - total_cost
        
        # Update user balance
        success1 = await self.update_user_data(ctx.author.id, {
            "balance": new_balance
        })
        
        # Add to inventory
        success2 = await self.add_to_inventory(ctx.author.id, item_id, quantity)
        
        if not success1 or not success2:
            embed = discord.Embed(
                title="❌ Purchase Failed",
                description="An error occurred during the purchase. Please try again.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title="✅ Purchase Successful!",
            description=f"You bought {quantity}x {item['name']} for {self.format_money(total_cost)}.",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=self.format_money(new_balance), inline=True)
        embed.add_field(name="Item Type", value=item['type'].title(), inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx: commands.Context, member: discord.Member = None):
        """View your or another user's inventory."""
        member = member or ctx.author
        inventory = await self.get_inventory(member.id)
        
        if not inventory:
            embed = discord.Embed(
                title=f"🎒 {member.display_name}'s Inventory",
                description="No items found. Visit the shop with `!shop` to buy some!",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"🎒 {member.display_name}'s Inventory",
            color=discord.Color.blue()
        )
        
        total_items = 0
        for item_data in inventory:
            item_id = item_data['item_id']
            quantity = item_data['quantity']
            total_items += quantity
            
            # Find item details
            item = next((i for i in self.shop_items if i['id'] == item_id), None)
            if item:
                embed.add_field(
                    name=f"{item['name']} x{quantity}",
                    value=f"ID: {item_id} | Type: {item['type']}",
                    inline=True
                )
        
        embed.set_footer(text=f"Total items: {total_items}")
        embed.set_thumbnail(url=member.display_avatar.url)
        
        await ctx.send(embed=embed)
    
    # -------------------- Leaderboard --------------------
    @commands.command(name="leaderboard", aliases=["lb", "rich"])
    async def leaderboard(self, ctx: commands.Context):
        """Display the wealth leaderboard."""
        try:
            users_collection = self.bot.database_manager.get_collection('users')
            if not users_collection:
                embed = discord.Embed(
                    title="❌ Database Error",
                    description="Database connection not available.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
            
            # Get top 10 users by net worth
            pipeline = [
                {"$addFields": {
                    "net_worth": {"$add": ["$balance", "$bank_balance"]}
                }},
                {"$sort": {"net_worth": -1}},
                {"$limit": 10}
            ]
            
            cursor = users_collection.aggregate(pipeline)
            top_users = await cursor.to_list(length=10)
            
            embed = discord.Embed(
                title="🏆 Wealth Leaderboard",
                color=discord.Color.gold()
            )
            
            if not top_users:
                embed.description = "No users found on the leaderboard yet."
            else:
                description = ""
                for i, user_data in enumerate(top_users, 1):
                    user_id = int(user_data['user_id'])
                    user = self.bot.get_user(user_id)
                    username = user.name if user else f"User {user_id}"
                    net_worth = user_data.get('net_worth', 0)
                    
                    medal = ""
                    if i == 1:
                        medal = "🥇"
                    elif i == 2:
                        medal = "🥈" 
                    elif i == 3:
                        medal = "🥉"
                    else:
                        medal = f"**{i}.**"
                    
                    description += f"{medal} **{username}** - {self.format_money(net_worth)}\n"
                
                embed.description = description
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Error generating leaderboard: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description="An error occurred while generating the leaderboard.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

async def setup(bot):
    """Setup function for the Economy cog."""
    await bot.add_cog(Economy(bot))
