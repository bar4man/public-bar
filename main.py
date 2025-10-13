# main.py

import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
import os
import json
import datetime
import asyncio
import time
from collections import defaultdict

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# -------------- Helpers --------------

def is_bot_admin(user: discord.Member) -> bool:
    return any(role.name.lower() == "bot-admin" for role in user.roles)

def load_json(filename):
    with open(filename, "r") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

# -------------- Events --------------

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"{bot.user} is ready.")
    schedule_task.start()

@bot.event
async def on_member_join(member):
    config = load_json("config.json")
    role = discord.utils.get(member.guild.roles, name=config["auto_role_name"])
    channel = bot.get_channel(config["welcome_channel_id"])
    if role:
        await member.add_roles(role)
    if channel:
        await channel.send(config["welcome_message"].replace("{mention}", member.mention))
    await log_to_channel(member.guild, f"✅ {member} joined.")

@bot.event
async def on_member_remove(member):
    await log_to_channel(member.guild, f"❌ {member} left or was kicked.")

@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return
    await log_to_channel(message.guild, f"🗑️ Message deleted from {message.author}: `{message.content}`")

@bot.event
async def on_message_edit(before, after):
    if before.content != after.content and not before.author.bot:
        await log_to_channel(before.guild, f"✏️ Message edited by {before.author}:\nBefore: `{before.content}`\nAfter: `{after.content}`")

# -------------- Logging --------------

async def log_to_channel(guild, content):
    config = load_json("config.json")
    channel = guild.get_channel(config["log_channel_id"])
    if channel:
        await channel.send(content)

# -------------- Slash Commands --------------

@bot.tree.command(name="help", description="Show all available bot commands.")
async def help_command(interaction: discord.Interaction):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return

    embed = discord.Embed(title="🤖 Bot Commands", color=discord.Color.blue())
    embed.add_field(name="🛠 Moderation", value="`/warn`, `/kick`, `/ban`, `/timeout`", inline=False)
    embed.add_field(name="✅ Roles", value="`/verify`, `/createrole`", inline=False)
    embed.add_field(name="📨 Tickets", value="`/ticket open`, `/ticket close`", inline=False)
    embed.add_field(name="📅 Scheduling", value="`/schedule`", inline=False)
    embed.add_field(name="🎨 Self Roles", value="Dropdown menu only", inline=False)
    embed.add_field(name="🆘 Utility", value="`/help`", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="warn", description="Warn a user.")
