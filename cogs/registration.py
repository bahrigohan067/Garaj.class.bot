import discord
from discord.ext import commands
import config
import aiohttp
import re

async def send_to_approval(interaction, nickname, reason, roblox_url=None):
    approval_channel = interaction.guild.get_channel(config.CH_ONAY_RED)
    
    embed = discord.Embed(title="Yeni Kayıt İsteği", color=discord.Color.blue())
    embed.add_field(name="Kullanıcı", value=interaction.user.mention, inline=False)
    embed.add_field(name="Kullanıcı ID", value=interaction.user.id, inline=False)
    embed.add_field(name="Takma Ad", value=nickname, inline=False)
    embed.add_field(name="Sunucuya neden katıldı? / Oyunlar", value=reason, inline=False)
    
    if roblox_url:
        embed.add_field(name="Roblox URL/ID", value=roblox_url, inline=False)
    
    view = ApprovalView(user_id=interaction.user.id, nickname=nickname, roblox_url=roblox_url)
    await approval_channel.send(content=f"<@&{config.ROLE_REGISTRATION_MANAGER}>", embed=embed, view=view)

class RegistrationModalRoblox(discord.ui.Modal, title='Kayıt Formu (2/2) - Roblox'):
    roblox_url = discord.ui.TextInput(
        label='Roblox Profil Linki veya ID',
        style=discord.TextStyle.short,
        placeholder='https://www.roblox.com/users/... veya Nick',
        required=True
    )

    def __init__(self, nickname, reason):
        super().__init__()
        self.nickname = nickname
        self.reason = reason

    async def on_submit(self, interaction: discord.Interaction):
        await send_to_approval(interaction, self.nickname, self.reason, self.roblox_url.value)
        await interaction.response.send_message("Kayıt formun yetkililere gönderildi, lütfen bekle.", ephemeral=True)

class RobloxFormView(discord.ui.View):
    def __init__(self, nickname, reason):
        super().__init__(timeout=300)
        self.nickname = nickname
        self.reason = reason

    @discord.ui.button(label="Roblox Profilini Gir", style=discord.ButtonStyle.primary, emoji="🎮")
    async def btn_roblox(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RegistrationModalRoblox(self.nickname, self.reason))
        # Butona basıldıktan sonra mesajı silebiliriz
        try:
            await interaction.message.delete()
        except:
            pass

class RegistrationModalMain(discord.ui.Modal, title='Kayıt Formu'):
    nickname = discord.ui.TextInput(
        label='Takma Ad',
        placeholder='Oyundaki takma adınız...',
        required=True,
        max_length=32
    )
    
    reason = discord.ui.TextInput(
        label='Neden katıldınız? / Hangi oyunlar?',
        style=discord.TextStyle.long,
        placeholder='Açıklamanızı buraya yazın...',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        if "roblox" in self.reason.value.lower():
            # Discord API, bir form gönderildiğinde anında 2. bir form açmaya izin vermez.
            # Bu yüzden araya bir buton koyuyoruz.
            view = RobloxFormView(self.nickname.value, self.reason.value)
            await interaction.response.send_message(
                "Açıklamanızda **Roblox** kelimesi geçtiği için profil linkinizi girmelisiniz.\nLütfen aşağıdaki butona tıklayın:",
                view=view,
                ephemeral=True
            )
        else:
            # Geçmiyorsa direkt gönder
            await send_to_approval(interaction, self.nickname.value, self.reason.value, None)
            await interaction.response.send_message("Kayıt formun yetkililere gönderildi, lütfen bekle.", ephemeral=True)

class RegistrationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Kayıt Ol", style=discord.ButtonStyle.success, custom_id="btn_register")
    async def register_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if user has unverified role
        unverified_role = interaction.guild.get_role(config.ROLE_UNVERIFIED)
        if unverified_role in interaction.user.roles:
            await interaction.response.send_modal(RegistrationModalMain())
        else:
            await interaction.response.send_message("Sadece kayıtlı olmayan kullanıcılar bu butonu kullanabilir.", ephemeral=True)

class RejectModal(discord.ui.Modal, title='Reddetme Sebebi'):
    reason = discord.ui.TextInput(
        label='Sebep',
        style=discord.TextStyle.long,
        placeholder='Reddetme sebebini girin...',
        required=True
    )
    
    def __init__(self, user_id, message_to_edit):
        super().__init__()
        self.user_id = user_id
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.user_id)
        if member:
            try:
                await member.send(f"Sunucu kayıt başvurunuz reddedildi. Sebep: {self.reason.value}")
            except discord.Forbidden:
                pass # Can't DM user
        
        embed = self.message_to_edit.embeds[0]
        embed.color = discord.Color.red()
        
        content = f"{interaction.user.mention} tarafından Reddedildi / Sebep: {self.reason.value}"
        await self.message_to_edit.edit(content=content, embed=embed, view=None)
        await interaction.response.send_message("Reddedildi.", ephemeral=True)

