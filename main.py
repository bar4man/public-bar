import os
import logging
from dotenv import load_dotenv
import sys
import asyncio

# Load environment variables first
load_dotenv()

# Configure logging before any other imports
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Import discord
try:
    import discord
    from discord.ext import commands
    logger.info("✅ Using discord.py")
except ImportError as e:
    logger.error(f"❌ Discord import failed: {e}")
    sys.exit(1)

import json
from datetime import datetime, timezone, timedelta
import traceback

# Environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
MONGODB_URI = os.getenv("MONGODB_URI")
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "true").lower() == "true"

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# ---------------- Manager Classes ----------------
class ConfigManager:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.default_config = {
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
            logger.info(f"Created new config file: {self.filename}")
    
    async def load(self):
        """Load configuration from file."""
        try:
            with open(self.filename, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return self.default_config.copy()
    
    async def save(self, data):
        """Save configuration to file."""
        try:
            with open(self.filename, "w") as f:
                json.dump(data, f, indent=2)
            return True
        except Exception:
            return False

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
                logger.error("MONGODB_URI not found")
                return False
                
            import pymongo
            import certifi
            
            self.client = pymongo.MongoClient(self.uri, tlsCAFile=certifi.where())
            self.db = self.client.get_database('discord_bot')
            
            # Test connection
            self.client.admin.command('ping')
            self.is_connected = True
            
            # Setup basic indexes
            self.db.users.create_index("user_id", unique=True)
            self.db.inventory.create_index([("user_id", 1), ("item_id", 1)], unique=True)
            
            logger.info("✅ MongoDB connected")
            return True
            
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            return False
    
    def get_collection(self, name):
        """Get a MongoDB collection."""
        return self.db[name] if self.is_connected else None
    
    async def close(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            self.is_connected = False

# ---------------- Bot Class ----------------
class EconomyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="~~",
            intents=intents,
            help_command=None,
            case_insensitive=True
        )
        self.start_time = datetime.now(timezone.utc)
        self.config_manager = ConfigManager()
        self.database_manager = DatabaseManager()
    
    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"✅ {self.user} is online!")
        logger.info(f"📊 Connected to {len(self.guilds)} guilds")
        
        # Set status
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"{len(self.guilds)} servers | ~~help"
            )
        )
        
        # Start background tasks after bot is ready
        self.update_status.start()

    async def setup_hook(self):
        """Setup hook."""
        logger.info("🔧 Setting up bot...")
        os.makedirs("data", exist_ok=True)
        await self.load_cogs()
    
    async def load_cogs(self):
        """Load all cogs."""
        cogs = ['admin', 'economy']
        loaded = 0
        
        # Connect to database first
        await self.database_manager.connect()
        
        for cog in cogs:
            try:
                await self.load_extension(cog)
                loaded += 1
                logger.info(f"✅ Loaded {cog}")
            except Exception as e:
                logger.error(f"❌ Failed to load {cog}: {e}")
        
        logger.info(f"📊 Loaded {loaded}/{len(cogs)} cogs")
    
    @tasks.loop(minutes=5)
    async def update_status(self):
        """Update bot status."""
        try:
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=f"{len(self.guilds)} servers | ~~help"
                )
            )
            logger.debug("✅ Status updated")
        except Exception as e:
            logger.error(f"Status update failed: {e}")

# Create bot instance
bot = EconomyBot()

# ---------------- Error Handling ----------------
@bot.event
async def on_command_error(ctx, error):
    """Global error handler."""
    if isinstance(error, commands.CommandNotFound):
        return
    
    error_embed = discord.Embed(color=discord.Color.red())
    
    if isinstance(error, commands.MissingRequiredArgument):
        error_embed.title = "❌ Missing Argument"
        error_embed.description = f"Missing: `{error.param.name}`"
    elif isinstance(error, commands.BadArgument):
        error_embed.title = "❌ Invalid Argument"
        error_embed.description = "Check your arguments"
    elif isinstance(error, commands.MissingPermissions):
        error_embed.title = "❌ Missing Permissions"
        error_embed.description = "You don't have permission"
    elif isinstance(error, commands.CommandOnCooldown):
        error_embed.title = "⏰ Cooldown"
        error_embed.description = f"Wait {error.retry_after:.1f}s"
        error_embed.color = discord.Color.orange()
    else:
        logger.error(f"Unexpected error: {error}")
        error_embed.title = "❌ Error"
        error_embed.description = "Something went wrong"
    
    try:
        await ctx.send(embed=error_embed, delete_after=10)
    except discord.Forbidden:
        pass

