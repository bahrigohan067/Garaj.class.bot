import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import random
import string
import pytz
import os
import config
import database

TZ = pytz.timezone("Europe/Istanbul")

# ==================== KURAL LİSTESİ VE MADDELER ====================
RULES = {
    # 1. KATEGORİ: GENEL KURALLAR (M1 - M13)
    "M1": {
        "title": "Küfür / Hakaret",
        "points": 2,
        "type": "point",
        "desc": "Sunucumuzda küfür/hakarete başvurmak. Bununla ilgili içerik paylaşmak."
    },
    "M2": {
        "title": "Reklam ve Ticari Faaliyetler",
        "points": 0,
        "type": "ban",
        "desc": "Reklam yapmak, hesap/oyun satışı gibi ticari faaliyetlerde bulunmak (Özel mesaj da dahil)."
    },
    "M3": {
        "title": "Abartı Övünme / Rahatsızlık Verme",
        "points": 1,
        "type": "point",
        "desc": "Sunucumuzda düzenlenen etkinliklerde veya yapılacak olan kapışmalarda karşı taraf rahatsız olduğu halde kendini abartı şekilde övmek."
    },
    "M4": {
        "title": "Taciz İçeren Davranışlar",
        "points": 0,
        "type": "timeout",
        "duration_days": 2,
        "desc": "Cinsiyet fark etmeksizin taciz içeren davranışlarda bulunmak."
    },
    "M5": {
        "title": "Kanalları Amacı Dışında Kullanmak",
        "points": 3,
        "type": "point",
        "desc": "Kanalları amacı dışında kullanmak (Örn: #bot-komut'da sohbet etmek)."
    },
    "M6": {
        "title": "Cinsel İçerikli Paylaşım (+18)",
        "points": 8,
        "type": "point",
        "desc": "Cinsel içerikli herhangi bir paylaşım (görsel, yazı, link) yapmak."
    },
    "M7": {
        "title": "Kavga Ortamı Yaratma / Kasten Rahatsız Etme",
        "points": 4,
        "type": "point",
        "desc": "Bir kişiye muhatap olmak istemediği sürece ya da kasten kavga ortamı yaratmak."
    },
    "M8": {
        "title": "Zorbalık ve Üye Soğutma",
        "points": 5,
        "type": "point",
        "desc": "Zorbalık yapmak, başka bir üyeyi sunucudan soğutacak davranışlarda bulunmak."
    },
    "M9": {
        "title": "İzinsiz Sunucu / Grup Daveti",
        "points": 0,
        "type": "yasakli",
        "desc": "Yönetimin bilgisi dışında sunucu üyelerini kendi sunucunuza veya grubunuza davet etmek."
    },
    "M10": {
        "title": "Uygunsuz / Ayrımcı İçerik Paylaşımı",
        "points": 0,
        "type": "timeout",
        "duration_days": 1,
        "desc": "+18, cinsel taciz, ırkçılık, cinsiyet/yaş ayrımcılığı içeren içerik paylaşmak."
    },
    "M11": {
        "title": "Irkçılık ve Ayrımcılık",
        "points": 0,
        "type": "timeout",
        "duration_days": 1,
        "desc": "Irkçılık ve her türlü ayrımcılık yapmak."
    },
    "M12": {
        "title": "Psikolojik Baskı, Küçümseme ve Dalga Geçme",
        "points": 2,
        "type": "point",
        "desc": "Sunucuda bulunan kişilerin psikolojisini etkileyecek argo, küçümseme ve dalga geçme gibi faaliyetler yapmak."
    },
    "M13": {
        "title": "3. Taraf Yazılım / Hile Kullanımı",
        "points": 0,
        "type": "timeout",
        "duration_days": 1,
        "desc": "Sunucuda yapılan etkinliklerde ve kapışmalarda 3. Taraf yazılım kullanmak."
    },

    # 2. KATEGORİ: GENEL SUNUCU DÜZENİ (Önemli Kanallar & Ses Kanalları) (D1 - D3)
    "D1": {
        "title": "Önemli Kanallara Boş / Anlamsız Mesaj",
        "points": 3,
        "type": "point",
        "desc": "Önemli kanallara (duyuru vb.) anlamsız, boş mesajlar atmak."
    },
    "D2": {
        "title": "Kanal / Panel Spawnlama ve Meşgul Etme",
        "points": 3,
        "type": "point",
        "desc": "Ses kanallarında ses panelini veya sohbet kanallarında sohbeti gereksiz yere çağırmak (spawnlamak)."
    },
    "D3": {
        "title": "Ses Kanallarında Gereksiz Oda Değiştirme",
        "points": 3,
        "type": "point",
        "desc": "Önemli ses kanallarında sürekli yolculuk yaparak gereksiz bildirim yağmuruna sebep olmak."
    },

    # Rol / Oyun / Roleplay Kuralları (RM1 - RM18)
    "RM1": {"title": "Rol İhlali (Fail RP / Non RP)", "points": 2, "type": "point", "desc": "Rolün gerektirdiği mantık çerçevesinin dışına çıkmak."},
    "RM2": {"title": "Meta Gaming (Oyun Dışı Bilgi Kullanımı)", "points": 2, "type": "point", "desc": "Discord veya harici yerlerden edindiği bilgiyi oyun içinde haksız avantaj olarak kullanmak."},
    "RM3": {"title": "Power Gaming (Gerçek Dışı Hareketler)", "points": 2, "type": "point", "desc": "Karakterin fiziksel olarak yapamayacağı imkansız hareketlerde bulunmak."},
    "RM4": {"title": "RDM (Sebepsiz Saldırı / Zarar Verme)", "points": 3, "type": "point", "desc": "Geçerli bir sebep olmadan diğer oyunculara saldırmak veya zarar vermek."},
    "RM5": {"title": "VDM (Araçla Kasıtlı Ezme / Çarpma)", "points": 3, "type": "point", "desc": "Aracı kasıtlı olarak oyuncuları ezmek için silah gibi kullanmak."},
    "RM6": {"title": "Rol İçi Hayatına Değer Vermeme (Fear RP)", "points": 2, "type": "point", "desc": "Silah çekildiğinde veya hayati tehlike anında hayatına değer vermemek."},
    "RM7": {"title": "Combat Log (Rolden Kaçma)", "points": 4, "type": "point", "desc": "Rol sırasında veya ceza alacağını anlayınca oyundan/sunucudan çıkmak."},
    "RM8": {"title": "Güvenli Bölge İhlali (Safezone)", "points": 3, "type": "point", "desc": "Belirlenen güvenli bölgelerde suç işlemek veya çatışma başlatmak."},
    "RM9": {"title": "Rol Bölme ve OOC Konuşma", "points": 2, "type": "point", "desc": "Rol esnasında rolü bozacak şekilde oyun dışı konuşmak veya tartışmak."},
    "RM10": {"title": "Haksız Kazanç ve Bug / Glitch İstismarı", "points": 4, "type": "point", "desc": "Oyun mekaniğindeki hatalardan yararlanarak avantaj sağlamak."},
    "RM11": {"title": "Oyun İçi Rolde Saygısızlık ve Toksiklik", "points": 2, "type": "point", "desc": "Rol çerçevesini aşarak oyuncuyu kişisel olarak hedef alıp aşağılamak."},
    "RM12": {"title": "Rol Pasifliği ve İletişimsizlik", "points": 1, "type": "point", "desc": "Rol esnasında tepki vermemek veya rol akışını aksatmak."},
    "RM13": {"title": "Araç Hırsızlığı ve Kuralsız Sürüş", "points": 2, "type": "point", "desc": "Rol dışı gereksiz araç kaçırma veya gerçek dışı araç kullanımı."},
    "RM14": {"title": "Kamu / Görevli Personeli Trollük", "points": 3, "type": "point", "desc": "Polis, sağlıkçı vb. kamu görevlilerini sebepsiz yere meşgul etmek."},
    "RM15": {"title": "Ağır Rol İhlali ve Rol Sabotajı", "points": 5, "type": "timeout", "duration_days": 1, "desc": "Toplu rol etkinliklerini kasten sabote etmek."},
    "RM16": {"title": "Gerçek Para ile Ticaret (RMT)", "points": 0, "type": "yasakli", "desc": "Oyun içi varlıkları gerçek para karşılığında satmaya veya almaya çalışmak."},
    "RM17": {"title": "Yetkililere Yalan Beyan ve Sahte Kanıt", "points": 5, "type": "timeout", "duration_days": 2, "desc": "Destek taleplerinde gerçeğe aykırı delil sunmak veya yetkiliyi yanıltmak."},
    "RM18": {"title": "Hile, 3. Parti Yazılım ve Exploit", "points": 0, "type": "ban", "desc": "Oyun dosyalarını değiştirmek veya üçüncü parti hile yazılımı kullanmak."},

    # Yetkili Kuralları (Y1 - Y5)
    "Y1": {"title": "Yetki İhmali ve İlgisizlik", "type": "staff", "desc": "Desteklere bakmamak, biletleri cevapsız bırakmak veya görevini aksatmak."},
    "Y2": {"title": "Üyelere veya Yetkililere Karşı Saygısız Tutum", "type": "staff", "desc": "Üyelerle polemiğe girmek, azarlamak veya haksız muamele yapmak."},
    "Y3": {"title": "Hatalı veya Kanıtsız Ceza Uygulaması", "type": "staff", "desc": "Yeterli kanıt olmadan keyfi ceza vermek veya kural dışı işlem yapmak."},
    "Y4": {"title": "Yetkili Odalarında ve Toplantılarda Düzensizlik", "type": "staff", "desc": "Yetkili toplantılarına mazeretsiz katılmamak veya yetkili sohbetinde kaos yaratmak."},
    "Y5": {"title": "Ağır Yetki Suistimali (Yetkiyi Kötüye Kullanma)", "type": "staff_heavy", "desc": "Yetkilerini kişisel çıkarları için kullanmak, rollerle oynamak veya sabotaj."},
}

