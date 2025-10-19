import discord
from discord.ext import commands
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('discord_bot')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix='!',
    intents=intents,
    help_command=None
)

# Global variables
ADMIN_ROLE = "bot-admin"

# Data file paths
DATA_DIR = "data"
ECONOMY_FILE = f"{DATA_DIR}/economy.json"
MARKET_FILE = f"{DATA_DIR}/market.json"
JOBS_FILE = f"{DATA_DIR}/jobs.json"

# Create data directory if it doesn't exist
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
    logger.info(f"Created {DATA_DIR} directory")

# Initialize data files
def init_data_files():
    """Initialize all JSON data files with default structures"""
    
    # Economy data structure
    if not os.path.exists(ECONOMY_FILE):
        with open(ECONOMY_FILE, 'w') as f:
            json.dump({}, f, indent=2)
        logger.info(f"Created {ECONOMY_FILE}")
    
    # Market data structure
    if not os.path.exists(MARKET_FILE):
        default_market = {
            "stocks": {
                "TECH": {"name": "Tech Corp", "price": 100, "history": []},
                "FOOD": {"name": "Food Industries", "price": 50, "history": []},
                "ENERGY": {"name": "Energy Solutions", "price": 75, "history": []}
            },
            "news": [],
            "last_update": datetime.utcnow().isoformat()
        }
        with open(MARKET_FILE, 'w') as f:
            json.dump(default_market, f, indent=2)
        logger.info(f"Created {MARKET_FILE}")
    
    # Jobs data structure
    if not os.path.exists(JOBS_FILE):
        default_jobs = {
            "available_jobs": [
                {"name": "cashier", "pay": 50, "required_balance": 0, "cooldown": 3600},
                {"name": "delivery", "pay": 100, "required_balance": 500, "cooldown": 3600},
                {"name": "manager", "pay": 200, "required_balance": 2000, "cooldown": 7200},
                {"name": "ceo", "pay": 500, "required_balance": 10000, "cooldown": 14400}
            ]
        }
        with open(JOBS_FILE, 'w') as f:
            json.dump(default_jobs, f, indent=2)
        logger.info(f"Created {JOBS_FILE}")

# Utility functions
def has_admin_role(member):
    """Check if member has bot-admin role"""
    return discord.utils.get(member.roles, name=ADMIN_ROLE) is not None

def load_json(filepath):
    """Load JSON data from file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return {}

def save_json(filepath, data):
    """Save JSON data to file"""
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {filepath}: {e}")
        return False

# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Global error handler"""
    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Argument",
            description=f"Missing required argument: `{error.param.name}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Missing Permissions",
            description="You don't have permission to use this command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    
    else:
        logger.error(f"Error in command {ctx.command}: {error}")
        embed = discord.Embed(
            title="⚠️ Error",
            description="An unexpected error occurred.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

# Events
@bot.event
async def on_ready():
    """Called when bot is ready"""
    logger.info(f'Bot logged in as {bot.user.name} (ID: {bot.user.id})')
    logger.info(f'Connected to {len(bot.guilds)} guild(s)')
    
    # Initialize data files
    init_data_files()
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="!help | Economy Bot"
        )
    )
    
    logger.info('Bot is ready!')

@bot.event
async def on_guild_join(guild):
    """Called when bot joins a guild"""
    logger.info(f'Joined guild: {guild.name} (ID: {guild.id})')

@bot.event
async def on_guild_remove(guild):
    """Called when bot leaves a guild"""
    logger.info(f'Left guild: {guild.name} (ID: {guild.id})')

# Basic help command
@bot.command(name='help')
async def help_command(ctx, category: str = None):
    """Display help information"""
    
    if category is None:
        embed = discord.Embed(
            title="🤖 Bot Help",
            description="Choose a category to see commands:",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📋 General",
            value="`!help general` - Server management commands",
            inline=False
        )
        embed.add_field(
            name="👑 Admin",
            value="`!help admin` - Admin-only commands",
            inline=False
        )
        embed.add_field(
            name="💰 Economy",
            value="`!help economy` - Economy, jobs, and market commands",
            inline=False
        )
        embed.set_footer(text="Use !help <category> for detailed commands")
        await ctx.send(embed=embed)
    
    elif category.lower() == 'general':
        embed = discord.Embed(
            title="📋 General Commands",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="!clear <amount>",
            value="Clear messages from channel",
            inline=False
        )
        embed.add_field(
            name="!ping",
            value="Check bot latency",
            inline=False
        )
        embed.add_field(
            name="!serverinfo",
            value="Display server information",
            inline=False
        )
        await ctx.send(embed=embed)
    
    elif category.lower() == 'admin':
        embed = discord.Embed(
            title="👑 Admin Commands",
            description="Requires `bot-admin` role",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Coming Soon",
            value="Admin commands will be added in the next file",
            inline=False
        )
        await ctx.send(embed=embed)
    
    elif category.lower() == 'economy':
        embed = discord.Embed(
            title="💰 Economy Commands",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Coming Soon",
            value="Economy commands will be added in the next file",
            inline=False
        )
        await ctx.send(embed=embed)
    
    else:
        embed = discord.Embed(
            title="❌ Unknown Category",
            description="Valid categories: `general`, `admin`, `economy`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# Load cogs (we'll add these later)
async def load_extensions():
    """Load all cog extensions"""
    extensions = ['general', 'admin', 'economy']
    
    for extension in extensions:
        try:
            await bot.load_extension(extension)
            logger.info(f'Loaded extension: {extension}')
        except Exception as e:
            logger.error(f'Failed to load extension {extension}: {e}')

# Setup hook
@bot.event
async def setup_hook():
    """Called before bot starts"""
    await load_extensions()

# Run the bot
if __name__ == '__main__':
    if not TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables!")
    else:
        try:
            bot.run(TOKEN)
        except Exception as e:
            logger.critical(f"Failed to start bot: {e}")