@bot.event
async def on_message(message):
    """Message handler."""
    if message.author.bot:
        return
    await bot.process_commands(message)

# ---------------- Commands ----------------
@bot.command()
async def ping(ctx):
    """Check bot latency."""
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"Latency: {latency}ms",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def reload(ctx):
    """Reload cogs."""
    msg = await ctx.send("🔄 Reloading...")
    
    # Reload cogs
    reloaded = 0
    for cog in list(bot.extensions.keys()):
        try:
            await bot.reload_extension(cog)
            reloaded += 1
        except Exception as e:
            logger.error(f"Failed to reload {cog}: {e}")
    
    await msg.edit(content=f"✅ Reloaded {reloaded} cogs")

@bot.command()
async def status(ctx):
    """Check bot status."""
    embed = discord.Embed(title="🤖 Bot Status", color=discord.Color.blue())
    
    embed.add_field(name="Uptime", value=str(datetime.now(timezone.utc) - bot.start_time).split('.')[0], inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="Database", value="✅" if bot.database_manager.is_connected else "❌", inline=True)
    embed.add_field(name="Cogs", value=len(bot.cogs), inline=True)
    
    await ctx.send(embed=embed)

@bot.command()
async def help(ctx):
    """Show help."""
    embed = discord.Embed(
        title="🤖 Economy Bot Help",
        description="Available commands:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="💰 Economy",
        value="• `~~balance` - Check balance\n• `~~daily` - Daily reward\n• `~~work` - Earn money\n• `~~crime` - Risky earnings\n• `~~shop` - Browse items\n• `~~buy <id>` - Buy item\n• `~~inventory` - View items\n• `~~leaderboard` - Top users",
        inline=False
    )
    
    embed.add_field(
        name="🔧 Utility", 
        value="• `~~ping` - Check latency\n• `~~status` - Bot status\n• `~~help` - This message",
        inline=False
    )
    
    if ctx.author.guild_permissions.administrator:
        embed.add_field(
            name="🛡️ Admin",
            value="• `~~reload` - Reload cogs\n• `~~economygive @user amount` - Give money\n• `~~economytake @user amount` - Take money",
            inline=False
        )
    
    await ctx.send(embed=embed)

# ---------------- Web Server ----------------
def start_web_server():
    """Start web server for keep-alive."""
    try:
        from flask import Flask
        import threading
        
        app = Flask(__name__)
        
        @app.route('/')
        def home():
            return "Bot is running!"
        
        @app.route('/health')
        def health():
            return "OK"
        
        @app.route('/ping')
        def ping():
            return "pong"
        
        def run():
            import waitress
            waitress.serve(app, host='0.0.0.0', port=8080)
        
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        logger.info("✅ Web server started on port 8080")
        return True
    except Exception as e:
        logger.error(f"❌ Web server failed: {e}")
        return False

# ---------------- Main ----------------
if __name__ == "__main__":
    try:
        logger.info("🚀 Starting bot...")
        
        if not TOKEN:
            logger.critical("❌ No DISCORD_TOKEN")
            sys.exit(1)
        
        # Start web server
        if KEEP_ALIVE:
            start_web_server()
        
        # Run bot - this will start the event loop
        bot.run(TOKEN)
        
    except KeyboardInterrupt:
        logger.info("⏹️ Bot stopped")
        if bot.database_manager.is_connected:
            bot.database_manager.close()
    except Exception as e:
        logger.critical(f"❌ Bot failed: {e}")
        traceback.print_exc()
        sys.exit(1)