def generate_warn_id():
    """Rastgele 4 haneli benzersiz uyarı ID'si üretir (Örn: #A8F2)"""
    chars = string.ascii_uppercase + string.digits
    return "#" + "".join(random.choice(chars) for _ in range(4))

def is_staff(member: discord.Member) -> bool:
    """Kullanıcının yetkili olup olmadığını kontrol eder."""
    if member.guild_permissions.administrator:
        return True
    return any(role.id in config.STAFF_ROLES for role in member.roles)

# ==================== KANIT GÖRSELİ EKLEME GÖRÜNÜMÜ ====================

class EvidenceModal(discord.ui.Modal, title="📎 Kanıt Görseli Ekle"):
    def __init__(self, warn_id: str, log_message: discord.Message, log_channel: discord.TextChannel):
        super().__init__()
        self.warn_id = warn_id
        self.log_message = log_message
        self.log_channel = log_channel

    image_url = discord.ui.TextInput(
        label="Kanıt Görsel Linki (URL)",
        placeholder="https://cdn.discordapp.com/... veya görsel bağlantısı",
        style=discord.TextStyle.short,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        url = self.image_url.value.strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            await interaction.response.send_message("❌ Geçersiz görsel bağlantısı! Link http:// veya https:// ile başlamalıdır.", ephemeral=True)
            return

        # Veritabanında güncelle
        database.set_warning_image(self.warn_id, url)

        # Log mesajındaki embed'i güncelle
        try:
            if self.log_message and self.log_message.embeds:
                embed = self.log_message.embeds[0]
                embed.set_image(url=url)
                # Kanıt alanını güncelle
                for i, field in enumerate(embed.fields):
                    if "Kanıt" in field.name:
                        embed.set_field_at(i, name="📎 Kanıt", value=f"Görsel Kanıtı: [Resim için Tıkla]({url})", inline=False)
                        break
                await self.log_message.edit(embed=embed)
        except Exception as e:
            print(f"Log mesajı kanıt güncelleme hatası: {e}")

        await interaction.response.send_message(f"✅ Kanıt görseli **{self.warn_id}** numaralı uyarı kaydına başarıyla eklendi!", ephemeral=True)

class EvidencePromptView(discord.ui.View):
    def __init__(self, warn_id: str, log_message: discord.Message, log_channel: discord.TextChannel):
        super().__init__(timeout=60)
        self.warn_id = warn_id
        self.log_message = log_message
        self.log_channel = log_channel

    @discord.ui.button(label="📎 Görsel Yükle", style=discord.ButtonStyle.primary, emoji="📎")
    async def add_evidence(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EvidenceModal(self.warn_id, self.log_message, self.log_channel))

    @discord.ui.button(label="⏩ Pas Geç", style=discord.ButtonStyle.secondary)
    async def skip_evidence(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.send_message("Kanıt ekleme adımı pas geçildi. İşlem tamamlandı.", ephemeral=True)

# ==================== MODALLER ====================

class VerbalWarnModal(discord.ui.Modal, title="🗣️ Sözlü Uyarı Formu"):
    def __init__(self, target_member: discord.Member, cog):
        super().__init__()
        self.target_member = target_member
        self.cog = cog

    reason = discord.ui.TextInput(
        label="Uyarı Sebebi",
        placeholder="Sözlü uyarı gerekçesini detaylıca açıklayın...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.process_verbal_warning(interaction, self.target_member, self.reason.value.strip())

class OfficialWarnModal(discord.ui.Modal, title="⚠️ Resmi Uyarı Formu"):
    def __init__(self, target_member: discord.Member, cog):
        super().__init__()
        self.target_member = target_member
        self.cog = cog

    rule_code = discord.ui.TextInput(
        label="Madde Numarası",
        placeholder="M1 / D1 / RM4 / Y2 vb.",
        style=discord.TextStyle.short,
        required=True,
        max_length=15
    )

    extra_note = discord.ui.TextInput(
        label="Ek Açıklama / Not (Opsiyonel)",
        placeholder="Varsa olayla ilgili ek ayrıntıları buraya yazın...",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.cog.process_official_warning(
            interaction,
            self.target_member,
            self.rule_code.value.strip(),
            self.extra_note.value.strip() if self.extra_note.value else ""
        )

# ==================== SEÇİM VE ARAYÜZ VIEW'LARI ====================

class UserSelectView(discord.ui.View):
    def __init__(self, warn_type: str, cog):
        super().__init__(timeout=60)
        self.warn_type = warn_type # 'verbal' veya 'official'
        self.cog = cog

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Uyarı verilecek kişiyi seçin...", min_values=1, max_values=1)
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        target = select.values[0]
        guild = interaction.guild
        member = guild.get_member(target.id)
        if not member:
            try:
                member = await guild.fetch_member(target.id)
            except Exception:
                await interaction.response.send_message("❌ Kullanıcı sunucuda bulunamadı!", ephemeral=True)
                return

        if member.bot:
            await interaction.response.send_message("❌ Botlara uyarı verilemez!", ephemeral=True)
            return

        if self.warn_type == "verbal":
            await interaction.response.send_modal(VerbalWarnModal(member, self.cog))
        else:
            await interaction.response.send_modal(OfficialWarnModal(member, self.cog))

class WarningPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    async def check_staff(self, interaction: discord.Interaction) -> bool:
        if not is_staff(interaction.user):
            await interaction.response.send_message("❌ Bu paneli yalnızca yetkililer kullanabilir!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Sözlü Uyarı Ver", style=discord.ButtonStyle.secondary, emoji="🗣️", custom_id="warn_panel_verbal")
    async def verbal_warn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_staff(interaction):
            return
        view = UserSelectView(warn_type="verbal", cog=self.cog)
        await interaction.response.send_message("Lütfen sözlü uyarı verilecek kullanıcıyı seçin:", view=view, ephemeral=True)

    @discord.ui.button(label="Uyarı Ver", style=discord.ButtonStyle.danger, emoji="⚠️", custom_id="warn_panel_official")
    async def official_warn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_staff(interaction):
            return
        view = UserSelectView(warn_type="official", cog=self.cog)
        await interaction.response.send_message("Lütfen uyarı verilecek kullanıcıyı seçin:", view=view, ephemeral=True)

# ==================== ANA UYARI SİSTEMİ COG ====================

class WarningSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.auto_pardon_loop.start()
        self.jail_check_loop.start()

    async def cog_load(self):
        self.bot.add_view(WarningPanelView(cog=self))

    def cog_unload(self):
        self.auto_pardon_loop.cancel()
        self.jail_check_loop.cancel()

    # ------------------ YARDIMCI METODLAR ------------------

    async def send_log_embed(self, target: discord.Member, moderator: discord.Member, warn_id: str,
                             end_date_str: str, total_warns: int, points_text: str, reason_text: str,
                             roles_text: str, action_taken: str, color: discord.Color,
                             image_url: str = None) -> discord.Message:
        """Kullanıcının istediği şemaya birebir sadık uyarı bildirim embed'ini gönderir."""
        log_channel = self.bot.get_channel(config.CH_UYARI_LOG)
        if not log_channel:
            try:
                log_channel = await self.bot.fetch_channel(config.CH_UYARI_LOG)
            except Exception:
                return None

        guild = target.guild
        embed = discord.Embed(
            title="⚠️ Uyarı Var!!!",
            color=color,
            timestamp=datetime.datetime.now(TZ)
        )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        # 👤 Taraflar
        embed.add_field(
            name="👤 Taraflar",
            value=f"**Ceza Yiyen Kişi:** {target.mention}\n**Yetkili:** {moderator.mention}",
            inline=False
        )

        # 📌 Kayıt Özet
        embed.add_field(
            name="📌 Kayıt Özet",
            value=(
                f"• **Uyarı ID:** `{warn_id}`\n"
                f"• **Yetkili:** {moderator.mention}\n"
                f"• **Ceza Yiyen Kişi:** {target.mention}\n"
                f"• **Uyarı Bitiş Tarihi:** {end_date_str}\n"
                f"• **Toplam Uyarı:** {total_warns}"
            ),
            inline=False
        )

        # 🚨 Verilen Uyarı Puanı
        embed.add_field(
            name="🚨 Verilen Uyarı Puanı:",
            value=points_text,
            inline=False
        )

        # 📝 Uyarı Sebebi
        embed.add_field(
            name="📝 Uyarı Sebebi:",
            value=reason_text,
            inline=False
        )

        # 🏷️ Rolleri
        embed.add_field(
            name="🏷️ Rolleri:",
            value=roles_text if roles_text else "Rol Bulunamadı",
            inline=False
        )

        # 📎 Kanıt
        evidence_text = f"[Resim için Tıkla]({image_url})" if image_url else "Eklenmedi"
        embed.add_field(
            name="📎 Kanıt",
            value=f"Görsel Kanıtı: {evidence_text}",
            inline=False
        )

        # ⚡ Uygulanan İşlem
        embed.add_field(
            name="⚡ Uygulanan İşlem",
            value=f"```{action_taken}```",
            inline=False
        )

        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(
            text=f"Uyarı ID: {warn_id} • © 2026 GarajClass",
            icon_url=guild.icon.url if guild.icon else None
        )

        msg = await log_channel.send(content=f"{target.mention}", embed=embed)
        return msg

    # ------------------ SÖZLÜ UYARI İŞLEYİŞİ ------------------

    async def process_verbal_warning(self, interaction: discord.Interaction, target: discord.Member, reason: str):
        warn_id = generate_warn_id()
        moderator = interaction.user
        roles_text = ", ".join([r.mention for r in target.roles if not r.is_default()])

        action_taken = "Sözlü uyarı yapıldı (0 Puan, Rolsüz ihtar)."
        expires_at = "Kalıcı"
        total_warns = database.get_total_warnings_count(target.id) + 1

        # Veritabanına kaydet
        database.save_warning(
            warn_id=warn_id,
            user_id=target.id,
            moderator_id=moderator.id,
            target_roles=roles_text,
            warn_type="verbal",
            rule_code="SÖZLÜ",
            reason=reason,
            points=0,
            action_taken=action_taken,
            expires_at=expires_at
        )

        # Log Embed Gönder (Turuncu Şerit)
        msg = await self.send_log_embed(
            target=target,
            moderator=moderator,
            warn_id=warn_id,
            end_date_str=expires_at,
            total_warns=total_warns,
            points_text="0 Puan (Sözlü İhtar)",
            reason_text=f"**Sözlü İhtar:** {reason}",
            roles_text=roles_text,
            action_taken=action_taken,
            color=discord.Color.orange()
        )

        if msg:
            database.set_warning_log_message_id(warn_id, msg.id)

        # Yetkiliye kanıt ekleme butonları sun
        log_channel = self.bot.get_channel(config.CH_UYARI_LOG)
        evidence_view = EvidencePromptView(warn_id, msg, log_channel)
        await interaction.followup.send(
            f"✅ **{target.display_name}** kullanıcısına sözlü uyarı başarıyla iletildi (`{warn_id}`).\n"
            f"İsterseniz aşağıdaki butonla bu uyarıya ekran görüntüsü kanıtı ekleyebilirsiniz:",
            view=evidence_view,
            ephemeral=True
        )

    # ------------------ RESMİ UYARI İŞLEYİŞİ ------------------

    async def process_official_warning(self, interaction: discord.Interaction, target: discord.Member,
                                       rule_code_input: str, extra_note: str):
        moderator = interaction.user
        guild = interaction.guild
        rule_key = rule_code_input.upper().strip()
        rule = RULES.get(rule_key)

        target_is_staff_member = is_staff(target)
        is_staff_rule = rule_key.startswith("Y") or (rule and rule.get("type", "").startswith("staff"))

        warn_id = generate_warn_id()
        now = datetime.datetime.now(TZ)
        roles_text = ", ".join([r.mention for r in target.roles if not r.is_default()])

        user_data = database.get_user_warn_data(target.id)
        action_taken = ""
        points_given = 0
        warn_type = "participant"
        color = discord.Color.red()
        end_date_str = (now + datetime.timedelta(days=30)).strftime("%d/%m/%Y")

        # ================= A: YETKİLİ İŞLEYİŞİ =================
        if target_is_staff_member and is_staff_rule:
            warn_type = "staff"
            color = discord.Color.dark_red()
            current_staff_warns = user_data["staff_warn_count"]
            new_staff_warns = current_staff_warns + 1

            rule_title = rule["title"] if rule else "Yetkili Kural İhlali"
            rule_desc = rule["desc"] if rule else "Yetkili sorumluluklarına aykırı hareket."

            # Ağır İhlal (Y5) veya 4. Uyarı Sınır Aşımı -> Tüm yetkilerin alınması
            if rule_key == "Y5" or new_staff_warns >= 4:
                action_taken = "4. İhlal Sınır Aşımı / Ağır İhlal: Tüm yetkili rolleri geri alındı ve yetkisi düşürüldü."
                # Yetkili uyarı rollerini ve yönetim rollerini kaldır
                roles_to_remove = [
                    config.ROLE_YETKILI_UYARI_1, config.ROLE_YETKILI_UYARI_2, config.ROLE_YETKILI_UYARI_3,
                    config.ROLE_NEW_TRIAL_STAFF, config.ROLE_STAFF, config.ROLE_SENIOR_STAFF,
                    config.ROLE_MODERATOR, config.ROLE_HEAD_ADMIN, config.ROLE_FOUNDER,
                    config.ROLE_REGISTRATION_MANAGER, config.ROLE_SUPPORT_TEAM, config.ROLE_TRIAL_MOD
                ]
                for r_id in roles_to_remove:
                    r = guild.get_role(r_id)
                    if r and r in target.roles:
                        try:
                            await target.remove_roles(r, reason="Yetkili Uyarı Sınır Aşımı: Yetki Alındı")
                        except Exception:
                            pass
            elif new_staff_warns == 1:
                action_taken = "1. İhlal: Yetkili Uyarı 1 rolü verildi."
                r1 = guild.get_role(config.ROLE_YETKILI_UYARI_1)
                if r1: await target.add_roles(r1, reason="Yetkili Uyarı 1")
            elif new_staff_warns == 2:
                action_taken = "2. İhlal: Yetkili Uyarı 1 silindi, Yetkili Uyarı 2 rolü verildi."
                r1 = guild.get_role(config.ROLE_YETKILI_UYARI_1)
                r2 = guild.get_role(config.ROLE_YETKILI_UYARI_2)
                if r1 and r1 in target.roles: await target.remove_roles(r1)
                if r2: await target.add_roles(r2, reason="Yetkili Uyarı 2")
            elif new_staff_warns == 3:
                action_taken = "3. İhlal: Yetkili Uyarı 2 silindi, Yetkili Uyarı 3 rolü verildi."
                r2 = guild.get_role(config.ROLE_YETKILI_UYARI_2)
                r3 = guild.get_role(config.ROLE_YETKILI_UYARI_3)
                if r2 and r2 in target.roles: await target.remove_roles(r2)
                if r3: await target.add_roles(r3, reason="Yetkili Uyarı 3")

            database.update_user_warn_data(
                user_id=target.id,
                total_points=user_data["total_points"],
                kademe=user_data["kademe"],
                staff_warn_count=new_staff_warns,
                last_warn_date=now.isoformat(),
                jail_until=user_data["jail_until"],
                timeout_10_applied=user_data["timeout_10_applied"]
            )
            points_text = f"Yetkili Uyarısı (Toplam İhlal: {new_staff_warns}/4)"
            reason_formatted = f"**{rule_key} — {rule_title}**\n{rule_desc}"
            if extra_note:
                reason_formatted += f"\n*Ek Not:* {extra_note}"

        # ================= B: KATILIMCI (OYUNCU) İŞLEYİŞİ =================
        else:
            rule_title = rule["title"] if rule else "Sunucu Kural İhlali"
            rule_desc = rule["desc"] if rule else "Belirtilen kural maddesine aykırı hareket."
            rule_type = rule.get("type", "point") if rule else "point"
            points_given = rule.get("points", 1) if rule else 1

            reason_formatted = f"**{rule_key} — {rule_title}**\n{rule_desc}"
            if extra_note:
                reason_formatted += f"\n*Ek Not:* {extra_note}"

            # 1. Özel Yaptırımlı Kural Kontrolleri
            if rule_type == "ban":
                warn_type = "direct_ban"
                end_date_str = "Kalıcı"
                action_taken = "Doğrudan Ban: Kullanıcı sunucudan kalıcı olarak uzaklaştırıldı."
                try:
                    await target.ban(reason=f"Doğrudan Ban Kuralı: {rule_key} - {rule_title}")
                except Exception as e:
                    action_taken += f" (Ban yetkisi yetersiz: {e})"
                points_text = "Özel Yaptırım: Kalıcı Ban"

            elif rule_type == "yasakli":
                warn_type = "direct_yasakli"
                end_date_str = "Kalıcı"
                action_taken = "Doğrudan Yasaklı: Kullanıcı izole edildi."
                # Varsa yasaklı rolünü ver
                if config.ROLE_YASAKLI:
                    r_yasakli = guild.get_role(config.ROLE_YASAKLI)
                    if r_yasakli:
                        await target.add_roles(r_yasakli, reason=f"Yasaklı Rolü: {rule_key}")
                points_text = "Özel Yaptırım: Yasaklı İzolasyonu"

            elif rule_type == "timeout":
                warn_type = "direct_timeout"
                days = rule.get("duration_days", 1)
                end_date_str = (now + datetime.timedelta(days=days)).strftime("%d/%m/%Y")
                action_taken = f"Özel Sabit Zaman Aşımı: {days} Gün Timeout uygulandı."
                try:
                    await target.timeout(datetime.timedelta(days=days), reason=f"Sabit Zaman Aşımı: {rule_key}")
                except Exception as e:
                    action_taken += f" (Timeout verilemedi: {e})"
                points_text = f"Özel Yaptırım ({days} Gün Zaman Aşımı)"

            # 2. Puanlı Kural İşleyişi
            else:
                current_points = user_data["total_points"]
                new_points = current_points + points_given
                new_kademe = 0
                role_actions = []

                # Kademe ve Rol Belirleme
                # 0-2: Kademe 0
                if new_points < 3:
                    new_kademe = 0
                    role_actions.append(f"+{points_given} Puan işlendi (Toplam {new_points} Puan, Kademe 0).")
                # 3-5: Kademe 1
                elif 3 <= new_points <= 5:
                    new_kademe = 1
                    r1 = guild.get_role(config.ROLE_UYARI_1)
                    if r1: await target.add_roles(r1, reason="Uyarı 1")
                    role_actions.append("Uyarı 1 rolü verildi.")
                # 6-8: Kademe 2
                elif 6 <= new_points <= 8:
                    new_kademe = 2
                    r1 = guild.get_role(config.ROLE_UYARI_1)
                    r2 = guild.get_role(config.ROLE_UYARI_2)
                    if r1 and r1 in target.roles: await target.remove_roles(r1)
                    if r2: await target.add_roles(r2, reason="Uyarı 2")
                    role_actions.append("Uyarı 1 kaldırıldı, Uyarı 2 rolü verildi.")
                # 9-11: Kademe 3
                elif 9 <= new_points <= 11:
                    new_kademe = 3
                    r2 = guild.get_role(config.ROLE_UYARI_2)
                    r3 = guild.get_role(config.ROLE_UYARI_3)
                    if r2 and r2 in target.roles: await target.remove_roles(r2)
                    if r3: await target.add_roles(r3, reason="Uyarı 3")
                    role_actions.append("Uyarı 2 kaldırıldı, Uyarı 3 rolü verildi.")
                # 12-14: Kademe 4
                elif 12 <= new_points <= 14:
                    new_kademe = 4
                    r3 = guild.get_role(config.ROLE_UYARI_3)
                    r4 = guild.get_role(config.ROLE_UYARI_4)
                    if r3 and r3 in target.roles: await target.remove_roles(r3)
                    if r4: await target.add_roles(r4, reason="Uyarı 4")
                    role_actions.append("Uyarı 3 kaldırıldı, Uyarı 4 rolü verildi.")
                # 15+: Kademe 5
                else:
                    new_kademe = 5
                    r4 = guild.get_role(config.ROLE_UYARI_4)
                    r5 = guild.get_role(config.ROLE_UYARI_5)
                    if r4 and r4 in target.roles: await target.remove_roles(r4)
                    if r5: await target.add_roles(r5, reason="Uyarı 5")
                    role_actions.append("Uyarı 5 rolü verildi.")

                    # 1 Hafta Karantina / Askıda Süreci
                    jail_until = (now + datetime.timedelta(days=7)).isoformat()
                    user_data["jail_until"] = jail_until
                    if config.ROLE_ASKIDA:
                        r_askida = guild.get_role(config.ROLE_ASKIDA)
                        if r_askida: await target.add_roles(r_askida, reason="15+ Puan Kademe 5 Askıda")
                    try:
                        await target.timeout(datetime.timedelta(days=7), reason="15+ Uyarı Puanı: 1 Hafta Karantina")
                    except Exception:
                        pass
                    role_actions.append("Kişiye Askıda süreci tanımlandı (1 Hafta Karantina).")

                # 10 Puan Kritik Eşiği (+3 Gün Zaman Aşımı)
                timeout_10_flag = user_data["timeout_10_applied"]
                if new_points >= 10 and timeout_10_flag == 0:
                    try:
                        await target.timeout(datetime.timedelta(days=3), reason="10 Puan Kritik Eşiği: +3 Gün Timeout")
                        role_actions.append("⚡ 10 Puan Kritik Eşiği: Otomatik +3 Gün Timeout uygulandı.")
                        timeout_10_flag = 1
                    except Exception as e:
                        role_actions.append(f"(10 puan timeout uygulanamadı: {e})")

                action_taken = "\n".join(role_actions)
                points_text = f"+{points_given} Puan (Toplam: {new_points})"

                database.update_user_warn_data(
                    user_id=target.id,
                    total_points=new_points,
                    kademe=new_kademe,
                    staff_warn_count=user_data["staff_warn_count"],
                    last_warn_date=now.isoformat(),
                    jail_until=user_data.get("jail_until"),
                    timeout_10_applied=timeout_10_flag
                )

        # Veritabanına kaydet
        total_warns = database.get_total_warnings_count(target.id) + 1
        database.save_warning(
            warn_id=warn_id,
            user_id=target.id,
            moderator_id=moderator.id,
            target_roles=roles_text,
            warn_type=warn_type,
            rule_code=rule_key,
            reason=reason_formatted,
            points=points_given,
            action_taken=action_taken,
            expires_at=end_date_str
        )

        # Log Embed'ini Gönder
        msg = await self.send_log_embed(
            target=target,
            moderator=moderator,
            warn_id=warn_id,
            end_date_str=end_date_str,
            total_warns=total_warns,
            points_text=points_text,
            reason_text=reason_formatted,
            roles_text=roles_text,
            action_taken=action_taken,
            color=color
        )

        if msg:
            database.set_warning_log_message_id(warn_id, msg.id)

        # Yetkiliye kanıt ekleme butonları sun
        log_channel = self.bot.get_channel(config.CH_UYARI_LOG)
        evidence_view = EvidencePromptView(warn_id, msg, log_channel)
        await interaction.followup.send(
            f"✅ **{target.display_name}** kullanıcısına uyarı başarıyla uygulandı (`{warn_id}`).\n"
            f"İşlem: `{action_taken}`\n\n"
            f"İsterseniz aşağıdaki butonla bu uyarıya ekran görüntüsü kanıtı ekleyebilirsiniz:",
            view=evidence_view,
            ephemeral=True
        )

    # ------------------ PERİYODİK GÖREVLER (AF VE JAIL) ------------------

    @tasks.loop(hours=1)
    async def auto_pardon_loop(self):
        """30 gün boyunca yeni ceza almayan üyeleri otomatik affeder."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        pardon_user_ids = database.get_users_for_auto_pardon(days=30)
        for uid in pardon_user_ids:
            database.reset_user_warnings_pardon(uid)
            member = guild.get_member(uid)
            if member:
                # Tüm uyarı rollerini temizle
                warning_role_ids = [
                    config.ROLE_UYARI_1, config.ROLE_UYARI_2, config.ROLE_UYARI_3,
                    config.ROLE_UYARI_4, config.ROLE_UYARI_5,
                    config.ROLE_YETKILI_UYARI_1, config.ROLE_YETKILI_UYARI_2, config.ROLE_YETKILI_UYARI_3
                ]
                for rid in warning_role_ids:
                    r = guild.get_role(rid)
                    if r and r in member.roles:
                        try:
                            await member.remove_roles(r, reason="30 Günlük Otomatik Af: Uyarı Rolleri Temizlendi")
                        except Exception:
                            pass
                print(f"[Otomatik Af] {member.display_name} ({uid}) için 30 günlük af uygulandı.")

    @auto_pardon_loop.before_loop
    async def before_auto_pardon(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=30)
    async def jail_check_loop(self):
        """1 haftalık karantina süresi dolan kullanıcıları serbest bırakır."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        expired_user_ids = database.get_expired_jails()
        for uid in expired_user_ids:
            database.clear_user_jail(uid)
            member = guild.get_member(uid)
            if member:
                if config.ROLE_ASKIDA:
                    r_askida = guild.get_role(config.ROLE_ASKIDA)
                    if r_askida and r_askida in member.roles:
                        try:
                            await member.remove_roles(r_askida, reason="1 Haftalık Karantina Süresi Doldu")
                        except Exception:
                            pass
                print(f"[Karantina Bitişi] {member.display_name} ({uid}) karantinadan çıkarıldı.")

    @jail_check_loop.before_loop
    async def before_jail_check(self):
        await self.bot.wait_until_ready()

    # ------------------ KOMUTLAR ------------------

    @app_commands.command(name="uyari-panel", description="Sunucu Uyarı Panelini belirtilen kanala kurar.")
    @app_commands.default_permissions(administrator=True)
    async def slash_uyari_panel(self, interaction: discord.Interaction):
        await self.setup_panel_message(interaction)

    @commands.command(name="uyaripaneli")
    @commands.has_permissions(administrator=True)
    async def cmd_uyari_panel(self, ctx):
        await self.setup_panel_message(ctx)

    async def setup_panel_message(self, ctx_or_interaction):
        guild = ctx_or_interaction.guild
        panel_channel = guild.get_channel(config.CH_UYARI_PANEL)
        if not panel_channel:
            try:
                panel_channel = await guild.fetch_channel(config.CH_UYARI_PANEL)
            except Exception:
                panel_channel = None

        if not panel_channel:
            msg = "❌ Uyarı paneli kanalı bulunamadı!"
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return

        embed = discord.Embed(
            title="⚠️ Sunucu Uyarı Paneli",
            description=(
                "**Yapmanız Gerekenler:**\n"
                "→ Uyarı alacak kişiyi seç.\n"
                "→ Karşına çıkan madde numarasını doldur.\n"
                "→ Kanıt görseli varsa yükle.\n\n"
                "📌 **Katılımcı Maddeleri:** `M1-M13`, `D1-D3`, `RM1-RM18`\n"
                "🛡️ **Yetkili Maddeleri:** `Y1-Y5`"
            ),
            color=discord.Color.red()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text="GarajClass Ceza ve Denetim Sistemi")

        view = WarningPanelView(cog=self)
        await panel_channel.send(embed=embed, view=view)

        resp = f"✅ Uyarı paneli başarıyla {panel_channel.mention} kanalına kuruldu!"
        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(resp, ephemeral=True)
        else:
            await ctx_or_interaction.send(resp)

    @app_commands.command(name="uyari-iptal", description="Hatalı bir uyarıyı iptal eder ve cezalarını geri alır.")
    @app_commands.describe(uyari_id="İptal edilecek uyarının ID'si (Örn: #A8F2)")
    async def slash_uyari_iptal(self, interaction: discord.Interaction, uyari_id: str):
        if not is_staff(interaction.user):
            await interaction.response.send_message("❌ Bu komutu yalnızca yetkililer kullanabilir!", ephemeral=True)
            return
        await self.process_cancel_warning(interaction, uyari_id)

    @commands.command(name="uyariiptal")
    @commands.has_permissions(manage_messages=True)
    async def cmd_uyari_iptal(self, ctx, uyari_id: str):
        await self.process_cancel_warning(ctx, uyari_id)

    async def process_cancel_warning(self, ctx_or_interaction, uyari_id: str):
        uid = uyari_id.strip()
        if not uid.startswith("#"):
            uid = "#" + uid.upper()
        else:
            uid = uid.upper()

        warn = database.get_warning(uid)
        if not warn:
            msg = f"❌ `{uid}` kodlu bir uyarı bulunamadı!"
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return

        if warn["is_cancelled"]:
            msg = f"⚠️ `{uid}` kodlu uyarı zaten iptal edilmiş!"
            if isinstance(ctx_or_interaction, discord.Interaction):
                await ctx_or_interaction.response.send_message(msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(msg)
            return

        guild = ctx_or_interaction.guild
        target_id = warn["user_id"]
        points = warn["points"]
        warn_type = warn["warn_type"]

        # Veritabanında iptal et
        database.cancel_warning(uid)

        # Kullanıcının puanlarını ve rollerini geri al
        user_data = database.get_user_warn_data(target_id)
        member = guild.get_member(target_id)

        if warn_type == "staff":
            new_staff_count = max(0, user_data["staff_warn_count"] - 1)
            database.update_user_warn_data(
                target_id,
                user_data["total_points"],
                user_data["kademe"],
                new_staff_count,
                user_data["last_warn_date"],
                user_data["jail_until"],
                user_data["timeout_10_applied"]
            )
            # Rolleri düzelt
            if member:
                if new_staff_count == 0:
                    r1 = guild.get_role(config.ROLE_YETKILI_UYARI_1)
                    if r1 and r1 in member.roles: await member.remove_roles(r1)
                elif new_staff_count == 1:
                    r2 = guild.get_role(config.ROLE_YETKILI_UYARI_2)
                    r1 = guild.get_role(config.ROLE_YETKILI_UYARI_1)
                    if r2 and r2 in member.roles: await member.remove_roles(r2)
                    if r1: await member.add_roles(r1)
                elif new_staff_count == 2:
                    r3 = guild.get_role(config.ROLE_YETKILI_UYARI_3)
                    r2 = guild.get_role(config.ROLE_YETKILI_UYARI_2)
                    if r3 and r3 in member.roles: await member.remove_roles(r3)
                    if r2: await member.add_roles(r2)

        elif warn_type == "participant":
            new_points = max(0, user_data["total_points"] - points)
            new_kademe = 0
            if new_points >= 15: new_kademe = 5
            elif new_points >= 12: new_kademe = 4
            elif new_points >= 9: new_kademe = 3
            elif new_points >= 6: new_kademe = 2
            elif new_points >= 3: new_kademe = 1

            database.update_user_warn_data(
                target_id,
                new_points,
                new_kademe,
                user_data["staff_warn_count"],
                user_data["last_warn_date"],
                user_data["jail_until"],
                user_data["timeout_10_applied"]
            )

            # Rolleri geri çek / güncelle
            if member:
                # Tüm uyarı rollerini kaldır ve gerekeni yeniden ver
                roles_map = {
                    1: config.ROLE_UYARI_1,
                    2: config.ROLE_UYARI_2,
                    3: config.ROLE_UYARI_3,
                    4: config.ROLE_UYARI_4,
                    5: config.ROLE_UYARI_5
                }
                for k, rid in roles_map.items():
                    r = guild.get_role(rid)
                    if r:
                        if k == new_kademe:
                            await member.add_roles(r, reason="Uyarı İptali Sonrası Düzeltme")
                        elif r in member.roles:
                            await member.remove_roles(r, reason="Uyarı İptali Sonrası Temizleme")

        # Log kanalındaki mesajı güncelle (İptal damgası ekle)
        log_channel = guild.get_channel(config.CH_UYARI_LOG)
        if log_channel and warn.get("log_message_id"):
            try:
                log_msg = await log_channel.fetch_message(warn["log_message_id"])
                if log_msg and log_msg.embeds:
                    embed = log_msg.embeds[0]
                    embed.title = f"🚫 [İPTAL EDİLDİ] {embed.title}"
                    embed.color = discord.Color.light_grey()
                    canceller = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author
                    embed.add_field(
                        name="🚫 İptal Bilgisi",
                        value=f"Bu uyarı {canceller.mention} tarafından iptal edilmiş ve cezaları geri alınmıştır.",
                        inline=False
                    )
                    await log_msg.edit(embed=embed)
            except Exception as e:
                print(f"Log mesajı iptal güncelleme hatası: {e}")

        res = f"✅ `{uid}` numaralı uyarı başarıyla iptal edildi! Puanlar ve roller geriye dönük düzeltildi."
        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(res, ephemeral=True)
        else:
            await ctx_or_interaction.send(res)

    @app_commands.command(name="sicil", description="Bir kullanıcının uyarı geçmişini ve ceza puanlarını görüntüler.")
    @app_commands.describe(kullanici="Sicili görüntülenecek üye")
    async def slash_sicil(self, interaction: discord.Interaction, kullanici: discord.Member):
        if not is_staff(interaction.user):
            await interaction.response.send_message("❌ Bu komutu yalnızca yetkililer kullanabilir!", ephemeral=True)
            return
        await self.show_sicil(interaction, kullanici)

    @commands.command(name="sicil")
    async def cmd_sicil(self, ctx, member: discord.Member = None):
        if not is_staff(ctx.author):
            await ctx.send("❌ Bu komutu yalnızca yetkililer kullanabilir!")
            return
        member = member or ctx.author
        await self.show_sicil(ctx, member)

    async def show_sicil(self, ctx_or_interaction, member: discord.Member):
        user_data = database.get_user_warn_data(member.id)
        warns = database.get_user_warnings(member.id, limit=5)

        embed = discord.Embed(
            title=f"📋 Ceza Sicil Kaydı: {member.display_name}",
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(TZ)
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        embed.add_field(
            name="📊 Puan ve Kademe Durumu",
            value=(
                f"• **Toplam Ceza Puanı:** `{user_data['total_points']}`\n"
                f"• **Mevcut Kademe:** `Kademe {user_data['kademe']}`\n"
                f"• **Yetkili İhtar Sayısı:** `{user_data['staff_warn_count']}/4`\n"
                f"• **10 Puan Timeout:** {'Uygulandı' if user_data['timeout_10_applied'] else 'Uygulanmadı'}\n"
                f"• **Karantina / Jail:** {'Aktif' if user_data['jail_until'] else 'Yok'}"
            ),
            inline=False
        )

        if warns:
            warn_lines = []
            for w in warns:
                status = "~~(İptal)~~ " if w["is_cancelled"] else ""
                dt_str = w["created_at"][:10] if w["created_at"] else "Tarih Yok"
                warn_lines.append(f"• `{w['warn_id']}` [{dt_str}] {status}**{w['rule_code']}** ({w['points']} Puan) — *{w['action_taken']}*")
            embed.add_field(name="📜 Son Uyarılar (Maks. 5)", value="\n".join(warn_lines), inline=False)
        else:
            embed.add_field(name="📜 Uyarı Geçmişi", value="*Bu kullanıcının geçmiş ceza veya uyarı kaydı bulunmuyor.*", inline=False)

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx_or_interaction.send(embed=embed)

async def setup(bot):
    await bot.add_cog(WarningSystem(bot))
