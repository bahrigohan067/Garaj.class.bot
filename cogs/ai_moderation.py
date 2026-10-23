import discord
from discord.ext import commands
import aiohttp
import json
import re
import datetime
import pytz
import config

TZ = pytz.timezone("Europe/Istanbul")

# Yaygın Türkçe küfür, hakaret ve argo kalıpları (Hızlı ve API bağımsız yerel yedek katman)
LOCAL_BAD_WORDS = [
    r"\bamk\b", r"\baq\b", r"\bamq\b", r"\bamına\b", r"\bamina\b", r"\bamcık\b", r"\bamcik\b",
    r"\bsik\b", r"\bsik[a-zıiğüşöç]*", r"\bsikeyim\b", r"\bsikerim\b", r"\bsikik\b", r"\bsikiş\b",
    r"\byarrak\b", r"\byarr[a-zıiğüşöç]*", r"\byarak\b",
    r"\bpiç\b", r"\bpic\b", r"\borospu\b", r"\boro[sş]pu[a-zıiğüşöç]*", r"\boç\b", r"\boc\b", r"\bo\.ç\b",
    r"\bgöt\b", r"\bgot\b", r"\bgötveren\b", r"\bgotveren\b", r"\bgötlek\b", r"\bgotlek\b",
    r"\bpezevenk\b", r"\bkahpe\b", r"\bşerefsiz\b", r"\bserefsiz\b", r"\bhaysiyetsiz\b", r"\bnamussuz\b",
    r"\banneni\b", r"\bananı\b", r"\banani\b", r"\bac드\b", r"\bbacı[a-zıiğüşöç]*", r"\bsülale[a-zıiğüşöç]*",
    r"\bsg\b", r"\bsiktir\b", r"\bsiktir[a-zıiğüşöç]*", r"\bsktr\b",
    r"\byavşak\b", r"\byavsak\b", r"\bdalyarak\b", r"\btaşak\b", r"\btasak\b", r"\bdaşşak\b", r"\bdassak\b",
    r"\bpuşt\b", r"\bpust\b", r"\bdomal\b", r"\bdomalt[a-zıiğüşöç]*", r"\bsürtük\b", r"\bsurtuk\b",
    r"\bibne\b", r"\bipne\b", r"\bkaşar\b", r"\bkasar\b", r"\bgavat\b", r"\bkaltak\b", r"\bgerizekalı\b",
    r"\bgerizekali\b", r"\baptal\b", r"\bsalak\b", r"\bmal\b"
]

def check_local_bad_words(text: str):
    """Metinde yerel filtreye takılan küfür/argo olup olmadığını denetler."""
    clean_text = text.lower()
    # Karakter uzatmalarını teke indir (ör: sssiiikkk -> sik)
    clean_text = re.sub(r'(.)\1{2,}', r'\1', clean_text)
    
    found = []
    for pattern in LOCAL_BAD_WORDS:
        match = re.search(pattern, clean_text, re.IGNORECASE)
        if match:
            found.append(match.group(0))
            
    if found:
        return {
            "is_inappropriate": True,
            "category": "Küfür / Argo",
            "detected_words": list(set(found)),
            "reason": "Mesajda sunucu kurallarına aykırı argo veya küfür ifadesi tespit edildi."
        }
    return None

