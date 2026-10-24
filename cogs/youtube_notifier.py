import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import pytz
import asyncio
import re
import xml.etree.ElementTree as ET
import aiohttp

from config import (
    GUILD_ID,
    ROLE_FOUNDER,
    ROLE_VIDEO_HABER,
    YOUTUBE_CHANNEL_ID,
    CH_ISLEMLER,
)
from database import (
    set_youtube_config,
    get_youtube_config,
    is_youtube_video_notified,
    mark_youtube_video_notified,
    get_notified_videos_count,
)

TZ = pytz.timezone("Europe/Istanbul")

ATOM_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}


class YouTubeLinkView(discord.ui.View):
    def __init__(self, video_url: str, channel_url: str):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Videoyu Hemen İzle",
                emoji="▶️",
                style=discord.ButtonStyle.link,
                url=video_url,
            )
        )
        self.add_item(
            discord.ui.Button(
                label="YouTube Kanalına Git",
                emoji="📺",
                style=discord.ButtonStyle.link,
                url=channel_url,
            )
        )


def build_youtube_dm_embed(
    guild: discord.Guild,
    member: discord.Member,
    video: dict,
    channel_id: str,
) -> discord.Embed:
    video_id = video["video_id"]
    video_title = video["title"]
    video_url = video["url"]
    channel_name = video.get("channel_name") or "GararjClass"
    channel_url = f"https://www.youtube.com/channel/{channel_id}"
    description_raw = (video.get("description") or "").strip()
    pub_ts = video.get("published_ts")

    if pub_ts:
        time_str = f"<t:{pub_ts}:F> (<t:{pub_ts}:R>)"
    else:
        now_ts = int(datetime.datetime.now(TZ).timestamp())
        time_str = f"<t:{now_ts}:F> (<t:{now_ts}:R>)"

    desc_parts = [
        f"👋 Merhaba {member.mention}!\n"
        f"🚨 **{channel_name}** YouTube kanalında yepyeni bir video yayına girdi! "
        f"Sunucumuzda **🎥 Video Haber** rolüne sahip olduğun için bu özel bildirimi ilk alanlardan birisin.",
        "***",
        f"### 📌 VİDEO DETAYLARI\n"
        f"> **📺 Kanal:** [{channel_name}]({channel_url})\n"
        f"> **🎬 Video Başlığı:** [{video_title}]({video_url})\n"
        f"> **🕒 Yayınlanma Zamanı:** {time_str}\n"
        f"> **🏷️ Bildirim Grubu:** `🎥 Video Haber`",
    ]

    if description_raw:
        clean_lines = [line.strip() for line in description_raw.splitlines() if line.strip()]
        short_desc = " ".join(clean_lines)
        if len(short_desc) > 220:
            short_desc = short_desc[:217] + "..."
        if short_desc:
            desc_parts.append(
                f"### 📝 VİDEO ÖZETİ\n"
                f"> *{short_desc}*"
            )

    desc_parts.extend([
        "***",
        "### 💡 DESTEK OLMAYI UNUTMA!\n"
        "👍 Videoyu izledikten sonra **beğenmeyi**, 💬 **yorumlarda** fikrini paylaşmayı ve 🔔 **abone olmayı** unutma!\n"
        "🍿 *Şimdiden iyi seyirler dileriz!*",
    ])

    embed = discord.Embed(
        title=f"🔥 {video_title}",
        url=video_url,
        description="\n\n".join(desc_parts),
        color=discord.Color.from_rgb(255, 0, 0),
        timestamp=datetime.datetime.now(TZ),
    )

    icon_url = guild.icon.url if guild and guild.icon else None
    embed.set_author(
        name=f"🎬 {channel_name} • YENİ VİDEO YAYINDA!",
        url=video_url,
        icon_url=icon_url,
    )

    if icon_url:
        embed.set_thumbnail(url=icon_url)

    # Yüksek çözünürlüklü YouTube kapak fotoğrafı
    thumbnail_url = video.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    embed.set_image(url=thumbnail_url)

    guild_name = guild.name if guild else "GararjClass"
    embed.set_footer(
        text=f"{guild_name} • YouTube Video Haber Sistemi",
        icon_url=icon_url,
    )
    return embed


class YouTubeNotifierCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._broadcast_lock = asyncio.Lock()
        self.youtube_check_loop.start()

    def cog_unload(self):
        self.youtube_check_loop.cancel()

    def get_active_channel_id(self) -> str:
        cfg = get_youtube_config()
        if cfg and cfg.get("channel_id"):
            return cfg["channel_id"].strip()
        if YOUTUBE_CHANNEL_ID:
            return YOUTUBE_CHANNEL_ID.strip()
        return ""

    async def resolve_youtube_channel_id(self, raw_input: str) -> tuple[str | None, str | None]:
        """Kullanıcının girdiği UC... ID, @kullaniciadi veya YouTube kanal linkinden UC... ID'sini çözer."""
        text = raw_input.strip()

        # Doğrudan UC... formatında girildiyse
        m_direct = re.match(r"^(UC[a-zA-Z0-9_-]{22})$", text)
        if m_direct:
            cid = m_direct.group(1)
            feed = await self.fetch_youtube_rss(cid)
            if feed is not None:
                return cid, feed.get("channel_name")
            return cid, None

        # URL içinde /channel/UC... varsa
        m_url = re.search(r"youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})", text)
        if m_url:
            cid = m_url.group(1)
            feed = await self.fetch_youtube_rss(cid)
            if feed is not None:
                return cid, feed.get("channel_name")
            return cid, None

        # @handle girildiyse URL'e çevir
        if text.startswith("@"):
            url = f"https://www.youtube.com/{text}"
        elif text.startswith("http://") or text.startswith("https://"):
            url = text
        else:
            url = f"https://www.youtube.com/@{text}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None, None
                    html = await resp.text()
        except Exception as e:
            print(f"[YouTubeNotifier] Kanal çözümlenirken hata: {e}")
            return None, None

        patterns = [
            r'"externalId":"(UC[a-zA-Z0-9_-]{22})"',
            r'<meta itemprop="channelId" content="(UC[a-zA-Z0-9_-]{22})"',
            r'youtube\.com/channel/(UC[a-zA-Z0-9_-]{22})',
            r'"browseId":"(UC[a-zA-Z0-9_-]{22})"',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                cid = m.group(1)
                feed = await self.fetch_youtube_rss(cid)
                if feed is not None:
                    return cid, feed.get("channel_name")
                return cid, None

        return None, None

    async def fetch_youtube_rss(self, channel_id: str) -> dict | None:
        """YouTube RSS akışını çeker ve kanal adı ile videoları döndürür."""
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(rss_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    xml_text = await resp.text()
        except Exception as e:
            print(f"[YouTubeNotifier] RSS okuma hatası: {e}")
            return None

        try:
            root = ET.fromstring(xml_text)
            channel_title_el = root.find("atom:title", ATOM_NS)
            channel_name = channel_title_el.text if channel_title_el is not None else "GararjClass"

            videos = []
            for entry in root.findall("atom:entry", ATOM_NS):
                vid_el = entry.find("yt:videoId", ATOM_NS)
                title_el = entry.find("atom:title", ATOM_NS)
                pub_el = entry.find("atom:published", ATOM_NS)
                link_el = entry.find("atom:link", ATOM_NS)
                media_group = entry.find("media:group", ATOM_NS)

                if vid_el is None or not vid_el.text:
                    continue

                video_id = vid_el.text.strip()
                title = title_el.text.strip() if (title_el is not None and title_el.text) else "Yeni Video"
                published_str = pub_el.text.strip() if (pub_el is not None and pub_el.text) else ""
                video_url = (
                    link_el.attrib.get("href")
                    if (link_el is not None and "href" in link_el.attrib)
                    else f"https://www.youtube.com/watch?v={video_id}"
                )

                description = ""
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                if media_group is not None:
                    desc_el = media_group.find("media:description", ATOM_NS)
                    if desc_el is not None and desc_el.text:
                        description = desc_el.text.strip()

                published_ts = None
                if published_str:
                    try:
                        dt = datetime.datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                        published_ts = int(dt.timestamp())
                    except Exception:
                        published_ts = None

                videos.append({
                    "video_id": video_id,
                    "title": title,
                    "url": video_url,
                    "published_at": published_str,
                    "published_ts": published_ts,
                    "description": description,
                    "thumbnail": thumbnail,
                    "channel_name": channel_name,
                })

            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "videos": videos,
            }
        except Exception as e:
            print(f"[YouTubeNotifier] XML ayrıştırma hatası: {e}")
            return None

    async def broadcast_video_dm(self, guild: discord.Guild, video: dict, channel_id: str) -> tuple[int, int, int]:
        """Video Haber rolüne sahip tüm üyelere DM üzerinden bildirim gönderir."""
        role = guild.get_role(ROLE_VIDEO_HABER)
        if not role:
            return 0, 0, 0

        members = [m for m in role.members if not m.bot]
        total_targets = len(members)
        sent_count = 0
        failed_count = 0

        channel_url = f"https://www.youtube.com/channel/{channel_id}"
        view = YouTubeLinkView(video_url=video["url"], channel_url=channel_url)

        async with self._broadcast_lock:
            for member in members:
                embed = build_youtube_dm_embed(guild, member, video, channel_id)
                try:
                    await member.send(embed=embed, view=view)
                    sent_count += 1
                except (discord.Forbidden, discord.HTTPException):
                    failed_count += 1
                except Exception:
                    failed_count += 1
                await asyncio.sleep(1.2)

        # Log kanalına özet rapor gönder
        log_ch = guild.get_channel(CH_ISLEMLER)
        if log_ch:
            log_embed = discord.Embed(
                title="🎬 YOUTUBE VİDEO HABER DM RAPORU",
                description=(
                    f"📺 **Kanal:** {video.get('channel_name', 'GararjClass')}\n"
                    f"🎬 **Video:** [{video['title']}]({video['url']})\n"
                    f"🏷️ **Hedef Rol:** {role.mention}\n\n"
                    f"***\n\n"
                    f"👥 **Roldeki Toplam Üye:** `{total_targets}`\n"
                    f"✅ **Başarıyla Gönderilen DM:** `{sent_count}`\n"
                    f"❌ **DM Kapalı / Ulaşılamayan:** `{failed_count}`"
                ),
                color=discord.Color.from_rgb(255, 0, 0),
                timestamp=datetime.datetime.now(TZ),
            )
            log_embed.set_thumbnail(url=video.get("thumbnail"))
            try:
                await log_ch.send(embed=log_embed)
            except Exception:
                pass

        return total_targets, sent_count, failed_count

    @tasks.loop(minutes=3)
    async def youtube_check_loop(self):
        channel_id = self.get_active_channel_id()
        if not channel_id:
            return

        # Eğer Railway'e yanlışlıkla link veya @handle girildiyse otomatik UC... ID'sine çevir
        if not channel_id.startswith("UC"):
            resolved_cid, resolved_name = await self.resolve_youtube_channel_id(channel_id)
            if not resolved_cid:
                return
            set_youtube_config(resolved_cid, resolved_name or "The_yagi.264")
            channel_id = resolved_cid

        guild = self.bot.get_guild(GUILD_ID)
        if not guild:
            return

        feed = await self.fetch_youtube_rss(channel_id)
        if not feed or not feed["videos"]:
            return

        videos = feed["videos"]

        # İlk kurulumda eski videoların hepsine bildirim gitmemesi için mevcut videoları kaydet
        if get_notified_videos_count() == 0:
            for v in videos:
                mark_youtube_video_notified(v["video_id"], v["title"], v["published_at"])
            set_youtube_config(channel_id, feed["channel_name"])
            print(f"[YouTubeNotifier] İlk kurulum: {len(videos)} mevcut video veritabanına işlendi ({feed['channel_name']}).")
            return

        # En son yüklenen videoyu kontrol et
        latest_video = videos[0]
        vid_id = latest_video["video_id"]

        if is_youtube_video_notified(vid_id):
            return

        # Eski videoların RSS'te yeniden görünmesi ihtimaline karşı 48 saat kontrolü
        now_ts = int(datetime.datetime.now(TZ).timestamp())
        pub_ts = latest_video.get("published_ts")
        if pub_ts and (now_ts - pub_ts) > (48 * 3600):
            mark_youtube_video_notified(vid_id, latest_video["title"], latest_video["published_at"])
            return

        # Yeni video tespit edildi -> Önce veritabanına kaydet, sonra DM gönderimini başlat
        mark_youtube_video_notified(vid_id, latest_video["title"], latest_video["published_at"])
        print(f"[YouTubeNotifier] Yeni video tespit edildi: {latest_video['title']} ({vid_id})")
        await self.broadcast_video_dm(guild, latest_video, channel_id)

    @youtube_check_loop.before_loop
    async def before_youtube_check_loop(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(5)

    # ==================== SLASH KOMUTLARI ====================

    @app_commands.command(
        name="youtube-ayarla",
        description="YouTube kanalınızı bağlar ve yeni videolarda Video Haber rolüne otomatik DM gönderir (Founder Özel)."
    )
    @app_commands.describe(
        kanal="YouTube kanal linkiniz (https://youtube.com/@...), @kullaniciadi veya UC... Kanal ID'niz"
    )
    async def cmd_youtube_ayarla(self, interaction: discord.Interaction, kanal: str):
        if not isinstance(interaction.user, discord.Member) or not any(r.id == ROLE_FOUNDER for r in interaction.user.roles):
            await interaction.response.send_message(
                "❌ Bu komutu yalnızca **Founder** rolüne sahip yetkililer kullanabilir.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        cid, resolved_name = await self.resolve_youtube_channel_id(kanal)
        if not cid:
            await interaction.followup.send(
                "❌ Girdiğiniz bağlantıdan veya bilgiden geçerli bir YouTube Kanal ID'si (`UC...`) bulunamadı.\n"
                "💡 **İpucu:** Kanal linkinizi (`https://www.youtube.com/@KanalAdiniz`) veya `UC...` ile başlayan Kanal ID'nizi doğrudan yapıştırabilirsiniz.",
                ephemeral=True,
            )
            return

        feed = await self.fetch_youtube_rss(cid)
        if not feed:
            await interaction.followup.send(
                f"❌ Kanal ID'si (`{cid}`) bulundu ancak YouTube RSS akışına ulaşılamadı. Lütfen tekrar deneyin.",
                ephemeral=True,
            )
            return

        channel_name = feed.get("channel_name") or resolved_name or "GararjClass"
        set_youtube_config(cid, channel_name)

        # Mevcut videoları "zaten biliniyor" olarak işaretle ki eski videolara DM gitmesin
        for v in feed.get("videos", []):
            mark_youtube_video_notified(v["video_id"], v["title"], v["published_at"])

        role = interaction.guild.get_role(ROLE_VIDEO_HABER) if interaction.guild else None
        role_count = len([m for m in role.members if not m.bot]) if role else 0
        latest_info = (
            f"[{feed['videos'][0]['title']}]({feed['videos'][0]['url']})"
            if feed.get("videos")
            else "Henüz video bulunamadı"
        )

        embed = discord.Embed(
            title="✅ YOUTUBE BİLDİRİM SİSTEMİ AKTİF EDİLDİ",
            description=(
                f"📺 **Bağlanan Kanal:** [{channel_name}](https://www.youtube.com/channel/{cid})\n"
                f"🆔 **Kanal ID:** `{cid}`\n"
                f"🎬 **Son Yüklenen Video:** {latest_info}\n\n"
                f"***\n\n"
                f"🏷️ **Bildirim Rolü:** <@&{ROLE_VIDEO_HABER}> (`{role_count}` Üye)\n"
                f"⏱️ **Kontrol Sıklığı:** Her **3 dakikada bir** otomatik kontrol\n"
                f"🛡️ **Koruma:** Kanalınızdaki mevcut `{len(feed.get('videos', []))}` video kaydedildi; **bundan sonra yükleyeceğiniz yeni videolarda** otomatik DM gönderilecektir.\n\n"
                f"💡 *DM mesajının nasıl göründüğünü hemen test etmek için `/youtube-test` komutunu kullanabilirsiniz!*"
            ),
            color=discord.Color.from_rgb(46, 204, 113),
            timestamp=datetime.datetime.now(TZ),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="youtube-test",
        description="Son yüklenen videonun DM bildirim tasarımını test eder veya tüm role gönderir (Founder Özel)."
    )
    @app_commands.describe(hedef="Bildirimin kime gönderileceğini seçin")
    @app_commands.choices(
        hedef=[
            app_commands.Choice(name="🔍 Sadece Bana Gönder (Tasarım Önizlemesi)", value="self"),
            app_commands.Choice(name="📢 Tüm Video Haber Rolüne Gönder (Gerçek Duyuru)", value="role"),
        ]
    )
    async def cmd_youtube_test(self, interaction: discord.Interaction, hedef: app_commands.Choice[str]):
        if not isinstance(interaction.user, discord.Member) or not any(r.id == ROLE_FOUNDER for r in interaction.user.roles):
            await interaction.response.send_message(
                "❌ Bu komutu yalnızca **Founder** rolüne sahip yetkililer kullanabilir.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        channel_id = self.get_active_channel_id()
        if not channel_id:
            await interaction.followup.send(
                "⚠️ Henüz bir YouTube kanalı ayarlanmamış! Önce `/youtube-ayarla` komutuyla kanalınızı bağlayın.",
                ephemeral=True,
            )
            return

        feed = await self.fetch_youtube_rss(channel_id)
        if not feed or not feed.get("videos"):
            await interaction.followup.send(
                "❌ YouTube kanalınızda henüz herkese açık bir video bulunamadı veya RSS okunamadı.",
                ephemeral=True,
            )
            return

        latest_video = feed["videos"][0]

        if hedef.value == "self":
            embed = build_youtube_dm_embed(interaction.guild, interaction.user, latest_video, channel_id)
            view = YouTubeLinkView(
                video_url=latest_video["url"],
                channel_url=f"https://www.youtube.com/channel/{channel_id}",
            )
            try:
                await interaction.user.send(embed=embed, view=view)
                await interaction.followup.send(
                    f"✅ **{latest_video['title']}** videosunun örnek DM bildirimi özel mesaj (DM) kutunuza gönderildi!",
                    ephemeral=True,
                )
            except Exception:
                await interaction.followup.send(
                    "❌ DM kutunuz kapalı olduğu için örnek mesaj gönderilemedi. Lütfen sunucu gizlilik ayarlarından DM'inizi açın.",
                    ephemeral=True,
                )
        else:
            total, sent, failed = await self.broadcast_video_dm(interaction.guild, latest_video, channel_id)
            await interaction.followup.send(
                f"📢 **Toplu DM Gönderimi Tamamlandı!**\n"
                f"👥 Hedef Üye: `{total}` | ✅ Gönderilen: `{sent}` | ❌ DM Kapalı: `{failed}`",
                ephemeral=True,
            )

    @app_commands.command(
        name="youtube-durum",
        description="YouTube bildirim sisteminin durumunu ve bağlı kanalı gösterir."
    )
    async def cmd_youtube_durum(self, interaction: discord.Interaction):
        channel_id = self.get_active_channel_id()
        if not channel_id:
            await interaction.response.send_message(
                "⚠️ Henüz bağlı bir YouTube kanalı yok. Kurucu `/youtube-ayarla` komutu ile kanalı bağlayabilir.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        feed = await self.fetch_youtube_rss(channel_id)
        cfg = get_youtube_config()
        channel_name = (feed.get("channel_name") if feed else None) or (cfg.get("channel_name") if cfg else "GararjClass")
        role = interaction.guild.get_role(ROLE_VIDEO_HABER) if interaction.guild else None
        role_count = len([m for m in role.members if not m.bot]) if role else 0

        latest_str = "Bulunamadı"
        if feed and feed.get("videos"):
            v = feed["videos"][0]
            latest_str = f"[{v['title']}]({v['url']})"

        embed = discord.Embed(
            title="🎬 YOUTUBE VİDEO HABER SİSTEM DURUMU",
            description=(
                f"📺 **Takip Edilen Kanal:** [{channel_name}](https://www.youtube.com/channel/{channel_id})\n"
                f"🆔 **Kanal ID:** `{channel_id}`\n"
                f"🎬 **En Son Video:** {latest_str}\n\n"
                f"***\n\n"
                f"🏷️ **Bildirim Rolü:** <@&{ROLE_VIDEO_HABER}>\n"
                f"👥 **Bildirim Alacak Üye Sayısı:** `{role_count}` Kişi\n"
                f"📊 **Kayıtlı Video Hafızası:** `{get_notified_videos_count()}` Video"
            ),
            color=discord.Color.from_rgb(255, 0, 0),
            timestamp=datetime.datetime.now(TZ),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(YouTubeNotifierCog(bot))
