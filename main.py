import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
import webserver
import aiohttp
import sys
import traceback

# Add the current directory to Python path for Render
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

# ---------------- Setup ----------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "true").lower() == "true"

# Enhanced logging setup
def setup_logging():
    """Setup comprehensive logging with both file and console output."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # File handler
    file_handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="a")
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(levelname)s - %(name)s - %(message)s'
    ))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

setup_logging()

# Discord intents with validation
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# ---------------- Manager Classes ----------------
class ConfigManager:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.lock = asyncio.Lock()
        self.default_config = {
            "auto_delete": {},
            "autorole": None,
            "grape_gifs": [],
            "member_numbers": {},
            "prefix": "~~",
            "allowed_channels": [],
            "mod_log_channel": None
        }
        self._ensure_config_exists()
    
    def _ensure_config_exists(self):
        """Create config file with default structure if it doesn't exist."""
        if not os.path.exists(self.filename):
            with open(self.filename, "w") as f:
                json.dump(self.default_config, f, indent=2)
            logging.info(f"Created new config file: {self.filename}")
    
    async def load(self):
        """Load configuration from file with error recovery."""
        async with self.lock:
            try:
                with open(self.filename, "r") as f:
                    config = json.load(f)
                return {**self.default_config, **config}
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.error(f"Config load error: {e}, using defaults")
                return self.default_config.copy()
    
    async def save(self, data):
        """Save configuration to file with validation."""
        async with self.lock:
            try:
                validated_data = {**self.default_config, **data}
                with open(self.filename, "w") as f:
                    json.dump(validated_data, f, indent=2, ensure_ascii=False)
                logging.info("Config saved successfully")
                return True
            except Exception as e:
                logging.error(f"Config save error: {e}")
                return False

class MessageFilter:
    def __init__(self):
        self.spam_tracker = {}
        self.SPAM_TIMEFRAME = 5
        self.SPAM_LIMIT = 5
        self._last_cleanup = datetime.now(timezone.utc).timestamp()
    
    def _load_filter_data(self):
        """Load filter data from file with caching."""
        try:
            with open("filter.json", "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"blocked_links": [], "blocked_words": []}
    
    def is_spam(self, user_id):
        """Check if user is spamming with automatic cleanup."""
        now = datetime.now(timezone.utc).timestamp()
        
        # Cleanup old entries every 5 minutes
        if now - self._last_cleanup > 300:
            self._cleanup_old_entries()
            self._last_cleanup = now
        
        self.spam_tracker.setdefault(user_id, [])
        self.spam_tracker[user_id] = [
            t for t in self.spam_tracker[user_id] 
            if now - t < self.SPAM_TIMEFRAME
        ]
        
        self.spam_tracker[user_id].append(now)
        return len(self.spam_tracker[user_id]) > self.SPAM_LIMIT
    
    def _cleanup_old_entries(self):
        """Clean up old spam tracker entries to prevent memory leaks."""
        now = datetime.now(timezone.utc).timestamp()
        cutoff = now - 300
        self.spam_tracker = {
            user_id: timestamps 
            for user_id, timestamps in self.spam_tracker.items()
            if any(t > cutoff for t in timestamps)
        }
    
    def contains_blocked_content(self, content):
        """Check if message contains blocked words or links."""
        filter_data = self._load_filter_data()
        content_lower = content.lower()
        
        for word in filter_data.get("blocked_words", []):
            if word and word.lower() in content_lower:
                return True, "word"
        
        for link in filter_data.get("blocked_links", []):
            if link and link.lower() in content_lower:
                return True, "link"
        
        return False, None

class DatabaseManager:
    def __init__(self):
        self.uri = MONGODB_URI
        self.client = None
        self.db = None
        self.is_connected = False
        
    async def connect(self):
        """Connect to MongoDB database."""
        try:
            if not self.uri:
                logging.error("MONGODB_URI not found in environment variables")
                return False
                
            import pymongo
            from pymongo import MongoClient
            import certifi
            
            self.client = MongoClient(self.uri, tlsCAFile=certifi.where())
            self.db = self.client.get_database('discord_bot')
            
            # Test connection
            self.client.admin.command('ping')
            self.is_connected = True
            
            # Setup indexes
            await self._setup_indexes()
            
            logging.info("✅ Successfully connected to MongoDB")
            return True
            
        except Exception as e:
            logging.error(f"❌ MongoDB connection failed: {e}")
            self.is_connected = False
            return False
    
    async def _setup_indexes(self):
        """Create necessary database indexes."""
        try:
            # Users collection indexes
            self.db.users.create_index("user_id", unique=True)
            
            # Market collections
            self.db.market_positions.create_index([("user_id", 1), ("commodity", 1)])
            self.db.market_trades.create_index([("user_id", 1), ("timestamp", -1)])
            self.db.market_portfolios.create_index("user_id", unique=True)
            self.db.price_history.create_index([("symbol", 1), ("timestamp", -1)])
            self.db.market_state.create_index("_id", unique=True)
            self.db.economic_state.create_index("_id", unique=True)
            self.db.market_events.create_index([("active", 1), ("expires_at", 1)])
            
            logging.info("✅ Database indexes created")
        except Exception as e:
            logging.error(f"❌ Failed to create indexes: {e}")
    
    def get_collection(self, name):
        """Get a MongoDB collection."""
        if not self.is_connected:
            logging.error("Database not connected")
            return None
        return self.db[name]
    
    async def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            self.is_connected = False
            logging.info("Database connection closed")

# ---------------- Create Manager Instances ----------------
config_manager = ConfigManager()
message_filter = MessageFilter()
database_manager = DatabaseManager()

# ---------------- Bot Class ----------------
class Bot(commands.Bot):
    """Custom bot class with additional utilities."""
    
    def __init__(self):
        super().__init__(
            command_prefix="~~",
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.start_time = datetime.now(timezone.utc)
        self.config_manager = config_manager
        self.message_filter = message_filter
        self.database_manager = database_manager
    
    async def on_ready(self):
        """Enhanced on_ready with more detailed startup info."""
        logging.info(f"✅ Bot is ready as {self.user} (ID: {self.user.id})")
        logging.info(f"📊 Connected to {len(self.guilds)} guild(s)")
        
        # Set bot status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="~~help | Economy & Markets"
            ),
            status=discord.Status.online
        )

