import discord
from discord.ext import commands, tasks
import config

class MemberCount(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_channel.start()

    def cog_unload(self):
        self.update_channel.cancel()

    async def do_update(self, guild):
        channel = guild.get_channel(config.CH_MEMBER_COUNT)
        if channel:
            # Ses veya metin kanalı ismini günceller
            new_name = f"══▐ {guild.member_count} KATILIMCI▐ ══"
            if channel.name != new_name:
                try:
                    await channel.edit(name=new_name)
                except discord.HTTPException:
                    pass # Rate limited (Discord izin vermiyor, 10 dk limiti vs.) veya yetki eksikliği

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id == config.GUILD_ID:
            await self.do_update(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id == config.GUILD_ID:
            await self.do_update(member.guild)

    # Discord'un kanal ismi değiştirme limiti kanal başına 10 dakikada 2 defadır.
    # Bu yüzden eğer anlık değiştirmelerde limite takılırsak, her 10 dakikada bir kontrol edip kesin güncelliyoruz.
    @tasks.loop(minutes=10)
    async def update_channel(self):
        guild = self.bot.get_guild(config.GUILD_ID)
        if guild:
            await self.do_update(guild)

    @update_channel.before_loop
    async def before_update(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MemberCount(bot))
