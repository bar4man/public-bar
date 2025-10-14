import discord
from discord.ext import commands
import json
import os
import asyncio
import logging
from datetime import datetime

class Admin(commands.Cog):
    """Administrative commands for bot management and moderation."""

    def __init__(self, bot):
        self.bot = bot
        self.econ_file = "economy.json"
        self.lock = asyncio.Lock()
        self._initialize_economy()

    def _initialize_economy(self):
        """Create economy.json if it doesn't exist."""
        if not os.path.exists(self.econ_file):
            with open(self.econ_file, "w") as f:
                json.dump({}, f, indent=2)

    # -------------------- Economy Helpers --------------------
    async def load_data(self) -> dict:
        async with self.lock:
            try:
                with open(self.econ_file, "r") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logging.error(f"Error loading economy data: {e}")
                return {}

    async def save_data(self, data: dict) -> bool:
        async with self.lock:
            try:
                with open(self.econ_file, "w") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                logging.error(f"Error saving economy data: {e}")
                return False

    def is_admin(self, member: discord.Member) -> bool:
        return discord.utils.get(member.roles, name="bot-admin") is not None

    async def cog_check(self, ctx):
        """Check all commands in this cog for bot-admin role."""
        if not self.is_admin(ctx.author):
            embed = discord.Embed(
                title="🔒 Admin Only",
                description="This command requires the `bot-admin` role.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return False
        return True

    # -------------------- Economy Commands --------------------
    @commands.command(name="give", aliases=["addmoney"])
    async def give_money(self, ctx, member: discord.Member, amount: int):
        if amount <= 0 or member.bot:
            return await ctx.send("❌ Invalid target or amount.")

        data = await self.load_data()
        uid = str(member.id)
        data.setdefault(uid, {"wallet": 0, "bank": 0})
        data[uid]["wallet"] += amount
        await self.save_data(data)
        await ctx.send(f"✅ Gave {amount}£ to {member.mention}")

    @commands.command(name="take", aliases=["removemoney"])
    async def take_money(self, ctx, member: discord.Member, amount: int):
        if amount <= 0 or member.bot:
            return await ctx.send("❌ Invalid target or amount.")

        data = await self.load_data()
        uid = str(member.id)
        data.setdefault(uid, {"wallet": 0, "bank": 0})
        taken = min(amount, data[uid]["wallet"])
        data[uid]["wallet"] -= taken
        await self.save_data(data)
        await ctx.send(f"✅ Took {taken}£ from {member.mention}")

    @commands.command(name="setmoney", aliases=["setbalance"])
    async def set_money(self, ctx, member: discord.Member, amount: int):
        if amount < 0 or member.bot:
            return await ctx.send("❌ Invalid target or amount.")

        data = await self.load_data()
        uid = str(member.id)
        data.setdefault(uid, {"wallet": 0, "bank": 0})
        data[uid]["wallet"] = amount
        await self.save_data(data)
        await ctx.send(f"✅ Set {member.mention}'s wallet to {amount}£")

    @commands.command(name="resetuser")
    async def reset_user(self, ctx, member: discord.Member):
        data = await self.load_data()
        uid = str(member.id)
        if uid not in data:
            return await ctx.send(f"ℹ️ {member.mention} has no data.")
        del data[uid]
        await self.save_data(data)
        await ctx.send(f"🔄 Reset economy data for {member.mention}")

    @commands.command(name="viewuser")
    async def view_user(self, ctx, member: discord.Member):
        data = await self.load_data()
        uid = str(member.id)
        user_data = data.get(uid, {"wallet": 0, "bank": 0})
        total = user_data["wallet"] + user_data["bank"]

        embed = discord.Embed(
            title=f"💼 Economy Profile: {member.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="💵 Wallet", value=f"{user_data['wallet']:,}£")
        embed.add_field(name="🏦 Bank", value=f"{user_data['bank']:,}£")
        embed.add_field(name="💎 Total", value=f"{total:,}£")
        await ctx.send(embed=embed)

    # -------------------- Utility / Moderation Commands --------------------
    @commands.command(name="clear", aliases=["purge"])
    async def clear(self, ctx, amount: int = 10):
        """Delete messages from channel (bot-admin only)."""
        if amount <= 0:
            return await ctx.send("❌ Specify a positive number of messages.")
        deleted = await ctx.channel.purge(limit=amount + 1)
        confirm = await ctx.send(f"✅ Deleted {len(deleted) - 1} messages.")
        await asyncio.sleep(3)
        await confirm.delete()

    @commands.command(name="ping")
    async def ping(self, ctx):
        await ctx.send(f"🏓 Pong! Latency: {round(self.bot.latency*1000)}ms")

    @commands.command(name="say")
    async def say(self, ctx, *, message: str):
        """Make bot say something (bot-admin only)."""
        await ctx.message.delete()
        await ctx.send(message)

    @commands.command(name="userinfo", aliases=["whois"])
    async def userinfo(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        embed = discord.Embed(
            title=f"👤 {member.display_name}",
            color=member.color,
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🆔 User ID", value=member.id)
        embed.add_field(name="🎭 Roles", value=", ".join(roles) if roles else "None")
        embed.add_field(name="📅 Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
        embed.add_field(name="🗓️ Joined Discord", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        await ctx.send(embed=embed)

    @commands.command(name="serverinfo", aliases=["guildinfo"])
    async def serverinfo(self, ctx):
        guild = ctx.guild
        embed = discord.Embed(
            title=f"🏰 {guild.name}",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="🆔 Server ID", value=guild.id)
        embed.add_field(name="👑 Owner", value=guild.owner.mention if guild.owner else "Unknown")
        embed.add_field(name="👥 Members", value=guild.member_count)
        embed.add_field(name="📅 Created On", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        embed.add_field(name="💬 Text Channels", value=len(guild.text_channels))
        embed.add_field(name="🎧 Voice Channels", value=len(guild.voice_channels))
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Admin(bot))
