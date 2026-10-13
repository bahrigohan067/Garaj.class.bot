import discord
from discord.ext import commands
import config
import datetime
import time

class AntiSpam(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.user_messages = {} # user_id: [timestamp1, timestamp2, ...]
        
        # Ayarlar: 5 saniye içinde 5 mesaj atılırsa spam kabul edilir
        self.SPAM_LIMIT = 5
        self.TIME_WINDOW = 5 # saniye
        self.TIMEOUT_DURATION = 5 # dakika

    @commands.Cog.listener()
    async def on_message(self, message):
        # Botları ve DM'leri yoksay
        if message.author.bot or not message.guild:
            return
            
        # Yetkilileri yoksay (Yanlışlıkla timeout yememeleri için)
        staff_roles = [
            config.ROLE_FOUNDER, config.ROLE_HEAD_ADMIN, config.ROLE_MODERATOR, 
            config.ROLE_SUPPORT_TEAM, config.ROLE_TRIAL_MOD, config.ROLE_SENIOR_STAFF, 
            config.ROLE_STAFF, config.ROLE_NEW_TRIAL_STAFF
        ]
        
        if any(r.id in staff_roles for r in message.author.roles):
            return
            
        user_id = message.author.id
        now = time.time()
        
        # Kullanıcının listesini oluştur veya zaman aşımına uğramış eski mesajları temizle
        if user_id not in self.user_messages:
            self.user_messages[user_id] = []
            
        self.user_messages[user_id] = [ts for ts in self.user_messages[user_id] if now - ts <= self.TIME_WINDOW]
        
        # Şu anki mesajın zamanını ekle
        self.user_messages[user_id].append(now)
        
        # Eğer belirtilen süre içinde limite ulaşılmışsa
        if len(self.user_messages[user_id]) >= self.SPAM_LIMIT:
            # İşlemin art arda defalarca tetiklenmesini önlemek için listeyi sıfırlıyoruz
            self.user_messages[user_id] = []
            
            try:
                # 1. Timeout uygula
                duration = datetime.timedelta(minutes=self.TIMEOUT_DURATION)
                until = discord.utils.utcnow() + duration
                await message.author.timeout(until, reason="Otomatik İşlem: Spam Koruması")
                
                # 2. Özelden (DM) uyar
                try:
                    await message.author.send(
                        f"🛑 **Uyarı:** **{message.guild.name}** sunucusunda çok hızlı mesaj gönderdiğiniz için (Spam) "
                        f"**{self.TIMEOUT_DURATION} dakika** boyunca susturuldunuz.\n"
                        "Lütfen mesaj gönderirken biraz daha yavaş olun ve kurallara uyun."
                    )
                except discord.Forbidden:
                    pass # Kullanıcının DM'leri kapalı
                
                # 3. Attığı son spam mesajlarını temizle (İsteğe bağlı, kanalı temiz tutar)
                try:
                    await message.channel.purge(limit=self.SPAM_LIMIT, check=lambda m: m.author == message.author)
                except:
                    pass
                
                # 4. İşlemler kanalına Log düş
                log_channel = message.guild.get_channel(config.CH_ISLEMLER)
                if log_channel:
                    embed = discord.Embed(
                        title="🛡️ Otomatik İşlem: Spam Koruması",
                        color=discord.Color.dark_red(),
                        timestamp=datetime.datetime.now()
                    )
                    embed.add_field(name="Kullanıcı", value=f"{message.author.mention} ({message.author.id})", inline=False)
                    embed.add_field(name="Kanal", value=message.channel.mention, inline=False)
                    embed.add_field(name="Ceza", value=f"{self.TIMEOUT_DURATION} Dakika Timeout", inline=False)
                    embed.add_field(name="Sebep", value=f"{self.TIME_WINDOW} saniye içinde {self.SPAM_LIMIT} mesaj gönderdi.", inline=False)
                    
                    await log_channel.send(embed=embed)
                    
            except discord.Forbidden:
                pass # Botun timeout atmaya veya mesaj silmeye yetkisi yok

async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
