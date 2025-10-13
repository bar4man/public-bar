# admin.py

import discord
import json
from datetime import datetime

CONFIG_FILE = "config.json"
LQ_ROLE = "low quality"
READER_ROLE = "reader"
LQ_ACCESS_ROLE = "lq-access"
FULL_ACCESS_ROLE = "bot-admin"
HOLDER_ROLE = "holder"

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

def save_config():
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

# ---------------- Permission Check ----------------

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

# ---------------- Admin Commands ----------------

def register_commands(bot):

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, discord.ext.commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: {error.param.name}")
        elif isinstance(error, discord.ext.commands.BadArgument):
            await ctx.send(f"❌ Invalid argument type or member not found.")
        elif isinstance(error, discord.ext.commands.CommandNotFound):
            await ctx.send(f"❌ Unknown command. Use ~~help to see available commands.")
        else:
            await ctx.send(f"❌ An error occurred: {str(error)}")

    @bot.command()
    async def clear(ctx, amount: int):
        if not is_allowed(ctx, "full"):
            return await ctx.send("❌ You do not have permission.")
        if amount < 1 or amount > 100:
            return await ctx.send("❌ Please choose a number between 1 and 100.")
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"🧹 Deleted {len(deleted)} messages.", delete_after=3)

    @bot.command()
    async def lq(ctx, member: discord.Member):
        if not is_allowed(ctx, "lq"):
            return await ctx.send("❌ You do not have permission.")
        lq_role = discord.utils.get(ctx.guild.roles, name=LQ_ROLE)
        reader_role = discord.utils.get(ctx.guild.roles, name=READER_ROLE)
        if lq_role:
            await member.add_roles(lq_role)
        if reader_role:
            await member.remove_roles(reader_role)
        await ctx.send(f"{member.mention} marked as low quality.")

    @bot.command()
    async def unlq(ctx, member: discord.Member):
        if not is_allowed(ctx, "lq"):
            return await ctx.send("❌ You do not have permission.")
        lq_role = discord.utils.get(ctx.guild.roles, name=LQ_ROLE)
        reader_role = discord.utils.get(ctx.guild.roles, name=READER_ROLE)
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
            return await ctx.send(f"⚠️ '{HOLDER_ROLE}' role does not exist.")
        await member.remove_roles(role)
        await ctx.send(f"🚫 {member.mention} can no longer use ~~grape.")
