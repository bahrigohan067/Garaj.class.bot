import datetime
import os
import re
import time
import pytz
import discord
from discord.ext import commands, tasks

import config

TZ = pytz.timezone("Europe/Istanbul")

# ==================== MERKEZİ AYARLAR (CONFIG) ====================
CONFIG = {
    "WINDOW_SECONDS": 30,             # Çok kanallı spam takip penceresi (saniye)
    "CHANNEL_THRESHOLD": 3,           # Aynı mesajın görülmesi gereken farklı kanal sayısı
    "MIN_MULTI_CHANNEL_LEN": 10,      # Kural 4 için en az normalize mesaj uzunluğu
    "MAX_SIGNATURE_LEN": 200,         # Karşılaştırma için alınan maksimum karakter sayısı
    "SCORE_EVERYONE": 2,              # Kural 1: @everyone veya @here puanı
    "SCORE_LINK": 1,                  # Kural 2: Link veya davet puanı
    "SCORE_SCAM": 1,                  # Kural 3: Dolandırıcılık kelimesi puanı
    "SCORE_MULTI_CHANNEL": 3,         # Kural 4: Çok kanallı aynı mesaj puanı
    "DELETE_SCORE_THRESHOLD": 2,      # Sadece mesaj silme eşiği
    "PUNISH_SCORE_THRESHOLD": 3,      # Tam ceza (toplu silme + timeout + DM + log) eşiği
    "TIMEOUT_HOURS": 24,              # Zaman aşımı süresi (saat)
    "TIMEOUT_REASON": "Şüpheli hesap hareketi",
    "PUNISH_COOLDOWN_SECONDS": 600,   # Aynı kullanıcıya tekrar ceza vermeme süresi (10 dakika)
    "CLEANUP_INTERVAL_SECONDS": 60,   # RAM temizlik periyodu (saniye)
}

# ==================== TESPİT KALIPLARI (REGEX SABİTLERİ) ====================
EVERYONE_RE = re.compile(r"@(everyone|here)\b", re.IGNORECASE)

LINK_RE = re.compile(
    r"(https?://\S+|discord\.gg/\S+|discord(?:app)?\.com/invite/\S+)",
    re.IGNORECASE,
)

SCAM_RE = re.compile(
    r"\b(nitro|free|gift|steam|airdrop|giveaway|claim|bedava|hediye|çekiliş|cekilis|kazandın|kazandin)\b",
    re.IGNORECASE,
)


# ==================== YARDIMCI FONKSİYONLAR ====================

def normalize_content(content: str) -> str:
    """Mesaj içeriğini küçük harfe çevirir, fazla boşlukları sadeleştirir ve ilk 200 karakteri alır."""
    if not content:
        return ""
    cleaned = re.sub(r"\s+", " ", content).strip().lower()
    return cleaned[: CONFIG["MAX_SIGNATURE_LEN"]]


def get_staff_role_ids() -> set[int]:
    """Yetkili rol ID'lerini env değişkeninden veya config.STAFF_ROLES listesinden okur."""
    env_roles = os.getenv("STAFF_ROLE_IDS", "").strip()
    if env_roles:
        role_ids = set()
        for part in env_roles.split(","):
            part = part.strip()
            if part.isdigit():
                role_ids.add(int(part))
        if role_ids:
            return role_ids
    return set(getattr(config, "STAFF_ROLES", []))


def is_staff(member: discord.Member) -> bool:
    """Kullanıcının muaf yetkili olup olmadığını kontrol eder (Tek noktadan kolayca değiştirilebilir)."""
    if member.guild_permissions.administrator or member.guild_permissions.manage_guild:
        return True
    staff_role_ids = get_staff_role_ids()
    return any(role.id in staff_role_ids for role in member.roles)


def can_moderate_member(guild: discord.Guild, member: discord.Member) -> bool:
    """Botun hedef üyeye timeout (zaman aşımı) uygulayıp uygulayamayacağını kontrol eder."""
    me = guild.me
    if not me:
        return False
    if not me.guild_permissions.moderate_members:
        return False
    if member.id == guild.owner_id:
        return False
    if member.guild_permissions.administrator:
        return False
    if me.top_role <= member.top_role:
        return False
    return True


# ==================== ANA ANTI-HIJACK COG MODÜLÜ ====================

class AntiHijackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # user_id -> list[dict(channel_id, message_id, timestamp, signature)]
        self.user_messages: dict[int, list[dict]] = {}
        # user_id -> ceza_zamani (float)
        self.punished_users: dict[int, float] = {}

    async def cog_load(self):
        """Cog yüklendiğinde RAM temizlik döngüsünü güvenli şekilde başlatır."""
        if not self.cleanup_loop.is_running():
            self.cleanup_loop.start()

    async def cog_unload(self):
        """Cog kaldırıldığında RAM temizlik döngüsünü durdurur."""
        if self.cleanup_loop.is_running():
            self.cleanup_loop.cancel()

    @tasks.loop(seconds=CONFIG["CLEANUP_INTERVAL_SECONDS"])
    async def cleanup_loop(self):
        """Her 60 saniyede bir 30 saniyeden eski mesaj kayıtlarını ve 10 dakikayı geçen ceza kayıtlarını temizler."""
        try:
            now = time.monotonic()
            window_cutoff = now - CONFIG["WINDOW_SECONDS"]
            cooldown_cutoff = now - CONFIG["PUNISH_COOLDOWN_SECONDS"]

            # Eski mesaj kayıtlarını temizle
            expired_users = []
            for user_id, records in self.user_messages.items():
                fresh = [r for r in records if r["timestamp"] >= window_cutoff]
                if fresh:
                    self.user_messages[user_id] = fresh
                else:
                    expired_users.append(user_id)

            for user_id in expired_users:
                self.user_messages.pop(user_id, None)

            # Süresi dolan ceza kayıtlarını temizle
            expired_punished = [
                uid for uid, ts in self.punished_users.items() if ts < cooldown_cutoff
            ]
            for uid in expired_punished:
                self.punished_users.pop(uid, None)
        except Exception as err:
            print(f"[AntiHijack] Bellek temizleme hatası: {err}")

    def record_and_count_channels(
        self,
        user_id: int,
        channel_id: int,
        message_id: int,
        signature: str,
        now: float,
    ) -> int:
        """Kullanıcının son 30 saniyedeki mesajlarını günceller ve aynı mesajın kaç farklı kanalda atıldığını döndürür."""
        cutoff = now - CONFIG["WINDOW_SECONDS"]
        records = self.user_messages.get(user_id, [])
        records = [r for r in records if r["timestamp"] >= cutoff]

        records.append({
            "channel_id": channel_id,
            "message_id": message_id,
            "timestamp": now,
            "signature": signature,
        })
        self.user_messages[user_id] = records

        # Kural 4: Normalize edilmiş içerik boşsa veya 10 karakterden kısaysa çok kanallı kuralı uygulama
        if len(signature) < CONFIG["MIN_MULTI_CHANNEL_LEN"]:
            return 0

        matching_channels = {
            r["channel_id"] for r in records if r["signature"] == signature
        }
        return len(matching_channels)

    def calculate_risk_score(
        self,
        content: str,
        signature: str,
        distinct_channels: int,
        staff_exempt: bool,
    ) -> tuple[int, list[str]]:
        """Mesaj için risk skorunu ve tetiklenen kuralların açıklama listesini hesaplar."""
        score = 0
        reasons: list[str] = []

        # Kural 1, 2 ve 3 yalnızca yetkili OLMAYAN üyelere uygulanır
        if not staff_exempt:
            if EVERYONE_RE.search(content):
                score += CONFIG["SCORE_EVERYONE"]
                reasons.append(f"@everyone / @here kullanımı (+{CONFIG['SCORE_EVERYONE']})")

            if LINK_RE.search(content):
                score += CONFIG["SCORE_LINK"]
                reasons.append(f"Bağlantı / davet linki (+{CONFIG['SCORE_LINK']})")

            if SCAM_RE.search(content):
                score += CONFIG["SCORE_SCAM"]
                reasons.append(f"Dolandırıcılık / şüpheli kelime (+{CONFIG['SCORE_SCAM']})")

        # Kural 4 (Çok kanallı aynı mesaj) yetkililer DAHİL herkese uygulanır (en az 10 karakter şartıyla)
        if (
            len(signature) >= CONFIG["MIN_MULTI_CHANNEL_LEN"]
            and distinct_channels >= CONFIG["CHANNEL_THRESHOLD"]
        ):
            score += CONFIG["SCORE_MULTI_CHANNEL"]
            reasons.append(
                f"{CONFIG['WINDOW_SECONDS']} sn içinde {distinct_channels} farklı kanalda aynı mesaj (+{CONFIG['SCORE_MULTI_CHANNEL']})"
            )

        return score, reasons

    async def safe_delete_partial(self, guild: discord.Guild, channel_id: int, message_id: int) -> bool:
        """fetch_message kullanmadan PartialMessage ile hızlıca mesajı siler."""
        try:
            channel = guild.get_channel(channel_id)
            if not channel:
                return False
            partial_msg = channel.get_partial_message(message_id)
            await partial_msg.delete()
            return True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return False
        except Exception:
            return False

    async def delete_recent_user_messages(self, guild: discord.Guild, user_id: int, now: float) -> int:
        """Kullanıcının son 30 saniye içinde attığı tüm kayıtlı mesajları PartialMessage ile siler."""
        cutoff = now - CONFIG["WINDOW_SECONDS"]
        records = self.user_messages.pop(user_id, [])
        deleted_count = 0

        for rec in records:
            if rec["timestamp"] >= cutoff:
                ok = await self.safe_delete_partial(guild, rec["channel_id"], rec["message_id"])
                if ok:
                    deleted_count += 1

        return deleted_count

    async def apply_member_timeout(self, guild: discord.Guild, member: discord.Member) -> str:
        """Kullanıcıya 24 saat timeout uygular; yetki/rol sırası yetersizse denemeden durumu döndürür."""
        if not can_moderate_member(guild, member):
            return "❌ Yapılamadı (Yetki / Rol Sırası Yetersiz)"

        try:
            duration = datetime.timedelta(hours=CONFIG["TIMEOUT_HOURS"])
            await member.timeout(duration, reason=CONFIG["TIMEOUT_REASON"])
            return f"✅ Başarılı ({CONFIG['TIMEOUT_HOURS']} Saat)"
        except (discord.Forbidden, discord.HTTPException):
            return "❌ Yapılamadı (Discord API / Yetki Hatası)"
        except Exception:
            return "❌ Yapılamadı (Bilinmeyen Hata)"

    async def send_hijack_dm(self, member: discord.Member, guild_name: str):
        """Kullanıcıya hesabının çalınmış olabileceğine dair güvenlik uyarısı DM'i gönderir."""
        try:
            embed = discord.Embed(
                title="⚠️ Güvenlik Uyarısı: Şüpheli Hesap Hareketi",
                description=(
                    f"Merhaba {member.mention}, **{guild_name}** sunucusunda hesabınızdan "
                    f"şüpheli spam / dolandırıcılık mesajları gönderildiği tespit edildi.\n\n"
                    f"***\n\n"
                    f"Hesabınızın güvenliği ve sunucu düzeni için hesabınız geçici olarak "
                    f"**{CONFIG['TIMEOUT_HOURS']} saat** zaman aşımına (susturmaya) alındı.\n\n"
                    f"### 🔐 Hesabınız Çalınmış Olabilir! Hemen Şunları Yapın:\n"
                    f"1. **Şifrenizi Değiştirin:** Discord şifrenizi hemen güçlü ve yeni bir şifreyle güncelleyin.\n"
                    f"2. **İki Aşamalı Doğrulamayı (2FA) Açın:** Hesabınıza ekstra koruma ekleyin.\n"
                    f"3. **Yetkili Uygulamaları Kontrol Edin:** *Kullanıcı Ayarları ➔ Yetkili Uygulamalar* bölümünden tanımadığınız uygulamaları kaldırın.\n"
                    f"4. **Cihazları Kontrol Edin:** *Kullanıcı Ayarları ➔ Cihazlar* sekmesinden tanımadığınız tüm oturumlardan çıkış yapın."
                ),
                color=discord.Color.orange(),
                timestamp=datetime.datetime.now(TZ),
            )
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            # Kullanıcının DM kutusu kapalıysa sessizce geç
            pass
        except Exception:
            pass

    async def send_security_log(
        self,
        guild: discord.Guild,
        member: discord.Member,
        channel: discord.abc.GuildChannel,
        score: int,
        deleted_count: int,
        timeout_status: str,
        reasons: list[str],
        raw_content: str,
    ):
        """Güvenlik log kanalına kırmızı alarm embed'i gönderir ve sadece yetkili rollerini etiketler."""
        try:
            log_channel_id = int(
                os.getenv("SECURITY_LOG_CHANNEL_ID", str(getattr(config, "CH_SECURITY_LOG", 1565016183277883463)))
            )
            log_channel = guild.get_channel(log_channel_id)
            if not log_channel:
                try:
                    log_channel = await guild.fetch_channel(log_channel_id)
                except Exception:
                    return

            safe_excerpt = (raw_content or "[Görsel / Boş İçerik]").replace("```", "'''")
            if len(safe_excerpt) > 500:
                safe_excerpt = safe_excerpt[:497] + "..."

            reasons_text = "\n".join(f"• {r}" for r in reasons) if reasons else "• Belirtilmedi"

            embed = discord.Embed(
                title="🚨 ÇALINTI HESAP / SPAM SALDIRISI ENGELLENDİ",
                description=(
                    f"👤 **Kullanıcı:** {member.mention} (`{member}`)\n"
                    f"🆔 **Kullanıcı ID:** `{member.id}`\n"
                    f"📍 **Son Mesaj Kanalı:** {channel.mention}\n\n"
                    f"***\n\n"
                    f"📊 **Risk Skoru:** `{score}`\n"
                    f"🗑️ **Silinen Mesaj Sayısı:** `{deleted_count}`\n"
                    f"⏳ **Timeout Durumu:** {timeout_status}\n\n"
                    f"***\n\n"
                    f"### 🔎 Tespit Sebepleri\n"
                    f"{reasons_text}\n\n"
                    f"### 💬 Yakalanan Mesaj İçeriği\n"
                    f"```text\n{safe_excerpt}\n```"
                ),
                color=discord.Color.from_rgb(231, 76, 60),
                timestamp=datetime.datetime.now(TZ),
            )
            if member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"{guild.name} • Anti-Hijack Güvenlik Modülü")

            staff_role_ids = get_staff_role_ids()
            role_mentions = " ".join(f"<@&{rid}>" for rid in sorted(staff_role_ids) if guild.get_role(rid))

            await log_channel.send(
                content=role_mentions if role_mentions else None,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(
                    everyone=False,
                    users=False,
                    roles=True,
                ),
            )
        except Exception as err:
            print(f"[AntiHijack] Log gönderim hatası: {err}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Her mesajı dinler, risk skorunu hesaplar ve eşik aşımında otomatik aksiyon alır."""
        try:
            # Botları, webhook mesajlarını ve sunucu dışı (DM) mesajları yoksay
            if not message.guild or message.author.bot or message.webhook_id is not None:
                return

            if message.guild.id != config.GUILD_ID:
                return

            # Sunucu sahibini muaf tut
            if message.author.id == message.guild.owner_id:
                return

            # Member nesnesini önbellekten al, yoksa fetch et
            member = message.author if isinstance(message.author, discord.Member) else message.guild.get_member(message.author.id)
            if not member:
                try:
                    member = await message.guild.fetch_member(message.author.id)
                except Exception:
                    return

            now = time.monotonic()
            content = message.content or ""
            signature = normalize_content(content)

            # Kayan pencereye mesajı kaydet ve aynı mesajın kaç farklı kanalda atıldığını hesapla
            distinct_channels = self.record_and_count_channels(
                user_id=member.id,
                channel_id=message.channel.id,
                message_id=message.id,
                signature=signature,
                now=now,
            )

            staff_exempt = is_staff(member)
            score, reasons = self.calculate_risk_score(
                content=content,
                signature=signature,
                distinct_channels=distinct_channels,
                staff_exempt=staff_exempt,
            )

            # Eşik altında kalan zararsız mesajlara dokunma
            if score < CONFIG["DELETE_SCORE_THRESHOLD"]:
                return

            # Skor == 2 ise yalnızca ilgili mesajı sil
            if score < CONFIG["PUNISH_SCORE_THRESHOLD"]:
                await self.safe_delete_partial(message.guild, message.channel.id, message.id)
                return

            # Skor >= 3: 10 dakika içinde zaten cezalandırıldıysa tekrar ceza uygulama (sadece mesajı sil)
            last_punished = self.punished_users.get(member.id)
            if last_punished is not None and (now - last_punished) < CONFIG["PUNISH_COOLDOWN_SECONDS"]:
                await self.safe_delete_partial(message.guild, message.channel.id, message.id)
                return

            # Tekrarlı tetiklenmeyi önlemek için ceza zamanını hemen kaydet
            self.punished_users[member.id] = now

            # a) Son 30 saniyedeki tüm spam mesajlarını tüm kanallarda PartialMessage ile sil
            deleted_count = await self.delete_recent_user_messages(message.guild, member.id, now)

            # b) Kullanıcıyı 24 saat timeout'a al
            timeout_status = await self.apply_member_timeout(message.guild, member)

            # c) Kullanıcıya güvenlik uyarısı DM'i gönder
            await self.send_hijack_dm(member, message.guild.name)

            # d) Güvenlik log kanalına kırmızı alarm embed'i gönder
            await self.send_security_log(
                guild=message.guild,
                member=member,
                channel=message.channel,
                score=score,
                deleted_count=deleted_count,
                timeout_status=timeout_status,
                reasons=reasons,
                raw_content=content,
            )

        except Exception as err:
            print(f"[AntiHijack] Mesaj işleme hatası: {err}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiHijackCog(bot))
