import discord
from discord.ext import commands, tasks
import logging
from dotenv import load_dotenv
import os
import asyncio
import random
import json
from datetime import datetime
import webserver

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='~~', intents=intents)
bot.remove_command("help")

CONFIG_FILE = "config.json"
LQ_ROLE = "low quality"
READER_ROLE = "reader"
LQ_ACCESS_ROLE = "lq-access"
FULL_ACCESS_ROLE = "bot-admin"
HOLDER_ROLE = "holder"

if not os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'w') as f:
        json.dump({"auto_delete": {}, "autorole": None, "grape_gifs": [], "member_numbers": {}}, f)

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def has_role(member, role_name):
    return discord.utils.get(member.roles, name=role_name) is not None

def is_allowed(ctx, command_type):
    if command_type == "lq":
        return has_role(ctx.author, LQ_ACCESS_ROLE) or has_role(ctx.author, FULL_ACCESS_ROLE)
    if command_type == "full":
        return has_role(ctx.author, FULL_ACCESS_ROLE)
    if command_type == "grape":
        return has_role(ctx.author, HOLDER_ROLE) or has_role(ctx.author, FULL_ACCESS_ROLE)
    return False

@bot.event
async def on_ready():
    print(f"Bot ready as {bot.user.name}")
    auto_cleaner.start()

    number_data = config.get("member_numbers", {})
    for member in bot.get_all_members():
        if not member.bot:
            member_id = str(member.id)
            if member_id not in number_data:
                try:
                    num = int(member.display_name)
                    number_data[member_id] = {"number": num, "original": num}
                except:
                    continue
            else:
                try:
                    await member.edit(nick=str(number_data[member_id]["number"]))
                except:
                    continue
    config["member_numbers"] = number_data
    save_config()

@bot.event
async def on_member_join(member):
    role_name = config.get("autorole")
    if role_name:
        role = discord.utils.get(member.guild.roles, name=role_name)
        if role:
            await member.add_roles(role)

    number_data = config.get("member_numbers", {})
    member_id = str(member.id)
    if member_id in number_data:
        number = number_data[member_id]["number"]
    else:
        current = max([v["number"] for v in number_data.values()], default=124)
        number = current + 1
        number_data[member_id] = {"number": number, "original": number}
        config["member_numbers"] = number_data
        save_config()
    try:
        await member.edit(nick=str(number))
    except:
        pass

@tasks.loop(seconds=30)
async def auto_cleaner():
    for cid, conf in config.get("auto_delete", {}).items():
        if not conf.get("enabled"):
            continue
        channel = bot.get_channel(int(cid))
        if not channel:
            continue

        try:
            messages = [msg async for msg in channel.history(limit=500, oldest_first=True)]
        except discord.Forbidden:
            continue

        now = datetime.utcnow()

        if conf.get("max_age"):
            for msg in messages:
                age = (now - msg.created_at).total_seconds()
                if age > conf["max_age"]:
                    try:
                        await msg.delete()
                        await asyncio.sleep(1)
                    except:
                        continue

        if conf.get("max_messages") and len(messages) > conf["max_messages"]:
            to_delete = messages[:len(messages) - conf["max_messages"]]
            for msg in to_delete:
                try:
                    await msg.delete()
                    await asyncio.sleep(1)
                except:
                    continue

@bot.command()
async def clear(ctx, amount: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    if amount < 1 or amount > 100:
        return await ctx.send("❌ Please choose a number between 1 and 100.")
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"🧹 Deleted {len(deleted)} messages.", delete_after=3)

@bot.command()
async def setdelete(ctx, toggle: str):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    cid = str(ctx.channel.id)
    config["auto_delete"].setdefault(cid, {})
    config["auto_delete"][cid]["enabled"] = toggle.lower() == "on"
    save_config()
    await ctx.send(f"🛠️ Auto-delete {'enabled' if toggle.lower() == 'on' else 'disabled'} for this channel.")

