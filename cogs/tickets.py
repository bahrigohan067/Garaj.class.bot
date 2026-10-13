import discord
from discord.ext import commands
from discord import app_commands
import config
import database
import datetime

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Kapat", style=discord.ButtonStyle.danger, custom_id="btn_close_ticket", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Bilet kapatılıyor...", ephemeral=True)
        channel = interaction.channel
        
        # Log to İşlemler
        log_channel = interaction.guild.get_channel(config.CH_ISLEMLER)
        
        # We could try to fetch messages to count them
        # Let's count messages per user in this channel
        messages = [msg async for msg in channel.history(limit=1000)]
        user_msg_counts = {}
        for msg in messages:
            if not msg.author.bot:
                user_msg_counts[msg.author.mention] = user_msg_counts.get(msg.author.mention, 0) + 1
                
        details = "\n".join([f"{user}: {count} mesaj" for user, count in user_msg_counts.items()])
        if not details:
            details = "Mesaj bulunamadı."
            
        embed = discord.Embed(title="Bilet Kapatıldı", color=discord.Color.red())
        embed.add_field(name="Kanal", value=channel.name, inline=False)
        embed.add_field(name="Kapatan", value=interaction.user.mention, inline=False)
        embed.add_field(name="Mesaj Detayları", value=details, inline=False)
        
        if log_channel:
            await log_channel.send(embed=embed)
            
        # Add stats for the staff member closing it if they are staff
        staff_roles = [config.ROLE_FOUNDER, config.ROLE_HEAD_ADMIN, config.ROLE_MODERATOR, config.ROLE_SUPPORT_TEAM, config.ROLE_TRIAL_MOD]
        is_staff = any(r.id in staff_roles for r in interaction.user.roles)
        if is_staff:
            database.add_ticket_closed(interaction.user.id)
            
        await channel.delete()

class TicketCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
    @discord.ui.button(label="Ticket Aç", style=discord.ButtonStyle.success, custom_id="btn_create_ticket", emoji="🎫")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        category = interaction.channel.category
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        # Add staff roles
        staff_roles = [config.ROLE_FOUNDER, config.ROLE_HEAD_ADMIN, config.ROLE_MODERATOR, config.ROLE_SUPPORT_TEAM, config.ROLE_TRIAL_MOD, config.ROLE_SENIOR_STAFF, config.ROLE_STAFF, config.ROLE_NEW_TRIAL_STAFF]
        for r_id in staff_roles:
            role = interaction.guild.get_role(r_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"destek-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        
        embed = discord.Embed(
            title="Destek Talebi",
            description=f"{interaction.user.mention} bir destek talebi oluşturdu.\nYetkililer en kısa sürede ilgilenecek.",
            color=discord.Color.purple()
        )
        
        mentions = f"<@&{config.ROLE_SENIOR_STAFF}> <@&{config.ROLE_STAFF}> <@&{config.ROLE_NEW_TRIAL_STAFF}>"
        await ticket_channel.send(content=mentions, embed=embed, view=TicketCloseView())
        await ticket_channel.send(f"[ {interaction.user.mention} Merhabalar, size nasıl yardımcı olabiliriz? Sorununuzu detaylıca yazarsanız sevinirim. ]")
        
        await interaction.response.send_message(f"Biletin oluşturuldu: {ticket_channel.mention}", ephemeral=True)

class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(TicketCreateView())
        self.bot.add_view(TicketCloseView())

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def ticketmesaji(self, ctx):
        """Ticket kanalına butonu gönderir."""
        embed = discord.Embed(
            title="🎫 Destek Sistemi",
            description="Destek almak için aşağıdaki butona tıkla, senin için özel bir kanal açılacak.",
            color=discord.Color.dark_purple()
        )
        await ctx.send(embed=embed, view=TicketCreateView())

    @app_commands.command(name="ekle", description="Bilete başka bir kullanıcı ekler.")
    async def ekle(self, interaction: discord.Interaction, kullanici: discord.Member):
        if "destek-" not in interaction.channel.name:
            await interaction.response.send_message("Bu komut sadece bilet kanallarında kullanılabilir.", ephemeral=True)
            return
            
        await interaction.channel.set_permissions(kullanici, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"{kullanici.mention} bilete eklendi.")

async def setup(bot):
    await bot.add_cog(Tickets(bot))
