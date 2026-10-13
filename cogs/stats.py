import discord
from discord.ext import commands, tasks
import config
import database
import datetime
import pytz

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.staff_roles = [config.ROLE_FOUNDER, config.ROLE_HEAD_ADMIN, config.ROLE_MODERATOR, config.ROLE_SUPPORT_TEAM, config.ROLE_TRIAL_MOD]
        self.tz = pytz.timezone("Europe/Istanbul")
        self.tracker_loop.start()
        self.leaderboard_loop.start()

    def cog_unload(self):
        self.tracker_loop.cancel()
        self.leaderboard_loop.cancel()

    @tasks.loop(minutes=1)
    async def tracker_loop(self):
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
            
        for member in guild.members:
            if member.bot:
                continue
                
            # Check if staff
            if any(r.id in self.staff_roles for r in member.roles):
                # Check discord activity
                if member.status != discord.Status.offline:
                    database.add_discord_active_time(member.id, 60)
                    
                # Check voice activity
                if member.voice and member.voice.channel:
                    database.add_voice_time(member.id, 60)

    @tracker_loop.before_loop
    async def before_tracker(self):
        await self.bot.wait_until_ready()

    def generate_progress_bar(self, current, target, length=10):
        if target == 0:
            return "🟩" * length
        percentage = min(current / target, 1.0)
        filled = int(percentage * length)
        empty = length - filled
        return "🟩" * filled + "⬜" * empty

    @tasks.loop(minutes=1)
    async def leaderboard_loop(self):
        now = datetime.datetime.now(self.tz)
        # Check if it's 00:00 (midnight)
        if now.hour == 0 and now.minute == 0:
            await self.post_leaderboard()
            
    @leaderboard_loop.before_loop
    async def before_leaderboard(self):
        await self.bot.wait_until_ready()
        
    async def post_leaderboard(self):
        # We need the date for "yesterday" since it's 00:00 now
        yesterday = (datetime.datetime.now(self.tz) - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        stats = database.get_stats_for_date(yesterday)
        
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
            
        channel = guild.get_channel(config.CH_ISLEMLER) # Or any specific leaderboard channel, user didn't specify. Let's use İşlemler.
        if not channel:
            return
            
        if not stats:
            await channel.send("Dün için kaydedilmiş yetkili verisi bulunamadı.")
            return
            
        embed = discord.Embed(title=f"📊 Günlük Yetkili Tablosu ({yesterday})", color=discord.Color.gold())
        
        for user_id, discord_sec, voice_sec, tickets, supports in stats:
            member = guild.get_member(user_id)
            if not member:
                continue
                
            discord_hours = discord_sec / 3600
            voice_hours = voice_sec / 3600
            
            discord_bar = self.generate_progress_bar(discord_hours, 8)
            voice_bar = self.generate_progress_bar(voice_hours, 5)
            
            val = (
                f"**Discord Aktifliği:** {discord_hours:.1f}/8 Saat\n{discord_bar}\n"
                f"**Ses Aktifliği:** {voice_hours:.1f}/5 Saat\n{voice_bar}\n"
                f"**Kapatılan Ticket:** {tickets}\n"
                f"**Biten Destek:** {supports}"
            )
            embed.add_field(name=member.display_name, value=val, inline=False)
            
        await channel.send(embed=embed)
        
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def zorlaleaderboard(self, ctx):
        """Test amaçlı günlük tabloyu zorla gönderir (Bugünün verisi)."""
        today = datetime.datetime.now(self.tz).strftime("%Y-%m-%d")
        stats = database.get_stats_for_date(today)
        
        if not stats:
            await ctx.send("Bugün için kaydedilmiş yetkili verisi bulunamadı.")
            return
            
        embed = discord.Embed(title=f"📊 Günlük Yetkili Tablosu ({today})", color=discord.Color.gold())
        
        for user_id, discord_sec, voice_sec, tickets, supports in stats:
            member = ctx.guild.get_member(user_id)
            if not member:
                continue
                
            discord_hours = discord_sec / 3600
            voice_hours = voice_sec / 3600
            
            discord_bar = self.generate_progress_bar(discord_hours, 8)
            voice_bar = self.generate_progress_bar(voice_hours, 5)
            
            val = (
                f"**Discord Aktifliği:** {discord_hours:.1f}/8 Saat\n{discord_bar}\n"
                f"**Ses Aktifliği:** {voice_hours:.1f}/5 Saat\n{voice_bar}\n"
                f"**Kapatılan Ticket:** {tickets}\n"
                f"**Biten Destek:** {supports}"
            )
            embed.add_field(name=member.display_name, value=val, inline=False)
            
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Stats(bot))
