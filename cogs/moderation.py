import discord
from discord.ext import commands
from discord import app_commands
import config
import datetime
import re

def parse_duration(duration_str):
    """Süre stringini (örn: 10m, 1h, 1d) datetime.timedelta'ya çevirir."""
    # Sadece sayı girildiyse varsayılan olarak dakika kabul edelim
    if duration_str.isdigit():
        return datetime.timedelta(minutes=int(duration_str))
        
    match = re.match(r'^(\d+)(s|m|h|d|w)$', duration_str.lower())
    if not match:
        return None
        
    amount = int(match.group(1))
    unit = match.group(2)
    
    if unit == 's':
        return datetime.timedelta(seconds=amount)
    elif unit == 'm':
        return datetime.timedelta(minutes=amount)
    elif unit == 'h':
        return datetime.timedelta(hours=amount)
    elif unit == 'd':
        return datetime.timedelta(days=amount)
    elif unit == 'w':
        return datetime.timedelta(weeks=amount)
    
    return None

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def log_action(self, interaction: discord.Interaction, action: str, member: discord.Member, reason: str, extra: str = None):
        log_channel = interaction.guild.get_channel(config.CH_ISLEMLER)
        if not log_channel:
            return
            
        embed = discord.Embed(
            title=f"Yetkili İşlemi: {action}",
            color=discord.Color.red() if action in ["Ban", "Kick"] else discord.Color.orange(),
            timestamp=datetime.datetime.now()
        )
        embed.add_field(name="İşlem Yapılan Kullanıcı", value=f"{member.mention} ({member.id})", inline=False)
        embed.add_field(name="İşlemi Yapan Yetkili", value=interaction.user.mention, inline=False)
        embed.add_field(name="Sebep", value=reason, inline=False)
        
        if extra:
            embed.add_field(name="Ekstra Bilgi", value=extra, inline=False)
            
        await log_channel.send(embed=embed)

    @app_commands.command(name="ban", description="Belirtilen kişiyi belirtilen sebeple sunucudan banlar.")
    @app_commands.describe(kisi="Banlanacak kullanıcı", sebep="Banlanma sebebi")
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, kisi: discord.Member, sebep: str):
        if kisi.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Bu kullanıcıyı banlamak için yeterli yetkiye sahip değilsiniz (Rolü sizden yüksek veya eşit).", ephemeral=True)
            return
            
        try:
            await kisi.ban(reason=f"{interaction.user}: {sebep}")
            await interaction.response.send_message(f"{kisi.mention} başarıyla banlandı.", ephemeral=True)
            await self.log_action(interaction, "Ban", kisi, sebep)
        except discord.Forbidden:
            await interaction.response.send_message("Botun bu kullanıcıyı banlamak için yeterli yetkisi yok.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Bir hata oluştu: {e}", ephemeral=True)

    @app_commands.command(name="kick", description="Belirtilen kişiyi belirtilen sebeple sunucudan atar (kick).")
    @app_commands.describe(kisi="Atılacak kullanıcı", sebep="Atılma sebebi")
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, kisi: discord.Member, sebep: str):
        if kisi.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Bu kullanıcıyı sunucudan atmak için yeterli yetkiye sahip değilsiniz.", ephemeral=True)
            return
            
        try:
            await kisi.kick(reason=f"{interaction.user}: {sebep}")
            await interaction.response.send_message(f"{kisi.mention} başarıyla sunucudan atıldı.", ephemeral=True)
            await self.log_action(interaction, "Kick", kisi, sebep)
        except discord.Forbidden:
            await interaction.response.send_message("Botun bu kullanıcıyı sunucudan atmak için yeterli yetkisi yok.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Bir hata oluştu: {e}", ephemeral=True)

    @app_commands.command(name="timeout", description="Belirtilen kişiyi belirtilen süreyle zaman aşımına (timeout) uğratır.")
    @app_commands.describe(kisi="Timeout atılacak kullanıcı", sure="Süre (Örn: 10m, 1h, 1d) veya dakika sayısı", sebep="Timeout sebebi")
    @app_commands.default_permissions(moderate_members=True)
    async def timeout(self, interaction: discord.Interaction, kisi: discord.Member, sure: str, sebep: str = "Belirtilmedi"):
        if kisi.top_role >= interaction.user.top_role:
            await interaction.response.send_message("Bu kullanıcıya timeout atmak için yeterli yetkiye sahip değilsiniz.", ephemeral=True)
            return
            
        duration = parse_duration(sure)
        if not duration:
            await interaction.response.send_message("Geçersiz süre formatı! Lütfen geçerli bir format girin (Örn: `10m`, `2h`, `1d` veya sadece dakika olarak sayı).", ephemeral=True)
            return
            
        if duration > datetime.timedelta(days=28):
            await interaction.response.send_message("Discord API kısıtlamaları gereği en fazla 28 gün (28d) timeout atabilirsiniz.", ephemeral=True)
            return
            
        try:
            # Until arg expects a timezone-aware datetime or None
            until = discord.utils.utcnow() + duration
            await kisi.timeout(until, reason=f"{interaction.user}: {sebep}")
            await interaction.response.send_message(f"{kisi.mention} başarıyla {sure} boyunca susturuldu.", ephemeral=True)
            await self.log_action(interaction, "Timeout", kisi, sebep, extra=f"Süre: {sure}")
        except discord.Forbidden:
            await interaction.response.send_message("Botun bu kullanıcıya timeout atmak için yeterli yetkisi yok.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Bir hata oluştu: {e}", ephemeral=True)


    @commands.command(name="temizle")
    @commands.has_permissions(manage_messages=True)
    async def temizle(self, ctx, miktar: int):
        """Belirtilen sayıda mesajı siler."""
        if miktar <= 0:
            await ctx.send("Lütfen silinecek mesaj sayısını 0'dan büyük girin.")
            return
            
        try:
            # +1 for deleting the command message itself
            deleted = await ctx.channel.purge(limit=miktar + 1)
            # Send confirmation and delete it after 3 seconds
            await ctx.send(f"🧹 Başarıyla **{len(deleted)-1}** mesaj silindi.", delete_after=3.0)
            
            # Log to İşlemler
            log_channel = ctx.guild.get_channel(config.CH_ISLEMLER)
            if log_channel:
                embed = discord.Embed(
                    title="Yetkili İşlemi: Mesaj Silme",
                    color=discord.Color.orange(),
                    timestamp=datetime.datetime.now()
                )
                embed.add_field(name="Kanal", value=ctx.channel.mention, inline=False)
                embed.add_field(name="İşlemi Yapan", value=ctx.author.mention, inline=False)
                embed.add_field(name="Silinen Mesaj Sayısı", value=str(len(deleted)-1), inline=False)
                await log_channel.send(embed=embed)
                
        except discord.Forbidden:
            await ctx.send("Mesajları silmek için yeterli yetkim yok.")
        except Exception as e:
            await ctx.send(f"Bir hata oluştu: {e}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
