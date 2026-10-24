import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import pytz
import config
import database

TZ = pytz.timezone("Europe/Istanbul")

TIER_INFO = {
    "1m": {
        "name": "1 Aylık (30 Gün)",
        "short": "1 Ay",
        "days": 30,
        "channel_id": config.CH_MARKET_1M,
        "title": "🏪 GACA-COIN ROL MARKETİ — 1 AYLIK ROLLER",
        "color": discord.Color.from_rgb(52, 152, 219),  # Mavi
        "badge": "⏳ 1 Aylık Süreli Rol Mağazası"
    },
    "3m": {
        "name": "3 Aylık (90 Gün)",
        "short": "3 Ay",
        "days": 90,
        "channel_id": config.CH_MARKET_3M,
        "title": "🏪 GACA-COIN ROL MARKETİ — 3 AYLIK ROLLER",
        "color": discord.Color.from_rgb(155, 89, 182),  # Mor
        "badge": "💎 3 Aylık Avantajlı Rol Mağazası"
    },
    "perm": {
        "name": "Kalıcı (Süresiz)",
        "short": "Kalıcı",
        "days": None,
        "channel_id": config.CH_MARKET_PERM,
        "title": "👑 GACA-COIN ROL MARKETİ — KALICI ROLLER",
        "color": discord.Color.gold(),  # Altın
        "badge": "♾️ Ömür Boyu Kalıcı Rol Mağazası"
    }
}

def is_founder(member: discord.Member) -> bool:
    """Kullanıcının Founder rolüne sahip olup olmadığını kontrol eder."""
    return any(r.id == config.ROLE_FOUNDER for r in member.roles)

def make_progress_bar(current: int, total: int, length: int = 10) -> str:
    filled = int((current / total) * length) if total > 0 else 0
    filled = max(0, min(length, filled))
    return "🟩" * filled + "⬛" * (length - filled)

# ==================== FOUNDER STOK GÜNCELLEME MODAL VE MENÜLERİ ====================