# Create bot instance
bot = Bot()

# Register bot with web server for status monitoring
try:
    import webserver
    webserver.set_bot(bot)
    logging.info("✅ Bot registered with web server for status monitoring")
except Exception as e:
    logging.warning(f"❌ Could not register bot with web server: {e}")

# ---------------- Error Handling ----------------
@bot.event
async def on_command_error(ctx, error):
    """Global error handler with enhanced error reporting."""
    if hasattr(ctx.command, 'on_error'):
        return
    
    error_embed = discord.Embed(color=discord.Color.red())
    
    if isinstance(error, commands.MissingRequiredArgument):
        error_embed.title = "❌ Missing Argument"
        error_embed.description = f"Missing required argument: `{error.param.name}`"
        error_embed.set_footer(text=f"Use ~~help {ctx.command} for more info")
        
    elif isinstance(error, commands.BadArgument):
        error_embed.title = "❌ Invalid Argument"
        error_embed.description = "Invalid argument type or member not found."
        
    elif isinstance(error, commands.CommandNotFound):
        return
        
    elif isinstance(error, commands.MissingPermissions):
        error_embed.title = "❌ Missing Permissions"
        error_embed.description = "You do not have permission to use this command."
        
    elif isinstance(error, commands.CommandOnCooldown):
        error_embed.title = "⏰ Cooldown Active"
        error_embed.description = f"Please wait **{error.retry_after:.1f}s** before using this command again."
        error_embed.color = discord.Color.orange()
        
    elif isinstance(error, commands.BotMissingPermissions):
        error_embed.title = "❌ Bot Missing Permissions"
        error_embed.description = f"I need these permissions: {', '.join(error.missing_permissions)}"
        
    elif isinstance(error, commands.NoPrivateMessage):
        error_embed.title = "❌ Guild Only Command"
        error_embed.description = "This command can only be used in servers."
        
    else:
        logging.error(f"Unexpected error in command {ctx.command}: {error}", exc_info=error)
        error_embed.title = "⚠️ Unexpected Error"
        error_embed.description = "An unexpected error occurred. The issue has been logged."
        error_embed.color = discord.Color.orange()
    
    try:
        await ctx.send(embed=error_embed, delete_after=10)
    except discord.Forbidden:
        pass