class AIModeration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()
        print("[AI Moderation] Yapay Zeka küfür ve argo denetim modülü aktif edildi.")

    async def cog_unload(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def analyze_with_ai(self, text: str):
        """Gemini AI API kullanarak mesajdaki uygunsuzluk/küfür/argo durumunu analiz eder."""
        api_key = getattr(config, "GEMINI_API_KEY", "")
        
        # Önce hızlı yerel kontrol yap; bariz bir küfür varsa beklemeden dön
        local_result = check_local_bad_words(text)
        if local_result:
            return local_result

        # Eğer API anahtarı girilmemişse yerel filtre sonucunu döndür
        if not api_key:
            return None

        # Detaylı ve bağlamsal kontrol için Gemini Flash API çağrısı
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        prompt = (
            "Sen bir Discord topluluk sunucusu için Türkçe argo, küfür, hakaret, aşağılama ve toksisite denetleyicisisin.\n"
            "Verilen mesajı tarafsızca analiz et. Eğer mesajda küfür, gizlenmiş küfür, ağır hakaret veya rencide edici kaba argo varsa tespit et.\n"
            "Gündelik doğal sohbetleri ('lan', 'ya', 'hadi', 'oha' gibi hafif ünlemleri) küfür sayma.\n\n"
            "SADECE ve SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir metin veya markdown ekleme:\n"
            "{\n"
            '  "is_inappropriate": true veya false,\n'
            '  "category": "Küfür" veya "Argo" veya "Hakaret" veya "Temiz",\n'
            '  "detected_words": ["tespit edilen uygunsuz ifadeler"],\n'
            '  "reason": "Kısa Türkçe gerekçe açıklaması"\n'
            "}\n\n"
            f'Mesaj: "{text}"'
        )

        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "response_mime_type": "application/json"
            }
        }

        try:
            if not self.session or self.session.closed:
                self.session = aiohttp.ClientSession()
            async with self.session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        result = json.loads(content_text.strip())
                        if result.get("is_inappropriate"):
                            return result
                else:
                    print(f"[AI Moderation] Gemini API Yanıt Kodu: {response.status}")
        except Exception as e:
            print(f"[AI Moderation] Gemini API Hatası: {e}")

        return local_result

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Botları ve özel mesajları yoksay
        if message.author.bot or not message.guild:
            return

        # Mesaj içeriği boşsa geç
        if not message.content or not message.content.strip():
            return

        # Log kanalında yazılanları denetleme (döngüyü önlemek için)
        if message.channel.id == getattr(config, "CH_AI_MOD_LOG", 0):
            return

        # Yapay zeka & filtre analizi
        analysis = await self.analyze_with_ai(message.content)
        if not analysis or not analysis.get("is_inappropriate"):
            return

        detected_words = analysis.get("detected_words", [])
        detected_str = ", ".join(detected_words) if detected_words else "Argo / Küfür tespiti"
        category = analysis.get("category", "Küfür / Argo")
        reason = analysis.get("reason", "Topluluk kurallarına aykırı uygunsuz ifade kullanımı.")

        # ---------------- 1. KULLANICIYA ÖZEL DM UYARISI (TURUNCU) ----------------
        dm_embed = discord.Embed(
            title="⚠️ Uygunsuz İçerik Bildirimi",
            description=(
                f"Sayın {message.author.mention},\n\n"
                "**GarajClass** sunucusunda gönderdiğiniz mesajda sunucu kurallarına aykırı "
                "**küfür, hakaret veya uygunsuz argo** tespit edilmiştir.\n\n"
                "Lütfen topluluk huzurunu ve sohbet ortamını korumak adına kullandığınız kelimelere "
                "özen gösteriniz. İhlalin devamı durumunda yetkili ekip tarafından cezai işlem uygulanabilir."
            ),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(TZ)
        )

        # Attığı mesajı göster
        content_preview = message.content
        if len(content_preview) > 900:
            content_preview = content_preview[:900] + "..."
        dm_embed.add_field(name="💬 Attığınız Mesaj:", value=f">>> {content_preview}", inline=False)
        dm_embed.add_field(name="📌 Tespit Edilen Tür:", value=f"`{category}` (İfade: `{detected_str}`)", inline=True)
        dm_embed.add_field(name="📍 Gönderilen Kanal:", value=f"#{message.channel.name}", inline=True)
        dm_embed.set_footer(text="GarajClass Otomatik Moderasyon & Güvenlik Sistemi")

        try:
            await message.author.send(embed=dm_embed)
        except Exception:
            # Kullanıcının DM kutusu kapalıysa hata vermeden devam et
            pass

        # ---------------- 2. YETKİLİ LOG KANALINA BİLDİRİM (KIRMIZI) ----------------
        log_channel_id = getattr(config, "CH_AI_MOD_LOG", 0)
        log_channel = message.guild.get_channel(log_channel_id)
        if not log_channel:
            try:
                log_channel = await message.guild.fetch_channel(log_channel_id)
            except Exception:
                log_channel = None

        if log_channel:
            log_embed = discord.Embed(
                title="🚨 Yapay Zeka Uygunsuz İçerik Tespiti",
                description="Sunucuda kural dışı küfür/argo veya uygunsuz dil kullanımı algılandı.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.now(TZ)
            )
            log_embed.set_thumbnail(url=message.author.display_avatar.url)

            # Kullanıcı Bilgisi
            log_embed.add_field(
                name="👤 Gönderen Kullanıcı",
                value=f"{message.author.mention}\n`{message.author.name}` (ID: `{message.author.id}`)",
                inline=True
            )

            # Kanal Bilgisi
            log_embed.add_field(
                name="📍 Kanal",
                value=f"{message.channel.mention}\n`#{message.channel.name}`",
                inline=True
            )

            # Tespit Türü
            log_embed.add_field(
                name="🔍 Kategori & İfade",
                value=f"**{category}**\n`{detected_str}`",
                inline=True
            )

            # Gönderilen Mesajın Tamamı
            log_embed.add_field(
                name="💬 Gönderilen Mesaj",
                value=f">>> {content_preview}",
                inline=False
            )

            # Yapay Zeka Gerekçesi
            log_embed.add_field(
                name="🤖 Analiz / Açıklama",
                value=reason,
                inline=False
            )

            # Hızlı Bağlantı ve Durum Notu
            log_embed.add_field(
                name="🔗 Mesaja Ulaş",
                value=f"[Mesaja Gitmek İçin Tıklayın]({message.jump_url})",
                inline=True
            )
            log_embed.add_field(
                name="⚡ Uygulanan İşlem",
                value="*Mesaj silinmedi. Kullanıcıya özel DM uyarısı gönderildi.*",
                inline=True
            )

            log_embed.set_footer(
                text="GarajClass AI Moderasyon Servisi • v1.1",
                icon_url=message.guild.icon.url if message.guild.icon else None
            )

            try:
                await log_channel.send(embed=log_embed)
            except Exception as e:
                print(f"[AI Moderation] Log gönderim hatası: {e}")

async def setup(bot):
    await bot.add_cog(AIModeration(bot))
