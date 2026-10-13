import discord
from discord.ext import commands
import config
import datetime

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != config.GUILD_ID:
            return
            
        # Give unverified role
        unverified_role = member.guild.get_role(config.ROLE_UNVERIFIED)
        if unverified_role:
            await member.add_roles(unverified_role)

        # Welcome message, send it to CH_WELCOME
        channel = member.guild.get_channel(config.CH_WELCOME)
            
        if channel:
            join_date = member.joined_at.strftime("%d/%m/%Y")
            
            embed = discord.Embed(
                title="✨ Sunucumuza Hoş Geldin!",
                description=f"Merhaba {member.mention}\n\n**{member.guild.name}** ailesine katıldığın için çok mutluyuz.\nSeninle birlikte artık **{member.guild.member_count}** kişiyiz!\n\n📜 [Kuralları okumayı unutma](https://discord.com/channels/1275120691863355487/1520419754509205535)\n💬 Sohbete katılmaktan çekinme\n🎮 İyi eğlenceler dileriz!",
                color=discord.Color.gold()
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Katılma tarihi: {join_date}", icon_url=member.guild.icon.url if member.guild.icon else None)
            
            await channel.send(content=member.mention, embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
