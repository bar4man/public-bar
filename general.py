import discord
from discord.ext import commands
import logging
from datetime import datetime

logger = logging.getLogger('discord_bot')

class General(commands.Cog):
    """General server management commands"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='ping')
    async def ping(self, ctx):
        """Check bot latency"""
        latency = round(self.bot.latency * 1000)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"Bot latency: **{latency}ms**",
            color=discord.Color.green() if latency < 100 else discord.Color.orange()
        )
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='clear')
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        """Clear messages from channel
        
        Usage: !clear <amount>
        Example: !clear 10
        """
        if amount < 1:
            embed = discord.Embed(
                title="❌ Invalid Amount",
                description="Amount must be at least 1.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed, delete_after=5)
        
        if amount > 100:
            embed = discord.Embed(
                title="❌ Too Many Messages",
                description="You can only clear up to 100 messages at a time.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed, delete_after=5)
        
        try:
            # Delete the command message first
            await ctx.message.delete()
            
            # Delete the specified amount of messages
            deleted = await ctx.channel.purge(limit=amount)
            
            embed = discord.Embed(
                title="🧹 Messages Cleared",
                description=f"Successfully deleted **{len(deleted)}** messages.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Cleared by {ctx.author.name}")
            
            # Send confirmation and delete after 5 seconds
            await ctx.send(embed=embed, delete_after=5)
            
            logger.info(f"{ctx.author} cleared {len(deleted)} messages in #{ctx.channel.name}")
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description="I don't have permission to delete messages in this channel.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        
        except Exception as e:
            logger.error(f"Error in clear command: {e}")
            embed = discord.Embed(
                title="⚠️ Error",
                description="An error occurred while clearing messages.",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed, delete_after=5)
    
    @commands.command(name='serverinfo')
    async def serverinfo(self, ctx):
        """Display server information
        
        Usage: !serverinfo
        """
        guild = ctx.guild
        
        # Get member counts
        total_members = guild.member_count
        bots = len([m for m in guild.members if m.bot])
        humans = total_members - bots
        
        # Get channel counts
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Get role count
        roles = len(guild.roles) - 1  # Exclude @everyone
        
        # Server boost info
        boost_level = guild.premium_tier
        boost_count = guild.premium_subscription_count
        
        embed = discord.Embed(
            title=f"📊 {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Set server icon
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Server info
        embed.add_field(
            name="🆔 Server ID",
            value=f"`{guild.id}`",
            inline=True
        )
        
        embed.add_field(
            name="👑 Owner",
            value=guild.owner.mention if guild.owner else "Unknown",
            inline=True
        )
        
        embed.add_field(
            name="📅 Created",
            value=guild.created_at.strftime("%b %d, %Y"),
            inline=True
        )
        
        # Member stats
        embed.add_field(
            name="👥 Members",
            value=f"Total: **{total_members}**\nHumans: **{humans}**\nBots: **{bots}**",
            inline=True
        )
        
        # Channel stats
        embed.add_field(
            name="📁 Channels",
            value=f"Categories: **{categories}**\nText: **{text_channels}**\nVoice: **{voice_channels}**",
            inline=True
        )
        
        # Other stats
        embed.add_field(
            name="🎭 Roles",
            value=f"**{roles}** roles",
            inline=True
        )
        
        # Boost info
        if boost_count > 0:
            embed.add_field(
                name="✨ Server Boost",
                value=f"Level **{boost_level}** ({boost_count} boosts)",
                inline=True
            )
        
        # Verification level
        verification_levels = {
            discord.VerificationLevel.none: "None",
            discord.VerificationLevel.low: "Low",
            discord.VerificationLevel.medium: "Medium",
            discord.VerificationLevel.high: "High",
            discord.VerificationLevel.highest: "Highest"
        }
        embed.add_field(
            name="🔒 Verification",
            value=verification_levels.get(guild.verification_level, "Unknown"),
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='userinfo')
    async def userinfo(self, ctx, member: discord.Member = None):
        """Display user information
        
        Usage: !userinfo [@user]
        Example: !userinfo or !userinfo @username
        """
        member = member or ctx.author
        
        # Get roles (excluding @everyone)
        roles = [role.mention for role in member.roles if role.name != "@everyone"]
        roles_display = ", ".join(roles) if roles else "None"
        
        # Trim if too long
        if len(roles_display) > 1024:
            roles_display = roles_display[:1021] + "..."
        
        embed = discord.Embed(
            title=f"👤 User Information",
            color=member.color if member.color != discord.Color.default() else discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Basic info
        embed.add_field(
            name="📛 Username",
            value=f"{member.name}",
            inline=True
        )
        
        embed.add_field(
            name="🆔 User ID",
            value=f"`{member.id}`",
            inline=True
        )
        
        embed.add_field(
            name="🤖 Bot",
            value="Yes" if member.bot else "No",
            inline=True
        )
        
        # Dates
        embed.add_field(
            name="📅 Account Created",
            value=member.created_at.strftime("%b %d, %Y"),
            inline=True
        )
        
        embed.add_field(
            name="📥 Joined Server",
            value=member.joined_at.strftime("%b %d, %Y") if member.joined_at else "Unknown",
            inline=True
        )
        
        # Status
        status_emojis = {
            discord.Status.online: "🟢 Online",
            discord.Status.idle: "🟡 Idle",
            discord.Status.dnd: "🔴 Do Not Disturb",
            discord.Status.offline: "⚫ Offline"
        }
        embed.add_field(
            name="📶 Status",
            value=status_emojis.get(member.status, "Unknown"),
            inline=True
        )
        
        # Roles
        embed.add_field(
            name=f"🎭 Roles ({len(roles)})",
            value=roles_display,
            inline=False
        )
        
        # Permissions
        if member.guild_permissions.administrator:
            embed.add_field(
                name="⚡ Key Permissions",
                value="👑 Administrator",
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='avatar')
    async def avatar(self, ctx, member: discord.Member = None):
        """Display user's avatar
        
        Usage: !avatar [@user]
        Example: !avatar or !avatar @username
        """
        member = member or ctx.author
        
        embed = discord.Embed(
            title=f"🖼️ {member.name}'s Avatar",
            color=discord.Color.blue()
        )
        
        embed.set_image(url=member.display_avatar.url)
        embed.add_field(
            name="Download",
            value=f"[Click here]({member.display_avatar.url})",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)
    
    @commands.command(name='invite')
    async def invite(self, ctx):
        """Get bot invite link
        
        Usage: !invite
        """
        # Generate invite URL with necessary permissions
        permissions = discord.Permissions(
            manage_messages=True,
            read_messages=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            add_reactions=True,
            manage_roles=True
        )
        
        invite_url = discord.utils.oauth_url(
            self.bot.user.id,
            permissions=permissions
        )
        
        embed = discord.Embed(
            title="🤖 Invite Me!",
            description=f"Click [here]({invite_url}) to invite me to your server!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📋 Features",
            value="• Server Management\n• Economy System\n• Jobs & Market\n• And more!",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.name}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    """Load the General cog"""
    await bot.add_cog(General(bot))
    logger.info("General cog loaded")
