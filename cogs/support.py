import discord
from discord.ext import commands
import config
import database

class SupportEndModal(discord.ui.Modal, title='Destek Sonucu'):
    resolution = discord.ui.TextInput(
        label='Nasıl Çözüldü?',
        style=discord.TextStyle.long,
        placeholder='Sorun nasıl çözüldü veya destek nasıl sonuçlandı?',
        required=True
    )
    
    def __init__(self, mod: discord.Member, target_user: discord.Member, message_to_edit: discord.Message):
        super().__init__()
        self.mod = mod
        self.target_user = target_user
        self.message_to_edit = message_to_edit

    async def on_submit(self, interaction: discord.Interaction):
        # Empty channel (disconnect both or just target user?)
        # "Kanalı boşaltır" -> let's disconnect target user. Mod might want to stay or we disconnect both.
        # Let's disconnect target user.
        if self.target_user.voice and self.target_user.voice.channel and self.target_user.voice.channel.id == config.CH_DESTEK_1:
            try:
                await self.target_user.move_to(None)
            except discord.HTTPException:
                pass
                
        # Log to İşlemler
        log_channel = interaction.guild.get_channel(config.CH_ISLEMLER)
        if log_channel:
            embed = discord.Embed(title="Destek Tamamlandı", color=discord.Color.green())
            embed.add_field(name="Yetkili", value=self.mod.mention, inline=False)
            embed.add_field(name="Kullanıcı", value=self.target_user.mention, inline=False)
            embed.add_field(name="Sonuç", value=self.resolution.value, inline=False)
            await log_channel.send(embed=embed)
            
        database.add_support_finished(self.mod.id)
        
        await self.message_to_edit.delete()
        await interaction.response.send_message("Destek başarıyla sonlandırıldı ve loglandı.", ephemeral=True)


class ActiveSupportView(discord.ui.View):
    def __init__(self, mod_id: int, target_user_id: int):
        super().__init__(timeout=None)
        self.mod_id = mod_id
        self.target_user_id = target_user_id
        
    @discord.ui.button(label="Desteği Bitir", style=discord.ButtonStyle.success, custom_id="btn_end_support")
    async def end_support_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.mod_id:
            await interaction.response.send_message("Sadece bu desteği alan yetkili işlemi bitirebilir.", ephemeral=True)
            return
            
        target_user = interaction.guild.get_member(self.target_user_id)
        if not target_user:
            await interaction.response.send_message("Kullanıcı sunucudan ayrılmış.", ephemeral=True)
            await interaction.message.delete()
            return
            
        await interaction.response.send_modal(SupportEndModal(interaction.user, target_user, interaction.message))

    @discord.ui.button(label="Boş (Troll/Ses Yok)", style=discord.ButtonStyle.secondary, custom_id="btn_empty_support")
    async def empty_support_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.mod_id:
            await interaction.response.send_message("Sadece bu desteği alan yetkili işlemi bitirebilir.", ephemeral=True)
            return
            
        target_user = interaction.guild.get_member(self.target_user_id)
        if target_user and target_user.voice and target_user.voice.channel and target_user.voice.channel.id == config.CH_DESTEK_1:
            try:
                await target_user.move_to(None)
            except discord.HTTPException:
                pass
                
        # Log as empty
        log_channel = interaction.guild.get_channel(config.CH_ISLEMLER)
        if log_channel:
            embed = discord.Embed(title="Destek Boş Geçti", color=discord.Color.light_grey())
            embed.add_field(name="Yetkili", value=interaction.user.mention, inline=False)
            embed.add_field(name="Kullanıcı", value=f"<@{self.target_user_id}>", inline=False)
            embed.add_field(name="Durum", value="Troll / Ses Yok", inline=False)
            await log_channel.send(embed=embed)
            
        database.add_support_finished(self.mod_id)
        
        await interaction.message.delete()
        await interaction.response.send_message("İşlem boş olarak kaydedildi.", ephemeral=True)


class IncomingSupportView(discord.ui.View):
    def __init__(self, target_user_id: int):
        super().__init__(timeout=None)
        self.target_user_id = target_user_id

    @discord.ui.button(label="Katılımcıyı Devral", style=discord.ButtonStyle.primary, custom_id="btn_take_support")
    async def take_support_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_user = interaction.guild.get_member(self.target_user_id)
        if not target_user or not target_user.voice or target_user.voice.channel.id != config.CH_DESTEK_BEKLEME:
            await interaction.response.send_message("Kullanıcı artık bekleme kanalında değil.", ephemeral=True)
            await interaction.message.delete()
            return
            
        # Move mod and user to Destek 1
        destek_1 = interaction.guild.get_channel(config.CH_DESTEK_1)
        
        try:
            if interaction.user.voice and interaction.user.voice.channel:
                await interaction.user.move_to(destek_1)
            await target_user.move_to(destek_1)
            await target_user.edit(mute=False)
        except discord.HTTPException:
            pass # Maybe they disconnected in between
            
        embed = discord.Embed(
            title="Destek Devam Ediyor",
            description=f"Yetkili: {interaction.user.mention}\nKullanıcı: {target_user.mention}\nKanal: {destek_1.mention}",
            color=discord.Color.yellow()
        )
        await interaction.message.edit(content=None, embed=embed, view=ActiveSupportView(interaction.user.id, target_user.id))
        await interaction.response.send_message("Kullanıcıyı devraldınız.", ephemeral=True)

    @discord.ui.button(label="Beklemeden Çıkar", style=discord.ButtonStyle.danger, custom_id="btn_kick_support")
    async def kick_support_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_user = interaction.guild.get_member(self.target_user_id)
        if target_user and target_user.voice and target_user.voice.channel and target_user.voice.channel.id == config.CH_DESTEK_BEKLEME:
            try:
                await target_user.move_to(None)
            except discord.HTTPException:
                pass
                
        await interaction.message.delete()
        await interaction.response.send_message("Kullanıcı bekleme kanalından atıldı.", ephemeral=True)


class VoiceSupport(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Ignore bots
        if member.bot:
            return
            
        # Joined Destek Bekleme
        if after.channel and after.channel.id == config.CH_DESTEK_BEKLEME and (not before.channel or before.channel.id != config.CH_DESTEK_BEKLEME):
            # Mute them
            if not after.mute:
                try:
                    await member.edit(mute=True)
                except discord.Forbidden:
                    pass
                    
            # Notify destek-panel
            panel_channel = member.guild.get_channel(config.CH_DESTEK_PANEL)
            if panel_channel:
                embed = discord.Embed(
                    title="Yeni Destek İsteği!",
                    description=f"{member.mention} Destek Bekleme kanalına giriş yaptı.",
                    color=discord.Color.orange()
                )
                
                # Tag Support Roles
                roles_to_tag = [config.ROLE_FOUNDER, config.ROLE_HEAD_ADMIN, config.ROLE_MODERATOR, config.ROLE_SUPPORT_TEAM, config.ROLE_TRIAL_MOD]
                mentions = " ".join([f"<@&{r}>" for r in roles_to_tag])
                
                await panel_channel.send(content=mentions, embed=embed, view=IncomingSupportView(member.id))
                
        # Handle Leaving Voice / Tracking Voice Time
        # (We will handle tracking in stats.py)

async def setup(bot):
    await bot.add_cog(VoiceSupport(bot))