class ApprovalView(discord.ui.View):
    def __init__(self, user_id: int, nickname: str, roblox_url: str = None):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.nickname = nickname
        self.roblox_url = roblox_url

    async def get_roblox_username(self, text):
        text = text.strip()
        match = re.search(r"(?:users/|/u/)(\d+)", text)
        
        user_id = None
        if match:
            user_id = match.group(1)
        elif text.isdigit():
            user_id = text
            
        async with aiohttp.ClientSession() as session:
            if user_id:
                try:
                    async with session.get(f"https://users.roblox.com/v1/users/{user_id}") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data.get("name")
                except Exception:
                    pass
            else:
                try:
                    async with session.post("https://users.roblox.com/v1/usernames/users", json={"usernames": [text], "excludeBannedUsers": False}) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data") and len(data["data"]) > 0:
                                return data["data"][0].get("name")
                except Exception:
                    pass
        return None

    @discord.ui.button(label="ONAYLA", style=discord.ButtonStyle.success, custom_id="btn_approve")
    async def approve_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        member = interaction.guild.get_member(self.user_id)
        if not member:
            await interaction.followup.send("Kullanıcı sunucuda bulunamadı.", ephemeral=True)
            return
            
        unverified_role = interaction.guild.get_role(config.ROLE_UNVERIFIED)
        verified_role = interaction.guild.get_role(config.ROLE_VERIFIED)
        
        if unverified_role in member.roles:
            await member.remove_roles(unverified_role)
        if verified_role:
            await member.add_roles(verified_role)
            
        if self.roblox_url:
            roblox_username = await self.get_roblox_username(self.roblox_url)
            if roblox_username:
                new_nick = f"{self.nickname} | {roblox_username}"
            else:
                new_nick = f"{self.nickname} | (Bulunamadı)"
        else:
            new_nick = self.nickname
            
        # Discord limit: 32 chars
        new_nick = new_nick[:32]
        
        try:
            await member.edit(nick=new_nick)
        except discord.Forbidden:
            pass # Yetki yetersizliği
            
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        
        content = f"{interaction.user.mention} tarafından Onaylandı."
        await interaction.message.edit(content=content, embed=embed, view=None)
        await interaction.followup.send("Onaylandı.", ephemeral=True)

    @discord.ui.button(label="REDDET", style=discord.ButtonStyle.danger, custom_id="btn_reject")
    async def reject_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RejectModal(self.user_id, interaction.message))

class Registration(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(RegistrationView())

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def kayitmesaji(self, ctx):
        """Kayıt ol kanalına butonu gönderir."""
        embed = discord.Embed(
            title="Kayıt Ol",
            description="Sunucuya kayıt olmak için aşağıdaki 'Kayıt Ol' butonuna basarak formu doldurun.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=RegistrationView())

async def setup(bot):
    await bot.add_cog(Registration(bot))