# ---------------- Message Filtering ----------------
@bot.event
async def on_message(message):
    """Enhanced message handler with better filtering."""
    if message.author.bot or isinstance(message.channel, discord.DMChannel):
        return
    
    try:
        if bot.message_filter.is_spam(message.author.id):
            await message.delete()
            warning_msg = await message.channel.send(
                f"{message.author.mention}, slow down! ⏰ (Rate limit: {bot.message_filter.SPAM_LIMIT} messages per {bot.message_filter.SPAM_TIMEFRAME}s)",
                delete_after=5
            )
            return
        
        is_blocked, block_type = bot.message_filter.contains_blocked_content(message.content)
        if is_blocked:
            await message.delete()
            if block_type == "word":
                msg = f"{message.author.mention}, that word is not allowed! 🚫"
            else:
                msg = f"{message.author.mention}, that link is not allowed! 🔗"
            await message.channel.send(msg, delete_after=5)
            return
            
    except discord.Forbidden:
        logging.warning(f"Missing permissions in channel {message.channel.id}")
    except Exception as e:
        logging.warning(f"Message filter error: {e}")
    
    await bot.process_commands(message)

# ---------------- Enhanced Cog Loader ----------------
async def load_cogs():
    """Enhanced cog loader that handles nested folders properly."""
    loaded_count = 0
    
    # Connect to database first
    db_connected = await bot.database_manager.connect()
    if not db_connected:
        logging.error("❌ Database connection failed - some features may not work")
    
    # Load cogs from different locations
    cog_paths = [
        "cogs",           # Main cogs folder
        "markets",        # Markets system
    ]
    
    for cog_path in cog_paths:
        if os.path.exists(cog_path):
            logging.info(f"📁 Loading cogs from: {cog_path}")
            for filename in os.listdir(cog_path):
                if filename.endswith('.py') and filename != '__init__.py':
                    cog_name = f"{cog_path}.{filename[:-3]}"
                    try:
                        await bot.load_extension(cog_name)
                        loaded_count += 1
                        logging.info(f"✅ Loaded cog: {cog_name}")
                    except Exception as e:
                        logging.error(f"❌ Failed to load cog {cog_name}: {e}")
                        # Print full traceback for debugging
                        traceback.print_exc()
        else:
            logging.warning(f"⚠️ Cog path not found: {cog_path}")
    
    # Sync application commands
    try:
        synced = await bot.tree.sync()
        logging.info(f"✅ Synced {len(synced)} application command(s)")
    except Exception as e:
        logging.error(f"❌ Failed to sync commands: {e}")
    
    logging.info(f"📊 Total cogs loaded: {loaded_count}")

async def reload_cogs():
    """Reload all cogs."""
    reloaded_count = 0
    
    # Get all loaded cogs
    for cog_name in list(bot.extensions.keys()):
        try:
            await bot.reload_extension(cog_name)
            reloaded_count += 1
            logging.info(f"🔄 Reloaded cog: {cog_name}")
        except Exception as e:
            logging.error(f"❌ Failed to reload cog {cog_name}: {e}")
    
    logging.info(f"📊 Cogs reloaded: {reloaded_count}")

# ---------------- Bot Events ----------------
@bot.event
async def setup_hook():
    """Enhanced setup hook with proper cog loading."""
    logging.info("🔧 Starting bot setup...")
    
    # Create necessary directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("cogs", exist_ok=True)
    os.makedirs("markets", exist_ok=True)
    os.makedirs("markets/config", exist_ok=True)
    logging.info("📁 Directories initialized")
    
    await load_cogs()
    logging.info("✅ Setup hook completed")

