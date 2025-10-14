import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import json
from datetime import datetime, timezone, timedelta
import webserver

# ---------------- Setup ----------------
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
KEEP_ALIVE = os.getenv("KEEP_ALIVE", "true").lower() == "true"

# Logging with rotation
handler = logging.FileHandler(filename="discord.log", encoding="utf-8", mode="a")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[handler]
)

# Discord intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# Bot setup with better configuration
bot = commands.Bot(
    command_prefix="~~",
    intents=intents,
    help_command=None  # We'll create a custom help command
)

# ---------------- Config Manager ----------------
class ConfigManager:
    def __init__(self, filename="config.json"):
        self.filename = filename
        self.lock = asyncio.Lock()
        self.default_config = {
            "auto_delete": {},
            "autorole": None,
            "grape_gifs": [],
            "member_numbers": {}
        }
        self._initialize_config()
    
    def _initialize_config(self):
        """Create config file if it doesn't exist."""
        if not os.path.exists(self.filename):
            with open(self.filename, "w") as f:
                json.dump(self.default_config, f, indent=2)
    
    async def load(self):
        """Load configuration from file."""
        async with self.lock:
            try:
                with open(self.filename, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.error(f"Config load error: {e}")
                return self.default_config.copy()
    
    async def save(self, data):
        """Save configuration to file."""
        async with self.lock:
            try:
                with open(self.filename, "w") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                logging.error(f"Config save error: {e}")

config_manager = ConfigManager()

# ---------------- Permissions Manager ----------------
class PermissionManager:
    FULL_ACCESS_ROLE = "bot-admin"
    LQ_ACCESS_ROLE = "lq-access"
    HOLDER_ROLE = "holder"
    
    @staticmethod
    def has_role(member, role_name: str) -> bool:
        """Check if member has a specific role."""
        return discord.utils.get(member.roles, name=role_name) is not None
    
    @classmethod
    def is_allowed(cls, member, command_type: str) -> bool:
        """Check if member has permission for command type."""
        if command_type == "full":
            return cls.has_role(member, cls.FULL_ACCESS_ROLE)
        elif command_type == "lq":
            return cls.has_role(member, cls.LQ_ACCESS_ROLE) or cls.has_role(member, cls.FULL_ACCESS_ROLE)
        elif command_type == "grape":
            return cls.has_role(member, cls.HOLDER_ROLE) or cls.has_role(member, cls.FULL_ACCESS_ROLE)
        return False

# ---------------- Error Handling ----------------
@bot.event
async def on_command_error(ctx, error):
    """Global error handler with embedded messages."""
    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Argument",
            description=f"Missing required argument: `{error.param.name}`",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"Use ~~help {ctx.command} for more info")
        await ctx.send(embed=embed)
        
    elif isinstance(error, commands.BadArgument):
        embed = discord.Embed(
            title="❌ Invalid Argument",
            description="Invalid argument type or member not found.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        
    elif isinstance(error, commands.CommandNotFound):
        embed = discord.Embed(
            title="❌ Unknown Command",
            description=f"Command not found. Use `~~help` to see available commands.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)
        
    elif isinstance(error, commands.MissingPermissions):
        embed = discord.Embed(
            title="❌ Missing Permissions",
            description="You do not have permission to use this command.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        
    elif isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="⏰ Cooldown Active",
            description=f"Please wait **{error.retry_after:.1f}s** before using this command again.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed, delete_after=5)
        
    else:
        logging.error(f"Error in command {ctx.command}: {error}", exc_info=error)
        embed = discord.Embed(
            title="⚠️ Unexpected Error",
            description="An unexpected error occurred. The issue has been logged.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

# ---------------- Message Filter ----------------
class MessageFilter:
    def __init__(self):
        self.spam_tracker = {}
        self.SPAM_TIMEFRAME = 5  # seconds
        self.SPAM_LIMIT = 5
        self.filter_file = "filter.json"
        
    def _load_filter_data(self):
        """Load filter data from file."""
        try:
            with open(self.filter_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"blocked_links": [], "blocked_words": []}
    
    def is_spam(self, user_id: int) -> bool:
        """Check if user is spamming."""
        now = datetime.now(timezone.utc).timestamp()
        
        # Clean old timestamps
        self.spam_tracker.setdefault(user_id, [])
        self.spam_tracker[user_id] = [
            t for t in self.spam_tracker[user_id] 
            if now - t < self.SPAM_TIMEFRAME
        ]
        
        # Add current timestamp
        self.spam_tracker[user_id].append(now)
        
        return len(self.spam_tracker[user_id]) > self.SPAM_LIMIT
    
    def contains_blocked_content(self, content: str) -> tuple[bool, str]:
        """Check if message contains blocked words or links."""
        filter_data = self._load_filter_data()
        content_lower = content.lower()
        
        # Check blocked words
        for word in filter_data.get("blocked_words", []):
            if word and word.lower() in content_lower:
                return True, "word"
        
        # Check blocked links
        for link in filter_data.get("blocked_links", []):
            if link and link.lower() in content_lower:
                return True, "link"
        
        return False, None

message_filter = MessageFilter()

@bot.event
async def on_message(message):
    """Handle message filtering and spam detection."""
    # Ignore bots and DMs
    if message.author.bot or isinstance(message.channel, discord.DMChannel):
        return
    
    try:
        # Spam detection
        if message_filter.is_spam(message.author.id):
            await message.delete()
            await message.channel.send(
                f"{message.author.mention}, slow down! ⏰",
                delete_after=5
            )
            return
        
        # Content filtering
        is_blocked, block_type = message_filter.contains_blocked_content(message.content)
        if is_blocked:
            await message.delete()
            if block_type == "word":
                msg = f"{message.author.mention}, watch your language! 🚫"
            else:
                msg = f"{message.author.mention}, that link is not allowed! 🔗"
            await message.channel.send(msg, delete_after=5)
            return
            
    except Exception as e:
        logging.warning(f"Message filter error: {e}")
    
    await bot.process_commands(message)

# ---------------- Auto Cleaner Task ----------------
@tasks.loop(minutes=1)  # Changed to 1 minute for better performance
async def auto_cleaner():
    """Automatically clean channels based on configuration."""
    try:
        config = await config_manager.load()
        
        for channel_id, settings in config.get("auto_delete", {}).items():
            if not settings.get("enabled"):
                continue
            
            channel = bot.get_channel(int(channel_id))
            if not channel:
                continue
            
            try:
                messages = [msg async for msg in channel.history(limit=500, oldest_first=True)]
            except discord.Forbidden:
                logging.warning(f"No permission to access channel {channel_id}")
                continue
            
            now = datetime.utcnow()
            deleted_count = 0
            
            # Age-based cleanup
            max_age = settings.get("max_age")
            if max_age:
                for msg in messages:
                    age_seconds = (now - msg.created_at).total_seconds()
                    if age_seconds > max_age:
                        try:
                            await msg.delete()
                            deleted_count += 1
                            await asyncio.sleep(1)  # Rate limit protection
                        except discord.NotFound:
                            pass
                        except Exception as e:
                            logging.error(f"Error deleting message: {e}")
            
            # Count-based cleanup
            max_messages = settings.get("max_messages")
            if max_messages and len(messages) > max_messages:
                to_delete = messages[:len(messages) - max_messages]
                for msg in to_delete:
                    try:
                        await msg.delete()
                        deleted_count += 1
                        await asyncio.sleep(1)
                    except discord.NotFound:
                        pass
                    except Exception as e:
                        logging.error(f"Error deleting message: {e}")
            
            if deleted_count > 0:
                logging.info(f"Auto-cleaned {deleted_count} messages from channel {channel_id}")
                
    except Exception as e:
        logging.error(f"Auto cleaner error: {e}")

@auto_cleaner.before_loop
async def before_auto_cleaner():
    """Wait for bot to be ready before starting auto cleaner."""
    await bot.wait_until_ready()

# ---------------- Custom Help Command ----------------
@bot.command(name="help")
async def help_command(ctx, command_name: str = None):
    """Display help information."""
    if command_name:
        # Help for specific command
        cmd = bot.get_command(command_name)
        if cmd:
            embed = discord.Embed(
                title=f"Command: {cmd.name}",
                description=cmd.help or "No description available",
                color=discord.Color.blue()
            )
            embed.add_field(name="Usage", value=f"`~~{cmd.name} {cmd.signature}`", inline=False)
            if cmd.aliases:
                embed.add_field(name="Aliases", value=", ".join(cmd.aliases), inline=False)
        else:
            embed = discord.Embed(
                title="❌ Command Not Found",
                description=f"No command named `{command_name}` found.",
                color=discord.Color.red()
            )
    else:
        # General help
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description="Use `~~help <command>` for detailed information.",
            color=discord.Color.blue()
        )
        
        # Group commands by cog
        cogs = {}
        for command in bot.commands:
            cog_name = command.cog_name or "General"
            if cog_name not in cogs:
                cogs[cog_name] = []
            cogs[cog_name].append(command)
        
        for cog_name, commands_list in cogs.items():
            cmd_list = ", ".join([f"`{cmd.name}`" for cmd in commands_list])
            embed.add_field(name=cog_name, value=cmd_list, inline=False)
        
        embed.set_footer(text="Command prefix: ~~")
    
    await ctx.send(embed=embed)

# ---------------- Cog Loader ----------------
async def load_cogs():
    """Load all cog extensions."""
    cogs = ["admin", "economy"]
    for cog in cogs:
        try:
            await bot.load_extension(cog)
            logging.info(f"✅ Loaded cog: {cog}")
        except Exception as e:
            logging.error(f"❌ Failed to load cog {cog}: {e}")

# ---------------- Bot Events ----------------
@bot.event
async def setup_hook():
    """Initialize bot components."""
    await load_cogs()
    auto_cleaner.start()
    logging.info("🔧 Setup hook completed")

@bot.event
async def on_ready():
    """Called when bot is ready."""
    logging.info(f"✅ Bot is ready as {bot.user} (ID: {bot.user.id})")
    logging.info(f"Connected to {len(bot.guilds)} guild(s)")
    
    # Set bot status
    await bot.change_presence(
        activity=discord.Game(name="~~help | Economy Bot"),
        status=discord.Status.online
    )

# ---------------- Keep Alive ----------------
if KEEP_ALIVE:
    webserver.keep_alive()

# ---------------- Run Bot ----------------
if __name__ == "__main__":
    try:
        bot.run(TOKEN)
    except Exception as e:
        logging.critical(f"Failed to start bot: {e}")
