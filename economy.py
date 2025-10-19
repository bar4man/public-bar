import discord
from discord.ext import commands, tasks
import json
import logging
import random
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger('discord_bot')

class Economy(commands.Cog):
    """Economy system with banking, jobs, gambling, and market"""
    
    def __init__(self, bot):
        self.bot = bot
        self.economy_file = "economy.json"
        self.market_file = "market.json"
        self.jobs_file = "jobs.json"
        self.cooldowns_file = "cooldowns.json"
        
        # Initialize files if they don't exist
        self._init_files()
        
        # Start background tasks
        self.market_update.start()
        self.random_news.start()
    
    def _init_files(self):
        """Initialize all economy-related files"""
        # Economy file
        try:
            with open(self.economy_file, 'r') as f:
                json.load(f)
        except:
            with open(self.economy_file, 'w') as f:
                json.dump({}, f, indent=2)
        
        # Market file
        try:
            with open(self.market_file, 'r') as f:
                json.load(f)
        except:
            default_market = {
                "stocks": {
                    "TECH": {"name": "Tech Corp", "price": 100, "history": []},
                    "FOOD": {"name": "Food Industries", "price": 50, "history": []},
                    "ENERGY": {"name": "Energy Solutions", "price": 75, "history": []},
                    "GAME": {"name": "Gaming Corp", "price": 120, "history": []},
                    "AUTO": {"name": "Auto Motors", "price": 90, "history": []}
                },
                "news": [],
                "last_update": datetime.utcnow().isoformat()
            }
            with open(self.market_file, 'w') as f:
                json.dump(default_market, f, indent=2)
        
        # Jobs file
        try:
            with open(self.jobs_file, 'r') as f:
                json.load(f)
        except:
            default_jobs = {
                "available_jobs": [
                    {"name": "cashier", "pay": 50, "required_balance": 0, "cooldown": 3600, "emoji": "🏪"},
                    {"name": "delivery", "pay": 100, "required_balance": 500, "cooldown": 3600, "emoji": "🚚"},
                    {"name": "chef", "pay": 150, "required_balance": 1000, "cooldown": 5400, "emoji": "👨‍🍳"},
                    {"name": "manager", "pay": 250, "required_balance": 2500, "cooldown": 7200, "emoji": "💼"},
                    {"name": "engineer", "pay": 400, "required_balance": 5000, "cooldown": 10800, "emoji": "⚙️"},
                    {"name": "ceo", "pay": 750, "required_balance": 10000, "cooldown": 14400, "emoji": "👔"}
                ]
            }
            with open(self.jobs_file, 'w') as f:
                json.dump(default_jobs, f, indent=2)
        
        # Cooldowns file
        try:
            with open(self.cooldowns_file, 'r') as f:
                json.load(f)
        except:
            with open(self.cooldowns_file, 'w') as f:
                json.dump({}, f, indent=2)
    
    def load_json(self, filepath):
        """Load JSON data"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filepath}: {e}")
            return {}
    
    def save_json(self, filepath, data):
        """Save JSON data"""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving {filepath}: {e}")
            return False
    
    def get_user_data(self, user_id):
        """Get or create user economy data"""
        economy = self.load_json(self.economy_file)
        user_id = str(user_id)
        
        if user_id not in economy:
            economy[user_id] = {
                "wallet": 0,
                "bank": 0,
                "total_earned": 0,
                "inventory": {},
                "stocks": {},
                "current_job": None
            }
            self.save_json(self.economy_file, economy)
        
        return economy[user_id]
    
    def update_user_data(self, user_id, data):
        """Update user economy data"""
        economy = self.load_json(self.economy_file)
        economy[str(user_id)] = data
        return self.save_json(self.economy_file, economy)
    
    def check_cooldown(self, user_id, command_name):
        """Check if user is on cooldown for a command"""
        cooldowns = self.load_json(self.cooldowns_file)
        user_id = str(user_id)
        
        if user_id not in cooldowns:
            return None
        
        if command_name not in cooldowns[user_id]:
            return None
        
        last_used = datetime.fromisoformat(cooldowns[user_id][command_name])
        now = datetime.utcnow()
        
        return last_used, now
    
    def set_cooldown(self, user_id, command_name, seconds):
        """Set cooldown for a command"""
        cooldowns = self.load_json(self.cooldowns_file)
        user_id = str(user_id)
        
        if user_id not in cooldowns:
            cooldowns[user_id] = {}
        
        cooldowns[user_id][command_name] = datetime.utcnow().isoformat()
        self.save_json(self.cooldowns_file, cooldowns)
    
    def format_time(self, seconds):
        """Format seconds into readable time"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")
        
        return " ".join(parts)
    
    # ==================== BANKING COMMANDS ====================
    
    @commands.command(name='balance')
    async def balance(self, ctx, member: discord.Member = None):
        """Check your or someone's balance
        
        Usage: !balance [@user]
        """
        member = member or ctx.author
        user_data = self.get_user_data(member.id)
        
        wallet = user_data["wallet"]
        bank = user_data["bank"]
        total = wallet + bank
        
        embed = discord.Embed(
            title=f"💰 {member.display_name}'s Balance",
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💵 Wallet", value=f"{wallet:,}£", inline=True)
        embed.add_field(name="🏦 Bank", value=f"{bank:,}£", inline=True)
        embed.add_field(name="💎 Total", value=f"{total:,}£", inline=True)
        
        if user_data.get("current_job"):
            embed.add_field(name="💼 Current Job", value=user_data["current_job"].title(), inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='deposit')
    async def deposit(self, ctx, amount: str):
        """Deposit money to bank
        
        Usage: !deposit <amount|all>
        """
        user_data = self.get_user_data(ctx.author.id)
        wallet = user_data["wallet"]
        
        if amount.lower() == "all":
            amount = wallet
        else:
            try:
                amount = int(amount)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please provide a valid number or use `all`.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if wallet < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{wallet:,}£** in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        user_data["wallet"] -= amount
        user_data["bank"] += amount
        
        if self.update_user_data(ctx.author.id, user_data):
            embed = discord.Embed(
                title="🏦 Deposit Successful",
                description=f"Deposited **{amount:,}£** to your bank.",
                color=discord.Color.green()
            )
            embed.add_field(name="💵 New Wallet", value=f"{user_data['wallet']:,}£", inline=True)
            embed.add_field(name="🏦 New Bank", value=f"{user_data['bank']:,}£", inline=True)
            await ctx.send(embed=embed)
    
    @commands.command(name='withdraw')
    async def withdraw(self, ctx, amount: str):
        """Withdraw money from bank
        
        Usage: !withdraw <amount|all>
        """
        user_data = self.get_user_data(ctx.author.id)
        bank = user_data["bank"]
        
        if amount.lower() == "all":
            amount = bank
        else:
            try:
                amount = int(amount)
            except ValueError:
                embed = discord.Embed(
                    title="❌ Invalid Amount",
                    description="Please provide a valid number or use `all`.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if bank < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{bank:,}£** in your bank.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        user_data["wallet"] += amount
        user_data["bank"] -= amount
        
        if self.update_user_data(ctx.author.id, user_data):
            embed = discord.Embed(
                title="🏦 Withdrawal Successful",
                description=f"Withdrew **{amount:,}£** from your bank.",
                color=discord.Color.green()
            )
            embed.add_field(name="💵 New Wallet", value=f"{user_data['wallet']:,}£", inline=True)
            embed.add_field(name="🏦 New Bank", value=f"{user_data['bank']:,}£", inline=True)
            await ctx.send(embed=embed)
    
    @commands.command(name='pay')
    async def pay(self, ctx, member: discord.Member, amount: int):
        """Pay another user
        
        Usage: !pay @user <amount>
        """
        if member == ctx.author:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You cannot pay yourself!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if member.bot:
            embed = discord.Embed(
                title="❌ Invalid Action",
                description="You cannot pay bots!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        sender_data = self.get_user_data(ctx.author.id)
        
        if sender_data["wallet"] < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{sender_data['wallet']:,}£** in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        receiver_data = self.get_user_data(member.id)
        
        sender_data["wallet"] -= amount
        receiver_data["wallet"] += amount
        
        self.update_user_data(ctx.author.id, sender_data)
        self.update_user_data(member.id, receiver_data)
        
        embed = discord.Embed(
            title="💸 Payment Successful",
            description=f"{ctx.author.mention} paid **{amount:,}£** to {member.mention}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Transaction ID: {ctx.message.id}")
        
        await ctx.send(embed=embed)
        logger.info(f"{ctx.author} paid {amount}£ to {member}")
    
    # ==================== JOB COMMANDS ====================
    
    @commands.command(name='jobs')
    async def jobs(self, ctx):
        """View available jobs
        
        Usage: !jobs
        """
        jobs_data = self.load_json(self.jobs_file)
        user_data = self.get_user_data(ctx.author.id)
        total_balance = user_data["wallet"] + user_data["bank"]
        
        embed = discord.Embed(
            title="💼 Available Jobs",
            description="Work to earn money! Higher paying jobs require balance.",
            color=discord.Color.blue()
        )
        
        for job in jobs_data["available_jobs"]:
            emoji = job.get("emoji", "💼")
            name = job["name"].title()
            pay = job["pay"]
            required = job["required_balance"]
            cooldown_hours = job["cooldown"] / 3600
            
            can_work = total_balance >= required
            status = "✅ Available" if can_work else f"🔒 Requires {required:,}£"
            
            field_value = f"**Pay:** {pay:,}£\n**Required Balance:** {required:,}£\n**Cooldown:** {cooldown_hours:.1f}h\n**Status:** {status}"
            
            embed.add_field(
                name=f"{emoji} {name}",
                value=field_value,
                inline=True
            )
        
        embed.add_field(
            name="💰 Your Balance",
            value=f"{total_balance:,}£",
            inline=False
        )
        embed.set_footer(text="Use !work <job> to start working!")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='work')
    async def work(self, ctx, job_name: str = None):
        """Work at a job to earn money
        
        Usage: !work <jobname>
        Example: !work cashier
        """
        if not job_name:
            embed = discord.Embed(
                title="❌ Missing Job Name",
                description="Please specify a job! Use `!jobs` to see available jobs.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        job_name = job_name.lower()
        jobs_data = self.load_json(self.jobs_file)
        
        # Find the job
        job = None
        for j in jobs_data["available_jobs"]:
            if j["name"] == job_name:
                job = j
                break
        
        if not job:
            embed = discord.Embed(
                title="❌ Job Not Found",
                description=f"Job `{job_name}` doesn't exist. Use `!jobs` to see available jobs.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        user_data = self.get_user_data(ctx.author.id)
        total_balance = user_data["wallet"] + user_data["bank"]
        
        # Check balance requirement
        if total_balance < job["required_balance"]:
            embed = discord.Embed(
                title="❌ Insufficient Balance",
                description=f"You need **{job['required_balance']:,}£** total balance to work as a {job_name}.\nYou have **{total_balance:,}£**.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check cooldown
        cooldown_data = self.check_cooldown(ctx.author.id, f"work_{job_name}")
        if cooldown_data:
            last_used, now = cooldown_data
            time_passed = (now - last_used).total_seconds()
            
            if time_passed < job["cooldown"]:
                remaining = job["cooldown"] - time_passed
                embed = discord.Embed(
                    title="⏰ On Cooldown",
                    description=f"You can work as a {job_name} again in **{self.format_time(remaining)}**",
                    color=discord.Color.orange()
                )
                return await ctx.send(embed=embed)
        
        # Work and earn money
        earnings = job["pay"]
        user_data["wallet"] += earnings
        user_data["total_earned"] += earnings
        user_data["current_job"] = job_name
        
        self.update_user_data(ctx.author.id, user_data)
        self.set_cooldown(ctx.author.id, f"work_{job_name}", job["cooldown"])
        
        work_messages = [
            f"completed your shift as a {job_name}",
            f"worked hard as a {job_name}",
            f"finished your duties as a {job_name}",
            f"successfully completed your work as a {job_name}"
        ]
        
        embed = discord.Embed(
            title=f"{job.get('emoji', '💼')} Work Complete!",
            description=f"You {random.choice(work_messages)} and earned **{earnings:,}£**!",
            color=discord.Color.green()
        )
        embed.add_field(name="💵 New Wallet", value=f"{user_data['wallet']:,}£", inline=True)
        embed.add_field(name="📊 Total Earned", value=f"{user_data['total_earned']:,}£", inline=True)
        embed.set_footer(text=f"Cooldown: {job['cooldown']/3600:.1f}h")
        
        await ctx.send(embed=embed)
        logger.info(f"{ctx.author} worked as {job_name} and earned {earnings}£")
    
    # ==================== GAMBLING COMMANDS ====================
    
    @commands.command(name='coinflip')
    async def coinflip(self, ctx, choice: str, amount: int):
        """Flip a coin and gamble money
        
        Usage: !coinflip <heads|tails> <amount>
        """
        choice = choice.lower()
        
        if choice not in ["heads", "tails"]:
            embed = discord.Embed(
                title="❌ Invalid Choice",
                description="Choose either `heads` or `tails`.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        user_data = self.get_user_data(ctx.author.id)
        
        if user_data["wallet"] < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{user_data['wallet']:,}£** in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        result = random.choice(["heads", "tails"])
        won = result == choice
        
        if won:
            user_data["wallet"] += amount
            user_data["total_earned"] += amount
            color = discord.Color.green()
            title = "🎉 You Won!"
            description = f"The coin landed on **{result}**!\nYou won **{amount:,}£**!"
        else:
            user_data["wallet"] -= amount
            color = discord.Color.red()
            title = "💔 You Lost!"
            description = f"The coin landed on **{result}**.\nYou lost **{amount:,}£**."
        
        self.update_user_data(ctx.author.id, user_data)
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.add_field(name="💵 New Balance", value=f"{user_data['wallet']:,}£", inline=True)
        
        await ctx.send(embed=embed)
    
    @commands.command(name='dice')
    async def dice(self, ctx, amount: int):
        """Roll a dice and gamble
        
        Usage: !dice <amount>
        Win 2x on 5-6, lose on 1-4
        """
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        user_data = self.get_user_data(ctx.author.id)
        
        if user_data["wallet"] < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{user_data['wallet']:,}£** in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        roll = random.randint(1, 6)
        won = roll >= 5
        
        if won:
            winnings = amount * 2
            user_data["wallet"] += winnings
            user_data["total_earned"] += winnings
            color = discord.Color.green()
            title = "🎲 You Won!"
            description = f"You rolled a **{roll}**!\nYou won **{winnings:,}£**!"
        else:
            user_data["wallet"] -= amount
            color = discord.Color.red()
            title = "🎲 You Lost!"
            description = f"You rolled a **{roll}**.\nYou lost **{amount:,}£**."
        
        self.update_user_data(ctx.author.id, user_data)
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.add_field(name="💵 New Balance", value=f"{user_data['wallet']:,}£", inline=True)
        embed.set_footer(text="Roll 5-6 to win 2x your bet!")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='slots')
    async def slots(self, ctx, amount: int):
        """Play slot machine
        
        Usage: !slots <amount>
        """
        if amount <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        user_data = self.get_user_data(ctx.author.id)
        
        if user_data["wallet"] < amount:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You only have **{user_data['wallet']:,}£** in your wallet.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        emojis = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣"]
        slot1 = random.choice(emojis)
        slot2 = random.choice(emojis)
        slot3 = random.choice(emojis)
        
        # Calculate winnings
        if slot1 == slot2 == slot3:
            if slot1 == "💎":
                multiplier = 10
            elif slot1 == "7️⃣":
                multiplier = 5
            else:
                multiplier = 3
            winnings = amount * multiplier
            user_data["wallet"] += winnings
            user_data["total_earned"] += winnings
            color = discord.Color.gold()
            title = "🎰 JACKPOT!"
            description = f"{slot1} {slot2} {slot3}\n\nYou won **{winnings:,}£** ({multiplier}x)!"
        elif slot1 == slot2 or slot2 == slot3:
            winnings = amount
            user_data["wallet"] += winnings
            user_data["total_earned"] += winnings
            color = discord.Color.green()
            title = "🎰 Small Win!"
            description = f"{slot1} {slot2} {slot3}\n\nYou won **{winnings:,}£** (2x)!"
        else:
            user_data["wallet"] -= amount
            color = discord.Color.red()
            title = "🎰 You Lost!"
            description = f"{slot1} {slot2} {slot3}\n\nYou lost **{amount:,}£**."
        
        self.update_user_data(ctx.author.id, user_data)
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.add_field(name="💵 New Balance", value=f"{user_data['wallet']:,}£", inline=True)
        
        await ctx.send(embed=embed)
    
    # ==================== MARKET COMMANDS ====================
    
    @commands.command(name='market')
    async def market(self, ctx):
        """View the stock market
        
        Usage: !market
        """
        market = self.load_json(self.market_file)
        
        embed = discord.Embed(
            title="📊 Stock Market",
            description="Current stock prices and trends",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        for symbol, stock in market["stocks"].items():
            price = stock["price"]
            name = stock["name"]
            
            # Calculate change if history exists
            change_text = ""
            if stock.get("history") and len(stock["history"]) > 1:
                old_price = stock["history"][-2]["price"]
                change = price - old_price
                change_percent = (change / old_price * 100) if old_price > 0 else 0
                
                if change > 0:
                    change_text = f"📈 +{change:,}£ ({change_percent:+.2f}%)"
                elif change < 0:
                    change_text = f"📉 {change:,}£ ({change_percent:.2f}%)"
                else:
                    change_text = "➡️ No change"
            
            field_value = f"**Price:** {price:,}£\n{change_text}" if change_text else f"**Price:** {price:,}£"
            
            embed.add_field(
                name=f"{symbol} - {name}",
                value=field_value,
                inline=True
            )
        
        embed.set_footer(text="Use !buy <symbol> <shares> to buy stocks")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='buy')
    async def buy(self, ctx, symbol: str, shares: int):
        """Buy stock shares
        
        Usage: !buy <symbol> <shares>
        Example: !buy TECH 10
        """
        symbol = symbol.upper()
        
        if shares <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Number of shares must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        market = self.load_json(self.market_file)
        
        if symbol not in market["stocks"]:
            embed = discord.Embed(
                title="❌ Stock Not Found",
                description=f"Stock symbol `{symbol}` doesn't exist. Use `!market` to see available stocks.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        stock = market["stocks"][symbol]
        total_cost = stock["price"] * shares
        
        user_data = self.get_user_data(ctx.author.id)
        
        if user_data["wallet"] < total_cost:
            embed = discord.Embed(
                title="❌ Insufficient Funds",
                description=f"You need **{total_cost:,}£** to buy {shares} shares.\nYou have **{user_data['wallet']:,}£**.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Process purchase
        user_data["wallet"] -= total_cost
        
        if symbol not in user_data["stocks"]:
            user_data["stocks"][symbol] = 0
        
        user_data["stocks"][symbol] += shares
        
        self.update_user_data(ctx.author.id, user_data)
        
        embed = discord.Embed(
            title="📈 Purchase Successful",
            description=f"Bought **{shares}** shares of **{stock['name']}** ({symbol})",
            color=discord.Color.green()
        )
        embed.add_field(name="💵 Cost", value=f"{total_cost:,}£", inline=True)
        embed.add_field(name="💵 New Wallet", value=f"{user_data['wallet']:,}£", inline=True)
        embed.add_field(name="📊 Total Shares", value=f"{user_data['stocks'][symbol]}", inline=True)
        
        await ctx.send(embed=embed)
        logger.info(f"{ctx.author} bought {shares} shares of {symbol} for {total_cost}£")
    
    @commands.command(name='sell')
    async def sell(self, ctx, symbol: str, shares: int):
        """Sell stock shares
        
        Usage: !sell <symbol> <shares>
        Example: !sell TECH 5
        """
        symbol = symbol.upper()
        
        if shares <= 0:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Number of shares must be greater than 0.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        market = self.load_json(self.market_file)
        
        if symbol not in market["stocks"]:
            embed = discord.Embed(
                title="❌ Stock Not Found",
                description=f"Stock symbol `{symbol}` doesn't exist.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        user_data = self.get_user_data(ctx.author.id)
        
        if symbol not in user_data["stocks"] or user_data["stocks"][symbol] < shares:
            owned = user_data["stocks"].get(symbol, 0)
            embed = discord.Embed(
                title="❌ Insufficient Shares",
                description=f"You don't have enough shares of {symbol}.\nYou own: **{owned}** shares",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        stock = market["stocks"][symbol]
        total_value = stock["price"] * shares
        
        # Process sale
        user_data["wallet"] += total_value
        user_data["stocks"][symbol] -= shares
        user_data["total_earned"] += total_value
        
        # Remove stock from inventory if 0 shares
        if user_data["stocks"][symbol] == 0:
            del user_data["stocks"][symbol]
        
        self.update_user_data(ctx.author.id, user_data)
        
        embed = discord.Embed(
            title="📉 Sale Successful",
            description=f"Sold **{shares}** shares of **{stock['name']}** ({symbol})",
            color=discord.Color.green()
        )
        embed.add_field(name="💰 Earned", value=f"{total_value:,}£", inline=True)
        embed.add_field(name="💵 New Wallet", value=f"{user_data['wallet']:,}£", inline=True)
        embed.add_field(name="📊 Remaining Shares", value=f"{user_data['stocks'].get(symbol, 0)}", inline=True)
        
        await ctx.send(embed=embed)
        logger.info(f"{ctx.author} sold {shares} shares of {symbol} for {total_value}£")
    
    @commands.command(name='portfolio')
    async def portfolio(self, ctx, member: discord.Member = None):
        """View your stock portfolio
        
        Usage: !portfolio [@user]
        """
        member = member or ctx.author
        user_data = self.get_user_data(member.id)
        market = self.load_json(self.market_file)
        
        if not user_data["stocks"]:
            embed = discord.Embed(
                title="📊 Portfolio",
                description=f"{member.display_name} doesn't own any stocks yet.",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"📊 {member.display_name}'s Portfolio",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        total_value = 0
        
        for symbol, shares in user_data["stocks"].items():
            if symbol in market["stocks"]:
                stock = market["stocks"][symbol]
                current_price = stock["price"]
                value = current_price * shares
                total_value += value
                
                embed.add_field(
                    name=f"{symbol} - {stock['name']}",
                    value=f"**Shares:** {shares}\n**Price:** {current_price:,}£\n**Value:** {value:,}£",
                    inline=True
                )
        
        embed.add_field(
            name="💎 Total Portfolio Value",
            value=f"{total_value:,}£",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='leaderboard')
    async def leaderboard(self, ctx):
        """View the wealth leaderboard
        
        Usage: !leaderboard
        """
        economy = self.load_json(self.economy_file)
        market = self.load_json(self.market_file)
        
        # Calculate net worth for all users
        user_wealth = []
        
        for user_id, data in economy.items():
            wallet = data.get("wallet", 0)
            bank = data.get("bank", 0)
            
            # Calculate stock value
            stock_value = 0
            for symbol, shares in data.get("stocks", {}).items():
                if symbol in market["stocks"]:
                    stock_value += market["stocks"][symbol]["price"] * shares
            
            net_worth = wallet + bank + stock_value
            
            if net_worth > 0:
                user_wealth.append((int(user_id), net_worth))
        
        if not user_wealth:
            embed = discord.Embed(
                title="📊 Wealth Leaderboard",
                description="No users have any wealth yet!",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        # Sort by net worth
        user_wealth.sort(key=lambda x: x[1], reverse=True)
        
        embed = discord.Embed(
            title="📊 Wealth Leaderboard",
            description="Top richest users on the server",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        
        medals = ["🥇", "🥈", "🥉"]
        
        for i, (user_id, net_worth) in enumerate(user_wealth[:10]):
            user = self.bot.get_user(user_id)
            username = user.display_name if user else f"User {user_id}"
            
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            
            embed.add_field(
                name=f"{medal} {username}",
                value=f"💰 {net_worth:,}£",
                inline=False
            )
        
        embed.set_footer(text=f"Total users: {len(user_wealth)}")
        
        await ctx.send(embed=embed)
    
    # ==================== BACKGROUND TASKS ====================
    
    @tasks.loop(hours=1)
    async def market_update(self):
        """Update stock prices every hour"""
        try:
            market = self.load_json(self.market_file)
            
            for symbol, stock in market["stocks"].items():
                old_price = stock["price"]
                
                # Random price change between -15% to +15%
                change_percent = random.uniform(-0.15, 0.15)
                new_price = int(old_price * (1 + change_percent))
                
                # Ensure price doesn't go below 10
                new_price = max(10, new_price)
                
                stock["price"] = new_price
                
                # Add to history
                if "history" not in stock:
                    stock["history"] = []
                
                stock["history"].append({
                    "price": new_price,
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                # Keep only last 100 entries
                if len(stock["history"]) > 100:
                    stock["history"] = stock["history"][-100:]
            
            market["last_update"] = datetime.utcnow().isoformat()
            self.save_json(self.market_file, market)
            
            logger.info("Market prices updated")
            
        except Exception as e:
            logger.error(f"Error updating market: {e}")
    
    @market_update.before_loop
    async def before_market_update(self):
        """Wait for bot to be ready before starting market updates"""
        await self.bot.wait_until_ready()
    
    @tasks.loop(hours=3)
    async def random_news(self):
        """Send random market news every 3 hours"""
        try:
            await self.bot.wait_until_ready()
            
            # Find a channel to send news (first text channel with "economy" or "market" in name)
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    if any(word in channel.name.lower() for word in ["economy", "market", "stock", "trade"]):
                        await self.send_market_news(channel)
                        break
                        
        except Exception as e:
            logger.error(f"Error sending random news: {e}")
    
    async def send_market_news(self, channel):
        """Send market news to a channel"""
        try:
            market = self.load_json(self.market_file)
            stocks = list(market["stocks"].keys())
            
            if not stocks:
                return
            
            # Generate random news
            news_templates = [
                "{stock} surges as new product launches!",
                "{stock} drops amid market uncertainty.",
                "Analysts predict growth for {stock} this quarter.",
                "{stock} announces record profits!",
                "Market volatility affects {stock} prices.",
                "{stock} expands to new markets!",
                "Investors show strong interest in {stock}.",
                "{stock} faces regulatory challenges.",
                "Breakthrough technology boosts {stock}!",
                "{stock} partners with major corporation."
            ]
            
            stock_symbol = random.choice(stocks)
            stock_name = market["stocks"][stock_symbol]["name"]
            stock_price = market["stocks"][stock_symbol]["price"]
            
            news_text = random.choice(news_templates).format(stock=stock_name)
            
            embed = discord.Embed(
                title="📰 Market News",
                description=news_text,
                color=discord.Color.gold(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(
                name=f"{stock_symbol} - {stock_name}",
                value=f"Current Price: **{stock_price:,}£**",
                inline=False
            )
            embed.set_footer(text="Market Update")
            
            await channel.send(embed=embed)
            
            # Save to news history
            if "news" not in market:
                market["news"] = []
            
            market["news"].append({
                "message": news_text,
                "stock": stock_symbol,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            # Keep only last 50 news items
            if len(market["news"]) > 50:
                market["news"] = market["news"][-50:]
            
            self.save_json(self.market_file, market)
            
            logger.info(f"Market news sent to #{channel.name}")
            
        except Exception as e:
            logger.error(f"Error sending market news: {e}")
    
    @random_news.before_loop
    async def before_random_news(self):
        """Wait for bot to be ready before sending news"""
        await self.bot.wait_until_ready()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.market_update.cancel()
        self.random_news.cancel()

async def setup(bot):
    """Load the Economy cog"""
    await bot.add_cog(Economy(bot))
    logger.info("Economy cog loaded")