class StockUpdateModal(discord.ui.Modal):
    def __init__(self, cog, tier: str, role_id: int, role_name: str):
        title_str = f"Stok Yönetimi: {role_name[:25]}"
        super().__init__(title=title_str)
        self.cog = cog
        self.tier = tier
        self.role_id = role_id  # 0 ise o kategorideki tüm roller
        self.role_name = role_name

    amount_input = discord.ui.TextInput(
        label="Stok Adedi (Sayı Girin)",
        placeholder="Örn: 5 (Markete kaç adet ekleneceğini/ayarlanacağını yazın)",
        style=discord.TextStyle.short,
        required=True,
        max_length=6
    )

    mode_input = discord.ui.TextInput(
        label="İşlem Türü: 'ekle' veya 'ayarla'",
        placeholder="'ekle' mevcut stoğa ekler, 'ayarla' doğrudan eşitler.",
        default="ekle",
        style=discord.TextStyle.short,
        required=True,
        max_length=10
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_founder(interaction.user):
            await interaction.response.send_message("❌ Bu işlemi yalnızca Founder yapabilir!", ephemeral=True)
            return

        try:
            amount = int(self.amount_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Lütfen geçerli bir tam sayı girin!", ephemeral=True)
            return

        mode_raw = self.mode_input.value.strip().lower()
        mode = "set" if mode_raw in ("ayarla", "set", "esitle", "eşitle", " sıfırla") else "add"

        await interaction.response.defer(ephemeral=True)

        if self.role_id == 0:
            # Kategorideki tüm ürünlerin stoğunu güncelle
            items = database.get_market_items(self.tier)
            for item in items:
                database.update_market_stock(self.tier, item["role_id"], amount, mode=mode)
            desc_msg = f"✅ **{TIER_INFO[self.tier]['name']}** kategorisindeki **tüm rollerin** stoğu güncellendi (`İşlem: {mode_raw.upper()}`, `Miktar: {amount}`)."
        else:
            new_stock = database.update_market_stock(self.tier, self.role_id, amount, mode=mode)
            desc_msg = (
                f"✅ <@&{self.role_id}> (**{TIER_INFO[self.tier]['name']}**) ürününün stoğu başarıyla güncellendi!\n"
                f"• **Yeni Stok:** `{new_stock} Adet`"
            )

        # İlgili market panelini ve admin panelini otomatik yenile
        await self.cog.refresh_market_panel(interaction.guild, self.tier)
        await self.cog.refresh_admin_panel(interaction.guild)

        await interaction.followup.send(desc_msg, ephemeral=True)


class StockRoleSelectView(discord.ui.View):
    def __init__(self, cog, guild: discord.Guild, tier: str):
        super().__init__(timeout=120)
        self.cog = cog
        self.tier = tier
        items = database.get_market_items(tier)

        options = [
            discord.SelectOption(
                label="🌟 TÜM KATEGORİ ROLLERİNE TOPLU STOK",
                value="0",
                description=f"{TIER_INFO[tier]['short']} kategorisindeki tüm rollere aynı anda stok ekle/ayarla",
                emoji="🌟"
            )
        ]

        for item in items:
            role = guild.get_role(item["role_id"])
            r_name = role.name if role else f"Rol ({item['role_id']})"
            label_str = f"#{item['item_index']:02d} {r_name}"[:95]
            desc_str = f"Fiyat: {item['price']} Gaca-Coin | Mevcut Stok: {item['stock']} Adet"[:95]
            options.append(
                discord.SelectOption(
                    label=label_str,
                    value=str(item["role_id"]),
                    description=desc_str,
                    emoji="📦" if item["stock"] > 0 else "🔴"
                )
            )

        select = discord.ui.Select(
            placeholder=f"{TIER_INFO[tier]['name']} — Stok güncellenecek rolü seçin...",
            min_values=1,
            max_values=1,
            options=options[:25]
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        if not is_founder(interaction.user):
            await interaction.response.send_message("❌ Bu menüyü yalnızca Founder kullanabilir!", ephemeral=True)
            return

        selected_val = int(interaction.data["values"][0])
        if selected_val == 0:
            r_name = f"Tüm {TIER_INFO[self.tier]['short']} Rolleri"
        else:
            role = interaction.guild.get_role(selected_val)
            r_name = role.name if role else f"Rol {selected_val}"

        await interaction.response.send_modal(StockUpdateModal(self.cog, self.tier, selected_val, r_name))


class FounderCoinManageModal(discord.ui.Modal, title="🪙 Üyeye Gaca-Coin Ekle / Çıkar"):
    def __init__(self, cog, target_member: discord.Member):
        super().__init__()
        self.cog = cog
        self.target_member = target_member

    amount_input = discord.ui.TextInput(
        label="Eklenecek veya Çıkarılacak Miktar",
        placeholder="Örn: 50 (ekler) veya -20 (çıkarır)",
        style=discord.TextStyle.short,
        required=True,
        max_length=8
    )

    reason_input = discord.ui.TextInput(
        label="Açıklama / Sebep (Opsiyonel)",
        placeholder="Örn: Etkinlik ödülü, telafi vb.",
        style=discord.TextStyle.short,
        required=False,
        max_length=150
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not is_founder(interaction.user):
            await interaction.response.send_message("❌ Bu işlemi yalnızca Founder yapabilir!", ephemeral=True)
            return

        try:
            amount = int(self.amount_input.value.strip())
        except ValueError:
            await interaction.response.send_message("❌ Lütfen geçerli bir sayı girin (Örn: `50` veya `-20`).", ephemeral=True)
            return

        new_balance = database.adjust_user_coins(self.target_member.id, amount)
        reason = self.reason_input.value.strip() if self.reason_input.value else "Founder Yönetimi"

        # Log kanalına bilgi gönder
        await self.cog.send_coin_admin_log(interaction.guild, self.target_member, interaction.user, amount, new_balance, reason)

        sign = f"+{amount}" if amount >= 0 else str(amount)
        await interaction.response.send_message(
            f"✅ **{self.target_member.display_name}** kullanıcısının bakiyesi **{sign} Gaca-Coin** güncellendi.\n"
            f"• **Yeni Bakiye:** `{new_balance} Gaca-Coin` 🪙",
            ephemeral=True
        )


class FounderCoinUserSelectView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=60)
        self.cog = cog

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Gaca-Coin eklenecek/çıkarılacak üyeyi seçin...", min_values=1, max_values=1)
    async def select_user(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        if not is_founder(interaction.user):
            await interaction.response.send_message("❌ Bu işlemi yalnızca Founder yapabilir!", ephemeral=True)
            return
        target = select.values[0]
        member = interaction.guild.get_member(target.id) or await interaction.guild.fetch_member(target.id)
        await interaction.response.send_modal(FounderCoinManageModal(self.cog, member))


# ==================== ANA GACA-COIN & MARKET SİSTEMİ COG ====================

class CoinMarketSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_coin_loop.start()
        self.role_expiry_loop.start()

    def cog_unload(self):
        self.voice_coin_loop.cancel()
        self.role_expiry_loop.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot açıldığında panelleri kontrol eder; eksik olan varsa otomatik kurar, varsa günceller."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return
        print("[Gaca-Coin & Market] Market ve Stok panelleri senkronize ediliyor...")
        await self.ensure_all_panels(guild)

    # ------------------ PANEL OLUŞTURMA VE YENİLEME ------------------

    def build_market_embed_and_view(self, guild: discord.Guild, tier: str):
        info = TIER_INFO[tier]
        items = database.get_market_items(tier)
        divider = "\n\n***\n\n"

        lines = []
        view = discord.ui.View(timeout=None)

        for item in items:
            idx = item["item_index"]
            r_id = item["role_id"]
            price = item["price"]
            stock = item["stock"]
            role = guild.get_role(r_id)
            role_mention = f"<@&{r_id}>"
            role_name = role.name if role else f"Rol #{idx}"

            if stock > 0:
                stock_badge = f"🟢 `Stok: {stock} Adet`"
                btn_style = discord.ButtonStyle.success
                btn_emoji = "🛒"
            else:
                stock_badge = "🔴 `Stok: 0 (Tükendi)`"
                btn_style = discord.ButtonStyle.secondary
                btn_emoji = "🔒"

            lines.append(f"`#{idx:02d}` • {role_mention} — **{price} Gaca-Coin** 🪙 ➔ {stock_badge}")

            # Buton etiketi (Maks 80 karakter)
            short_name = role_name[:22]
            btn_label = f"#{idx:02d} {short_name} | {price} Coin ({stock})"
            view.add_item(
                discord.ui.Button(
                    label=btn_label,
                    style=btn_style,
                    emoji=btn_emoji,
                    custom_id=f"market_buy:{tier}:{r_id}"
                )
            )

        # En sona Bakiyem & Aktif Rollerim butonu ekle
        view.add_item(
            discord.ui.Button(
                label="Bakiyem & Aktif Rollerim",
                style=discord.ButtonStyle.primary,
                emoji="💰",
                custom_id=f"market_balance:{tier}"
            )
        )

        duration_desc = (
            f"Bu mağazadan alacağınız roller **{info['name']}** boyunca hesabınızda aktif kalır. "
            "Süre tamamlandığında bot tarafından otomatik olarak kaldırılır ve dilerseniz yeniden satın alabilirsiniz."
            if info["days"]
            else "Bu mağazadan alacağınız roller **Ömür Boyu (Kalıcı)** olarak hesabınızda kalır!"
        )

        description = (
            f"### {info['badge']}\n"
            f"{duration_desc}\n\n"
            "🪙 **Nasıl Gaca-Coin Kazanılır?**\n"
            "• 💬 **Sohbet Aktifliği:** Sunucuda yazdığınız her **20 mesajda +1 Gaca-Coin**\n"
            "• 🎙️ **Ses Aktifliği:** Ses kanallarında geçirdiğiniz her **5 dakikada +1 Gaca-Coin**\n"
            f"• 📊 **Kazanım Takibi:** Kazandığınız tüm coin'ler anlık olarak <#{config.CH_COIN_LOG}> kanalına yansır!"
            f"{divider}"
            "### 🛍️ Ürün Listesi & Güncel Stoklar\n"
            + "\n".join(lines)
            + f"{divider}"
            "### 📌 Satın Alma Kuralları\n"
            "• Aşağıdaki butonlardan almak istediğiniz ürüne tıklayarak **anında** rolünüzü teslim alabilirsiniz.\n"
            "• Bir ürünü aynı anda **1 kere** kullanabilirsiniz. Süreli rol aldıysanız süresi bitince tekrar alabilirsiniz.\n"
            "• Kendi **Gaca-Coin** bakiyenizi ve aktif rol sürelerinizi görmek için **💰 Bakiyem & Aktif Rollerim** butonuna tıklayın."
        )

        embed = discord.Embed(
            title=info["title"],
            description=description,
            color=info["color"],
            timestamp=datetime.datetime.now(TZ)
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(
            text=f"GarajClass Gaca-Coin Ekonomi & Rol Market Sistemi • {info['name']}",
            icon_url=guild.icon.url if guild.icon else None
        )
        return embed, view

    def build_admin_embed_and_view(self, guild: discord.Guild):
        divider = "\n\n***\n\n"
        sections = []

        for tier_key in ("1m", "3m", "perm"):
            info = TIER_INFO[tier_key]
            items = database.get_market_items(tier_key)
            item_lines = []
            for it in items:
                st = it["stock"]
                dot = "🟢" if st > 0 else "🔴"
                item_lines.append(f"`#{it['item_index']:02d}` <@&{it['role_id']}> (`{it['price']} 🪙`) ➔ {dot} **Stok: {st}**")
            sections.append(f"### 📦 {info['name']} (<#{info['channel_id']}>)\n" + "\n".join(item_lines))

        description = (
            "### 🛡️ Founder Market & Stok Yönetim Merkezi\n"
            f"Bu panel yalnızca <@&{config.ROLE_FOUNDER}> yetkisine sahip yöneticiler tarafından kullanılabilir.\n"
            "Aşağıdaki butonları kullanarak istediğiniz kategorideki bir rolü seçip **stok ekleyebilir**, **stoğu sıfırlayabilir** "
            "veya üyelere **Gaca-Coin** tanımlayabilirsiniz. Yapılan her stok değişikliği ilgili market kanalında **anında** güncellenir!"
            f"{divider}"
            + divider.join(sections)
        )

        embed = discord.Embed(
            title="🛠️ GACA-COIN MARKET — FOUNDER STOK KONTROL PANELİ",
            description=description[:4090],
            color=discord.Color.dark_gold(),
            timestamp=datetime.datetime.now(TZ)
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(
            text="GarajClass Founder Özel Stok & Ekonomi Yönetim Paneli",
            icon_url=guild.icon.url if guild.icon else None
        )

        view = discord.ui.View(timeout=None)
        view.add_item(discord.ui.Button(label="1 Aylık Stok Yönet", style=discord.ButtonStyle.primary, emoji="📦", custom_id="market_admin:stock_1m", row=0))
        view.add_item(discord.ui.Button(label="3 Aylık Stok Yönet", style=discord.ButtonStyle.primary, emoji="💎", custom_id="market_admin:stock_3m", row=0))
        view.add_item(discord.ui.Button(label="Kalıcı Stok Yönet", style=discord.ButtonStyle.primary, emoji="👑", custom_id="market_admin:stock_perm", row=0))
        view.add_item(discord.ui.Button(label="Üyeye Coin Ekle / Çıkar", style=discord.ButtonStyle.success, emoji="🪙", custom_id="market_admin:coin_manage", row=1))
        view.add_item(discord.ui.Button(label="Tüm Panelleri Yenile", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="market_admin:refresh_all", row=1))

        return embed, view

    async def refresh_market_panel(self, guild: discord.Guild, tier: str, force_new: bool = False):
        info = TIER_INFO[tier]
        channel = guild.get_channel(info["channel_id"])
        if not channel:
            try:
                channel = await guild.fetch_channel(info["channel_id"])
            except Exception:
                return

        embed, view = self.build_market_embed_and_view(guild, tier)
        saved = database.get_market_panel(tier)

        if saved and not force_new:
            try:
                msg = await channel.fetch_message(saved["message_id"])
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        # Mevcut mesaj bulunamadıysa veya force_new ise yeni gönder
        try:
            new_msg = await channel.send(embed=embed, view=view)
            database.save_market_panel(tier, channel.id, new_msg.id)
        except Exception as e:
            print(f"[Market Panel Hatası - {tier}]: {e}")

    async def refresh_admin_panel(self, guild: discord.Guild, force_new: bool = False):
        channel = guild.get_channel(config.CH_MARKET_ADMIN)
        if not channel:
            try:
                channel = await guild.fetch_channel(config.CH_MARKET_ADMIN)
            except Exception:
                return

        embed, view = self.build_admin_embed_and_view(guild)
        saved = database.get_market_panel("admin")

        if saved and not force_new:
            try:
                msg = await channel.fetch_message(saved["message_id"])
                await msg.edit(embed=embed, view=view)
                return
            except Exception:
                pass

        try:
            new_msg = await channel.send(embed=embed, view=view)
            database.save_market_panel("admin", channel.id, new_msg.id)
        except Exception as e:
            print(f"[Admin Market Panel Hatası]: {e}")

    async def ensure_all_panels(self, guild: discord.Guild, force_new: bool = False):
        await self.refresh_admin_panel(guild, force_new=force_new)
        for tier in ("1m", "3m", "perm"):
            await self.refresh_market_panel(guild, tier, force_new=force_new)

    # ------------------ BUTON ETKİLEŞİMLERİ (SATIN ALMA & YÖNETİM) ------------------

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component:
            return
        if not interaction.data or "custom_id" not in interaction.data:
            return

        custom_id = interaction.data["custom_id"]

        # 1. MARKET SATIN ALMA BUTONLARI
        if custom_id.startswith("market_buy:"):
            parts = custom_id.split(":")
            if len(parts) != 3:
                return
            _, tier, role_id_str = parts
            role_id = int(role_id_str)
            await self.handle_buy_product(interaction, tier, role_id)

        # 2. BAKİYEM & AKTİF ROLLERİM BUTONU
        elif custom_id.startswith("market_balance:"):
            await self.handle_show_balance(interaction, interaction.user, ephemeral=True)

        # 3. FOUNDER STOK & YÖNETİM BUTONLARI
        elif custom_id.startswith("market_admin:"):
            if not is_founder(interaction.user):
                await interaction.response.send_message(
                    f"❌ Bu yönetim panelini yalnızca <@&{config.ROLE_FOUNDER}> rolüne sahip kişiler kullanabilir!",
                    ephemeral=True
                )
                return

            action = custom_id.split(":")[1]
            if action in ("stock_1m", "stock_3m", "stock_perm"):
                tier = action.replace("stock_", "")
                view = StockRoleSelectView(self, interaction.guild, tier)
                await interaction.response.send_message(
                    f"📦 **{TIER_INFO[tier]['name']}** kategorisi için stok güncellemek istediğiniz rolü aşağıdan seçin:",
                    view=view,
                    ephemeral=True
                )
            elif action == "coin_manage":
                view = FounderCoinUserSelectView(self)
                await interaction.response.send_message(
                    "🪙 **Gaca-Coin** eklemek veya çıkarmak istediğiniz kullanıcıyı seçin:",
                    view=view,
                    ephemeral=True
                )
            elif action == "refresh_all":
                await interaction.response.defer(ephemeral=True)
                await self.ensure_all_panels(interaction.guild, force_new=False)
                await interaction.followup.send("✅ Tüm market panelleri ve stok tabloları başarıyla senkronize edildi!", ephemeral=True)

    async def handle_buy_product(self, interaction: discord.Interaction, tier: str, role_id: int):
        member = interaction.user
        guild = interaction.guild
        item = database.get_market_item(tier, role_id)

        if not item:
            await interaction.response.send_message("❌ Bu ürün sistemde bulunamadı!", ephemeral=True)
            return

        role = guild.get_role(role_id)
        if not role:
            await interaction.response.send_message(
                f"❌ <@&{role_id}> rolü sunucuda bulunamadı! Lütfen yetkililere bildirin.",
                ephemeral=True
            )
            return

        # 1. Kullanıcının bu role zaten sahip olup olmadığını kontrol et
        if role in member.roles or database.has_active_role_purchase(member.id, role_id):
            await interaction.response.send_message(
                f"⚠️ **Bu Ürünü Zaten Kullanıyorsunuz!**\n\n"
                f"• {role.mention} rolü şu anda hesabınızda **aktif** durumdadır.\n"
                f"• Bir ürünü aynı anda yalnızca **1 kere** kullanabilirsiniz.\n"
                f"• *(Eğer süreli bir rol aldıysanız, rol süreniz sona erdiğinde bu ürünü tekrar satın alabilirsiniz.)*",
                ephemeral=True
            )
            return

        # 2. Stok kontrolü
        if item["stock"] <= 0:
            await interaction.response.send_message(
                f"🔒 **Stok Tükendi!**\n\n"
                f"• {role.mention} (**{TIER_INFO[tier]['name']}**) ürününün stoğu şu anda **0**.\n"
                f"• <@&{config.ROLE_FOUNDER}> tarafından stok yenilendiğinde tekrar satın alabilirsiniz!",
                ephemeral=True
            )
            return

        # 3. Bakiye kontrolü
        coin_data = database.get_user_coin_data(member.id)
        price = item["price"]
        if coin_data["coins"] < price:
            needed = price - coin_data["coins"]
            await interaction.response.send_message(
                f"❌ **Yetersiz Gaca-Coin Bakiyesi!**\n\n"
                f"• **Seçilen Ürün:** {role.mention} (`{TIER_INFO[tier]['name']}`)\n"
                f"• **Ürün Fiyatı:** `{price} Gaca-Coin` 🪙\n"
                f"• **Mevcut Bakiyeniz:** `{coin_data['coins']} Gaca-Coin` 🪙\n"
                f"• **Gereken Ekstra Coin:** `{needed} Gaca-Coin` daha kazanmalısınız!\n\n"
                f"💡 *Her 20 mesajda +1 Gaca-Coin ve ses odalarında her 5 dakikada +1 Gaca-Coin kazanabilirsiniz.*",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # 4. Süre hesapla ve satın alımı gerçekleştir
        now = datetime.datetime.now(TZ)
        days = TIER_INFO[tier]["days"]
        if days:
            expires_dt = now + datetime.timedelta(days=days)
            expires_at_str = expires_dt.isoformat()
            end_ts = int(expires_dt.timestamp())
            expiry_display = f"<t:{end_ts}:F> (<t:{end_ts}:R>)"
        else:
            expires_at_str = None
            expiry_display = "♾️ **Kalıcı (Süresiz)**"

        success, status, new_balance, new_stock = database.create_role_purchase(
            user_id=member.id,
            role_id=role_id,
            tier=tier,
            price=price,
            expires_at=expires_at_str
        )

        if not success:
            await interaction.followup.send("❌ Satın alma sırasında stok veya bakiye değiştiği için işlem tamamlanamadı.", ephemeral=True)
            return

        # 5. Rolü kullanıcıya ver
        try:
            await member.add_roles(role, reason=f"Gaca-Coin Market Satın Alımı ({TIER_INFO[tier]['name']})")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Coin düşüldü ancak botun rol verme yetkisi yetersiz kaldığı için rol verilemedi: `{e}`", ephemeral=True)
            return

        # 6. Market panelini ve Founder stok panelini güncelle
        await self.refresh_market_panel(guild, tier)
        await self.refresh_admin_panel(guild)

        # 7. Coin Log kanalına satın alma bildirimini gönder
        await self.send_purchase_log(guild, member, role, tier, price, new_balance, new_stock, expiry_display)

        # 8. Kullanıcıya onay mesajı göster
        await interaction.followup.send(
            f"🎉 **Satın Alma Başarılı! Hayırlı Olsun!**\n\n"
            f"• **Alınan Rol:** {role.mention}\n"
            f"• **Kategori:** `{TIER_INFO[tier]['name']}`\n"
            f"• **Ödenen Tutar:** `{price} Gaca-Coin` 🪙\n"
            f"• **Kalan Bakiyeniz:** `{new_balance} Gaca-Coin` 🪙\n"
            f"• **Bitiş Tarihi:** {expiry_display}",
            ephemeral=True
        )

    # ------------------ COIN KAZANMA SİSTEMİ (20 MESAJ & 5 DK SES) ------------------

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if message.guild.id != config.GUILD_ID:
            return

        earned, new_coins, total_msgs, progress = database.increment_user_message_coin(message.author.id)
        if earned:
            await self.send_coin_earn_log(
                guild=message.guild,
                member=message.author,
                earn_type="message",
                earned_amount=1,
                new_balance=new_coins,
                total_stat=total_msgs,
                channel_mention=message.channel.mention
            )

    @tasks.loop(minutes=1)
    async def voice_coin_loop(self):
        """Her dakika ses kanallarındaki aktif üyeleri kontrol eder; 5 dakikayı dolduranlara +1 Gaca-Coin verir."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot:
                    continue
                # AFK kanalındaysa sayma
                if guild.afk_channel and vc.id == guild.afk_channel.id:
                    continue

                earned_coins, new_coins, total_voice_mins, progress = database.increment_user_voice_minute_coin(member.id, minutes=1)
                if earned_coins > 0:
                    await self.send_coin_earn_log(
                        guild=guild,
                        member=member,
                        earn_type="voice",
                        earned_amount=earned_coins,
                        new_balance=new_coins,
                        total_stat=total_voice_mins,
                        channel_mention=vc.mention
                    )

    @voice_coin_loop.before_loop
    async def before_voice_coin_loop(self):
        await self.bot.wait_until_ready()

    # ------------------ OTONOM ROL SÜRESİ TAKİBİ ------------------

    @tasks.loop(minutes=10)
    async def role_expiry_loop(self):
        """Süresi dolan 1 Aylık ve 3 Aylık market rollerini otomatik olarak kontrol eder ve kullanıcıdan alır."""
        guild = self.bot.get_guild(config.GUILD_ID)
        if not guild:
            return

        expired_list = database.get_expired_role_purchases()
        for exp in expired_list:
            database.mark_purchase_expired(exp["id"])
            user_id = exp["user_id"]
            role_id = exp["role_id"]
            tier = exp["tier"]

            member = guild.get_member(user_id)
            if not member:
                try:
                    member = await guild.fetch_member(user_id)
                except Exception:
                    member = None

            role = guild.get_role(role_id)
            if member and role and role in member.roles:
                try:
                    await member.remove_roles(role, reason=f"Gaca-Coin Market Rol Süresi Doldu ({TIER_INFO.get(tier, {}).get('name', tier)})")
                except Exception as e:
                    print(f"[Market Rol Süre Dolumu Hatası]: {e}")

            await self.send_role_expired_log(guild, member, user_id, role_id, tier)

    @role_expiry_loop.before_loop
    async def before_role_expiry_loop(self):
        await self.bot.wait_until_ready()

    # ------------------ LOG MESAJLARI (1563256431107641476) ------------------

    async def get_coin_log_channel(self, guild: discord.Guild):
        ch = guild.get_channel(config.CH_COIN_LOG)
        if not ch:
            try:
                ch = await guild.fetch_channel(config.CH_COIN_LOG)
            except Exception:
                return None
        return ch

    async def send_coin_earn_log(self, guild: discord.Guild, member: discord.Member, earn_type: str,
                                 earned_amount: int, new_balance: int, total_stat: int, channel_mention: str):
        log_channel = await self.get_coin_log_channel(guild)
        if not log_channel:
            return

        divider = "\n\n***\n\n"
        if earn_type == "message":
            title = "🪙 Gaca-Coin Kazanıldı! (Sohbet Ödülü)"
            color = discord.Color.from_rgb(46, 204, 113)  # Zümrüt Yeşili
            activity_line = f"💬 **Kazanım Kaynağı:** Sohbet Aktifliği (`20 Mesaj Tamamlandı`)\n📍 **Mesaj Kanalı:** {channel_mention}\n📊 **Toplam Mesaj Sayısı:** `{total_stat} Mesaj`"
        else:
            title = "🪙 Gaca-Coin Kazanıldı! (Ses Kanalı Ödülü)"
            color = discord.Color.from_rgb(241, 196, 15)  # Altın Sarısı
            activity_line = f"🎙️ **Kazanım Kaynağı:** Ses Kanalı Aktifliği (`5 Dakika Tamamlandı`)\n🔊 **Bulunduğu Ses Kanalı:** {channel_mention}\n⏱️ **Toplam Ses Süresi:** `{total_stat} Dakika`"

        desc = (
            f"🎉 Tebrikler {member.mention}! Sunucu aktifliğiniz sayesinde **+{earned_amount} Gaca-Coin** kazandınız!"
            f"{divider}"
            f"### 📌 Kazanım Detayları\n"
            f"{activity_line}\n"
            f"• **Kazanılan Miktar:** `+{earned_amount} Gaca-Coin` 🪙\n"
            f"• **Güncel Bakiyeniz:** `{new_balance} Gaca-Coin` 🪙"
            f"{divider}"
            f"🛍️ *Kazandığınız Gaca-Coin'leri <#{config.CH_MARKET_1M}>, <#{config.CH_MARKET_3M}> ve <#{config.CH_MARKET_PERM}> kanallarında harcayabilirsiniz!*"
        )

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color,
            timestamp=datetime.datetime.now(TZ)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text="GarajClass Gaca-Coin Kazanım Bildirimi",
            icon_url=guild.icon.url if guild.icon else None
        )

        try:
            await log_channel.send(content=f"{member.mention}", embed=embed)
        except Exception as e:
            print(f"[Coin Log Gönderim Hatası]: {e}")

    async def send_purchase_log(self, guild: discord.Guild, member: discord.Member, role: discord.Role,
                                tier: str, price: int, new_balance: int, new_stock: int, expiry_display: str):
        log_channel = await self.get_coin_log_channel(guild)
        if not log_channel:
            return

        divider = "\n\n***\n\n"
        desc = (
            f"🛒 {member.mention} mağazadan yeni bir rol satın aldı!"
            f"{divider}"
            f"### 🛍️ Satın Alma Özeti\n"
            f"• **Alıcı:** {member.mention} (`{member.name}`)\n"
            f"• **Satın Alınan Rol:** {role.mention}\n"
            f"• **Paket Süresi:** `{TIER_INFO[tier]['name']}`\n"
            f"• **Harcanan Coin:** `-{price} Gaca-Coin` 🪙\n"
            f"• **Kalan Bakiye:** `{new_balance} Gaca-Coin` 🪙\n"
            f"• **Kalan Ürün Stoğu:** `{new_stock} Adet`\n"
            f"• **Rol Bitiş Tarihi:** {expiry_display}"
        )

        embed = discord.Embed(
            title="🛍️ Rol Marketi Satın Alımı",
            description=desc,
            color=discord.Color.purple(),
            timestamp=datetime.datetime.now(TZ)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text="GarajClass Gaca-Coin Market Logu",
            icon_url=guild.icon.url if guild.icon else None
        )

        try:
            await log_channel.send(content=f"{member.mention}", embed=embed)
        except Exception:
            pass

    async def send_role_expired_log(self, guild: discord.Guild, member: discord.Member, user_id: int, role_id: int, tier: str):
        log_channel = await self.get_coin_log_channel(guild)
        tier_name = TIER_INFO.get(tier, {}).get("name", tier)

        embed = discord.Embed(
            title="⌛ Süreli Market Rolünün Süresi Doldu",
            description=(
                f"<@{user_id}> kullanıcısının **{tier_name}** süreli <@&{role_id}> rolünün kullanım süresi tamamlanmıştır.\n\n"
                "• Rol kullanıcının üzerinden otomatik olarak kaldırılmıştır.\n"
                "• Kullanıcı dilerse marketten aynı ürünü **tekrar satın alabilir**."
            ),
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(TZ)
        )
        embed.set_footer(text="GarajClass Otonom Rol Süresi Takip Sistemi")

        if log_channel:
            try:
                await log_channel.send(content=f"<@{user_id}>", embed=embed)
            except Exception:
                pass

        if member:
            try:
                await member.send(embed=embed)
            except Exception:
                pass

    async def send_coin_admin_log(self, guild: discord.Guild, target: discord.Member, admin: discord.Member,
                                  amount: int, new_balance: int, reason: str):
        log_channel = await self.get_coin_log_channel(guild)
        if not log_channel:
            return

        sign = f"+{amount}" if amount >= 0 else str(amount)
        embed = discord.Embed(
            title="🛠️ Founder Bakiye Güncellemesi",
            description=(
                f"• **Kullanıcı:** {target.mention}\n"
                f"• **İşlemi Yapan:** {admin.mention}\n"
                f"• **Eklenen/Çıkarılan:** `{sign} Gaca-Coin` 🪙\n"
                f"• **Yeni Bakiye:** `{new_balance} Gaca-Coin` 🪙\n"
                f"• **Açıklama:** {reason}"
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(TZ)
        )
        try:
            await log_channel.send(content=f"{target.mention}", embed=embed)
        except Exception:
            pass

    # ------------------ BAKİYE, AKTİF ROLLER VE LİDERLİK KOMUTLARI ------------------

    async def handle_show_balance(self, ctx_or_interaction, member: discord.Member, ephemeral: bool = False):
        data = database.get_user_coin_data(member.id)
        active_purchases = database.get_user_active_purchases(member.id)
        divider = "\n\n***\n\n"

        msg_bar = make_progress_bar(data["msg_progress"], 20, length=10)
        voice_bar = make_progress_bar(data["voice_minutes"], 5, length=5)

        if active_purchases:
            purchase_lines = []
            for p in active_purchases:
                t_short = TIER_INFO.get(p["tier"], {}).get("short", p["tier"])
                if p["expires_at"]:
                    exp_dt = datetime.datetime.fromisoformat(p["expires_at"])
                    exp_ts = int(exp_dt.timestamp())
                    exp_str = f"Bitiş: <t:{exp_ts}:R> (<t:{exp_ts}:d>)"
                else:
                    exp_str = "♾️ **Kalıcı**"
                purchase_lines.append(f"• <@&{p['role_id']}> (`{t_short}`) — {exp_str}")
            roles_section = "\n".join(purchase_lines)
        else:
            roles_section = "*Şu anda marketten alınmış aktif bir rolünüz bulunmuyor.*"

        desc = (
            f"### 💰 Cüzdan & Bakiye Özeti\n"
            f"• **Mevcut Bakiye:** `{data['coins']} Gaca-Coin` 🪙\n"
            f"• **Toplam Kazanılan:** `{data['total_earned']} Gaca-Coin`\n"
            f"• **Market Harcaması:** `{data['total_spent']} Gaca-Coin`"
            f"{divider}"
            f"### 📈 Sonraki Coin İlerlemesi\n"
            f"💬 **Mesaj İlerlemesi:** `{data['msg_progress']} / 20 Mesaj` *(Toplam: {data['total_messages']})*\n"
            f"{msg_bar}\n\n"
            f"🎙️ **Ses İlerlemesi:** `{data['voice_minutes']} / 5 Dakika` *(Toplam: {data['total_voice_minutes']} dk)*\n"
            f"{voice_bar}"
            f"{divider}"
            f"### 🎭 Aktif Market Rolleriniz\n"
            f"{roles_section}"
        )

        embed = discord.Embed(
            title=f"🪙 Gaca-Coin Cüzdanı — {member.display_name}",
            description=desc,
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(TZ)
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="GarajClass Gaca-Coin Ekonomi Sistemi")

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        else:
            await ctx_or_interaction.send(embed=embed)

    @app_commands.command(name="bakiye", description="Gaca-Coin bakiyenizi, ilerlemenizi ve aktif market rollerinizi gösterir.")
    @app_commands.describe(kullanici="Bakiyesine bakılacak üye (opsiyonel)")
    async def slash_bakiye(self, interaction: discord.Interaction, kullanici: discord.Member = None):
        target = kullanici or interaction.user
        await self.handle_show_balance(interaction, target, ephemeral=False)

    @commands.command(name="bakiye", aliases=["coin", "gacacoin", "cuzdan"])
    async def cmd_bakiye(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        await self.handle_show_balance(ctx, target, ephemeral=False)

    @app_commands.command(name="zenginler", description="Sunucudaki en çok Gaca-Coin'e sahip ilk 10 üyeyi listeler.")
    async def slash_zenginler(self, interaction: discord.Interaction):
        await self.show_leaderboard(interaction)

    @commands.command(name="zenginler", aliases=["coinlider", "topcoin"])
    async def cmd_zenginler(self, ctx):
        await self.show_leaderboard(ctx)

    async def show_leaderboard(self, ctx_or_interaction):
        top_users = database.get_top_coin_users(limit=10)
        if not top_users:
            lines = ["*Henüz Gaca-Coin kazanan kullanıcı bulunmuyor.*"]
        else:
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for idx, u in enumerate(top_users, start=1):
                badge = medals[idx - 1] if idx <= 3 else f"`#{idx:02d}`"
                lines.append(
                    f"{badge} <@{u['user_id']}> — **{u['coins']} Gaca-Coin** 🪙 *(Toplam Kazanım: {u['total_earned']})*"
                )

        embed = discord.Embed(
            title="🏆 Gaca-Coin Zenginler Sıralaması (Top 10)",
            description="\n".join(lines),
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(TZ)
        )
        embed.set_footer(text="GarajClass Gaca-Coin Ekonomi Sistemi")

        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.send(embed=embed)

    @app_commands.command(name="market-kur", description="Founder Stok Paneli ve 3 Market Panelini (1 Ay, 3 Ay, Kalıcı) ilgili kanallara kurar.")
    async def slash_market_kur(self, interaction: discord.Interaction):
        if not is_founder(interaction.user):
            await interaction.response.send_message(
                f"❌ Bu komutu yalnızca <@&{config.ROLE_FOUNDER}> rolüne sahip kişiler kullanabilir!",
                ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        await self.ensure_all_panels(interaction.guild, force_new=True)
        await interaction.followup.send(
            "✅ **Tüm Market ve Yönetim Panelleri Başarıyla Kuruldu!**\n"
            f"• 🛠️ **Founder Stok Paneli:** <#{config.CH_MARKET_ADMIN}>\n"
            f"• ⏳ **1 Aylık Market:** <#{config.CH_MARKET_1M}>\n"
            f"• 💎 **3 Aylık Market:** <#{config.CH_MARKET_3M}>\n"
            f"• 👑 **Kalıcı Market:** <#{config.CH_MARKET_PERM}>",
            ephemeral=True
        )

    @commands.command(name="marketkur", aliases=["marketpaneli"])
    async def cmd_market_kur(self, ctx):
        if not is_founder(ctx.author):
            await ctx.send(f"❌ Bu komutu yalnızca <@&{config.ROLE_FOUNDER}> rolüne sahip kişiler kullanabilir!")
            return
        await self.ensure_all_panels(ctx.guild, force_new=True)
        await ctx.send("✅ Tüm Market ve Founder Stok Yönetim panelleri ilgili kanallara başarıyla kuruldu!")

async def setup(bot):
    await bot.add_cog(CoinMarketSystem(bot))