@bot.event
async def on_ready():
    """Enhanced on_ready with more detailed startup info."""
    logging.info(f"✅ Bot is ready as {bot.user} (ID: {bot.user.id})")
    logging.info(f"📊 Connected to {len(bot.guilds)} guild(s)")
    
    # Log guild names
    for guild in bot.guilds:
        logging.info(f"   - {guild.name} (ID: {guild.id}, Members: {guild.member_count})")
    
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="~~help | Economy & Markets"
        ),
        status=discord.Status.online
    )

# ---------------- Utility Commands ----------------
@bot.command(name="ping", brief="Check bot latency")
async def ping(ctx):
    """Check the bot's latency and response time."""
    start_time = ctx.message.created_at
    msg = await ctx.send("🏓 Pinging...")
    end_time = msg.created_at
    
    bot_latency = round(bot.latency * 1000)
    response_time = round((end_time - start_time).total_seconds() * 1000)
    
    embed = discord.Embed(
        title="🏓 Pong!",
        color=discord.Color.green()
    )
    embed.add_field(name="Bot Latency", value=f"{bot_latency}ms", inline=True)
    embed.add_field(name="Response Time", value=f"{response_time}ms", inline=True)
    
    await msg.edit(content=None, embed=embed)

@bot.command(name="reload", brief="Reload all cogs")
@commands.has_permissions(administrator=True)
async def reload(ctx):
    """Reload all cogs (Admin only)."""
    msg = await ctx.send("🔄 Reloading cogs...")
    await reload_cogs()
    await msg.edit(content="✅ All cogs reloaded successfully!")

@bot.command(name="status")
async def status_command(ctx: commands.Context):
    """Check bot and database status."""
    embed = discord.Embed(title="🤖 Bot Status", color=discord.Color.blue())
    
    # Bot info
    embed.add_field(
        name="Bot Status",
        value=f"✅ Online since <t:{int(bot.start_time.timestamp())}:R>",
        inline=False
    )
    
    # Latency
    embed.add_field(
        name="Latency",
        value=f"🏓 {round(bot.latency * 1000)}ms",
        inline=True
    )
    
    # Guild count
    embed.add_field(
        name="Servers",
        value=f"📊 {len(bot.guilds)}",
        inline=True
    )
    
    # Database status
    db_status = "✅ Connected" if bot.database_manager.is_connected else "❌ Disconnected"
    embed.add_field(
        name="Database",
        value=db_status,
        inline=True
    )
    
    # Cogs loaded
    cog_count = len(bot.cogs)
    embed.add_field(
        name="Cogs Loaded",
        value=f"⚙️ {cog_count}",
        inline=True
    )
    
    # Uptime
    uptime = datetime.now(timezone.utc) - bot.start_time
    embed.add_field(
        name="Uptime",
        value=f"⏰ {str(uptime).split('.')[0]}",
        inline=True
    )
    
    await ctx.send(embed=embed)

# ---------------- Keep Alive ----------------
if KEEP_ALIVE:
    try:
        import webserver
        success = webserver.keep_alive()
        if success:
            logging.info("✅ Keep-alive web server initialized")
        else:
            logging.warning("❌ Keep-alive web server failed to start")
    except Exception as e:
        logging.error(f"❌ Keep-alive setup failed: {e}")

# ---------------- Run Bot ----------------
if __name__ == "__main__":
    try:
        logging.info("🚀 Starting bot...")
        logging.info(f"📁 Current directory: {os.getcwd()}")
        logging.info(f"📁 Python path: {sys.path}")
        
        if not TOKEN:
            logging.critical("❌ DISCORD_TOKEN environment variable not set!")
            exit(1)
            
        bot.run(TOKEN)
    except KeyboardInterrupt:
        logging.info("⏹️ Bot stopped by user")
        if bot.database_manager.is_connected:
            bot.database_manager.close()
    except discord.LoginFailure:
        logging.critical("❌ Invalid Discord token")
    except Exception as e:
        logging.critical(f"❌ Failed to start bot: {e}")
        traceback.print_exc()