@bot.command()
async def maxmsg(ctx, amount: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    cid = str(ctx.channel.id)
    config["auto_delete"].setdefault(cid, {})
    config["auto_delete"][cid]["max_messages"] = amount
    save_config()
    await ctx.send(f"🔢 Max messages set to {amount}.")

@bot.command()
async def maxage(ctx, seconds: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    cid = str(ctx.channel.id)
    config["auto_delete"].setdefault(cid, {})
    config["auto_delete"][cid]["max_age"] = seconds
    save_config()
    await ctx.send(f"⏳ Max message age set to {seconds} seconds.")

@bot.command()
async def numq(ctx, number: int):
    number_data = config.get("member_numbers", {})
    for uid, data in number_data.items():
        if data["number"] == number:
            member = ctx.guild.get_member(int(uid))
            if member:
                return await ctx.send(f"❌ Number {number} is already in use by {member.mention}.")
    await ctx.send(f"✅ Number {number} is available.")

@bot.command()
async def setnum(ctx, member: discord.Member, number: int):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    number_data = config.get("member_numbers", {})
    for uid, data in number_data.items():
        if data["number"] == number and uid != str(member.id):
            return await ctx.send("❌ That number is already taken.")

    member_id = str(member.id)
    if member_id not in number_data:
        number_data[member_id] = {"number": number, "original": number}
    else:
        number_data[member_id]["number"] = number
    config["member_numbers"] = number_data
    save_config()
    try:
        await member.edit(nick=str(number))
    except:
        pass
    await ctx.send(f"✅ Set number {number} for {member.mention}.")

@bot.command()
async def grape(ctx, user: discord.Member):
    if not is_allowed(ctx, "grape"):
        return await ctx.send("❌ You do not have permission.")
    gifs = config.get("grape_gifs", [])
    gif = random.choice(gifs) if gifs else None
    embed = discord.Embed(description=f"**{ctx.author.display_name} took advantage of {user.display_name}**", color=discord.Color.purple())
    if gif:
        embed.set_image(url=gif)
    await ctx.send(embed=embed)

@bot.command()
async def lq(ctx, member: discord.Member):
    if not is_allowed(ctx, "lq"):
        return await ctx.send("❌ You do not have permission.")
    guild = ctx.guild
    lq_role = discord.utils.get(guild.roles, name=LQ_ROLE)
    reader_role = discord.utils.get(guild.roles, name=READER_ROLE)
    if lq_role:
        await member.add_roles(lq_role)
    if reader_role:
        await member.remove_roles(reader_role)
    await ctx.send(f"{member.mention} marked as low quality.")

@bot.command()
async def unlq(ctx, member: discord.Member):
    if not is_allowed(ctx, "lq"):
        return await ctx.send("❌ You do not have permission.")
    guild = ctx.guild
    lq_role = discord.utils.get(guild.roles, name=LQ_ROLE)
    reader_role = discord.utils.get(guild.roles, name=READER_ROLE)
    if reader_role:
        await member.add_roles(reader_role)
    if lq_role:
        await member.remove_roles(lq_role)
    await ctx.send(f"{member.mention} restored to reader.")

@bot.command()
async def allowgrape(ctx, member: discord.Member):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    role = discord.utils.get(ctx.guild.roles, name=HOLDER_ROLE)
    if not role:
        role = await ctx.guild.create_role(name=HOLDER_ROLE)
    await member.add_roles(role)
    await ctx.send(f"✅ {member.mention} can now use ~~grape.")

@bot.command()
async def disallowgrape(ctx, member: discord.Member):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    role = discord.utils.get(ctx.guild.roles, name=HOLDER_ROLE)
    if not role:
        return await ctx.send("⚠️ 'holder' role does not exist.")
    await member.remove_roles(role)
    await ctx.send(f"🚫 {member.mention} can no longer use ~~grape.")

@bot.command()
async def rest(ctx, member: discord.Member):
    if not is_allowed(ctx, "full"):
        return await ctx.send("❌ You do not have permission.")
    number_data = config.get("member_numbers", {})
    member_id = str(member.id)
    if member_id in number_data:
        number_data[member_id]["number"] = number_data[member_id]["original"]
        config["member_numbers"] = number_data
        save_config()
        try:
            await member.edit(nick=str(number_data[member_id]["original"]))
        except:
            pass
        await ctx.send(f"🔄 Reset nickname of {member.mention} to original number.")
    else:
        await ctx.send("❌ This user does not have a number registered.")

@bot.command(name="help")
async def custom_help(ctx):
    if not any(has_role(ctx.author, r) for r in [FULL_ACCESS_ROLE, LQ_ACCESS_ROLE, HOLDER_ROLE]):
        return await ctx.send("❌ You do not have permission to use this command.")

    embed = discord.Embed(title="Available Commands", color=discord.Color.blurple())

    if is_allowed(ctx, "full"):
        embed.add_field(name="~~clear [num]", value="Clear messages (1-100)", inline=False)
        embed.add_field(name="~~setdelete on/off", value="Toggle auto-deletion in channel", inline=False)
        embed.add_field(name="~~maxmsg [num]", value="Set max allowed messages", inline=False)
        embed.add_field(name="~~maxage [sec]", value="Set max message age in seconds", inline=False)
        embed.add_field(name="~~setnum @user [number]", value="Assign a specific number to a user", inline=False)
        embed.add_field(name="~~numq [number]", value="Check if a number is in use", inline=False)
        embed.add_field(name="~~allowgrape @user", value="Give holder role", inline=False)
        embed.add_field(name="~~disallowgrape @user", value="Remove holder role", inline=False)
        embed.add_field(name="~~rest @user", value="Reset a member's nickname to their original number", inline=False)

    if is_allowed(ctx, "lq"):
        embed.add_field(name="~~lq @user", value="Assign low quality role and remove reader role", inline=False)
        embed.add_field(name="~~unlq @user", value="Remove low quality role and add reader role", inline=False)

    if is_allowed(ctx, "grape"):
        embed.add_field(name="~~grape @user", value="Send a grape GIF with message", inline=False)

    await ctx.send(embed=embed)

webserver.keep_alive()
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