@app_commands.describe(user="User to warn", reason="Reason for warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return

    warns = load_json("warns.json")
    guild_id = str(interaction.guild_id)
    user_id = str(user.id)

    if guild_id not in warns:
        warns[guild_id] = {}
    if user_id not in warns[guild_id]:
        warns[guild_id][user_id] = []

    warns[guild_id][user_id].append({
        "reason": reason,
        "moderator": str(interaction.user),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

    save_json("warns.json", warns)

    await interaction.response.send_message(f"⚠️ Warned {user.mention} for: {reason}")
    await log_to_channel(interaction.guild, f"⚠️ {user} was warned by {interaction.user}: {reason}")

    # Auto punish
    if len(warns[guild_id][user_id]) >= 3:
        await user.timeout(datetime.timedelta(minutes=10), reason="Auto-timeout after 3 warnings.")
        await log_to_channel(interaction.guild, f"⏱️ {user} was auto-timed out for repeated warnings.")
    if len(warns[guild_id][user_id]) >= 5:
        await interaction.guild.ban(user, reason="Auto-ban after 5 warnings.")
        await log_to_channel(interaction.guild, f"🔨 {user} was auto-banned for repeated warnings.")

@bot.tree.command(name="kick", description="Kick a user.")
@app_commands.describe(user="User to kick", reason="Reason")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return
    await user.kick(reason=reason)
    await interaction.response.send_message(f"👢 Kicked {user.mention} for: {reason}")
    await log_to_channel(interaction.guild, f"👢 {user} was kicked by {interaction.user}: {reason}")

@bot.tree.command(name="ban", description="Ban a user.")
@app_commands.describe(user="User to ban", reason="Reason")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return
    await interaction.guild.ban(user, reason=reason)
    await interaction.response.send_message(f"🔨 Banned {user.mention} for: {reason}")
    await log_to_channel(interaction.guild, f"🔨 {user} was banned by {interaction.user}: {reason}")

@bot.tree.command(name="timeout", description="Timeout a user.")
@app_commands.describe(user="User to timeout", minutes="Duration in minutes")
async def timeout(interaction: discord.Interaction, user: discord.Member, minutes: int):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return
    duration = datetime.timedelta(minutes=minutes)
    await user.timeout(duration, reason=f"By {interaction.user}")
    await interaction.response.send_message(f"⏱️ Timed out {user.mention} for {minutes} minutes.")
    await log_to_channel(interaction.guild, f"⏱️ {user} was timed out by {interaction.user} for {minutes}m")

@bot.tree.command(name="verify", description="Give the verified role to a user.")
@app_commands.describe(user="User to verify")
async def verify(interaction: discord.Interaction, user: discord.Member):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return
    config = load_json("config.json")
    role = discord.utils.get(interaction.guild.roles, name=config["verified_role_name"])
    if role:
        await user.add_roles(role)
        await interaction.response.send_message(f"✅ {user.mention} has been verified.")
        await log_to_channel(interaction.guild, f"✅ {user} was verified by {interaction.user}.")

@bot.tree.command(name="createrole", description="Create a new role.")
@app_commands.describe(name="Name of the role")
async def createrole(interaction: discord.Interaction, name: str):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return
    role = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(f"🎭 Created role `{name}`.")
    await log_to_channel(interaction.guild, f"🎭 Role `{name}` created by {interaction.user}.")

@bot.tree.command(name="schedule", description="Schedule a message to be sent later.")
@app_commands.describe(channel="Channel to send to", message="Message content", minutes="Delay in minutes")
async def schedule(interaction: discord.Interaction, channel: discord.TextChannel, message: str, minutes: int):
    if not is_bot_admin(interaction.user):
        await interaction.response.send_message("❌ You don’t have permission to use this.", ephemeral=True)
        return
    schedule = load_json("scheduled.json")
    send_time = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)).isoformat()
    schedule.append({"channel_id": channel.id, "message": message, "time": send_time})
    save_json("scheduled.json", schedule)
    await interaction.response.send_message(f"📅 Scheduled message in {minutes} minutes.")

# -------------- Scheduled Tasks --------------

@tasks.loop(seconds=60)
async def schedule_task():
    now = datetime.datetime.now(datetime.timezone.utc)
    schedule = load_json("scheduled.json")
    to_post = [e for e in schedule if e["time"] <= now.isoformat()]
    if not to_post:
        return

    for event in to_post:
        channel = bot.get_channel(event["channel_id"])
        if channel:
            await channel.send(event["message"])
        schedule.remove(event)
    save_json("scheduled.json", schedule)

# -------------- Message Filtering --------------

spam_tracker = defaultdict(list)
SPAM_TIMEFRAME = 5
SPAM_LIMIT = 5

@bot.event
async def on_message(message):
    if message.author.bot or isinstance(message.channel, discord.DMChannel):
        return

    filter_data = load_json("filter.json")
    content = message.content.lower()

    for blocked in filter_data["blocked_links"]:
        if blocked in content:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, links are not allowed.", delete_after=5)
            await log_to_channel(message.guild, f"🚫 Link deleted from {message.author}: `{message.content}`")
            return

    for word in filter_data["blocked_words"]:
        if word in content:
            await message.delete()
            await message.channel.send(f"{message.author.mention}, watch your language.", delete_after=5)
            await log_to_channel(message.guild, f"⚠️ Offensive content from {message.author}: `{message.content}`")
            return

    now = time.time()
    spam_tracker[message.author.id] = [t for t in spam_tracker[message.author.id] if now - t < SPAM_TIMEFRAME]
    spam_tracker[message.author.id].append(now)
    if len(spam_tracker[message.author.id]) > SPAM_LIMIT:
        await message.delete()
        await message.channel.send(f"{message.author.mention}, slow down!", delete_after=5)
        await log_to_channel(message.guild, f"🛑 Spam detected from {message.author}.")
        return

    triggers = load_json("triggers.json")
    for keyword, response in triggers.items():
        if keyword in content:
            await message.channel.send(response)
            break

    await bot.process_commands(message)

# -------------- Run Bot --------------

bot.run(TOKEN)
