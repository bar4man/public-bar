import discord
from discord.ext import commands

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="testcmd")
    async def test_command(self, ctx):
        await ctx.send("✅ Test command works!")
    
    @commands.command(name="testprices")
    async def test_prices(self, ctx):
        await ctx.send("📊 Test prices command works!")

async def setup(bot):
    await bot.add_cog(TestCog(bot))
