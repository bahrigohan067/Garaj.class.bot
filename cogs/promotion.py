import discord
from discord.ext import commands
import config

class PromotionSelect(discord.ui.UserSelect):
    def __init__(self, action: str):
        super().__init__(placeholder="Lütfen bir kullanıcı seçin...", min_values=1, max_values=1)
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        target_member = self.values[0]
        
        # Check permissions just in case
        allowed_roles = [config.ROLE_FOUNDER, config.ROLE_HEAD_ADMIN]
        if not any(r.id in allowed_roles for r in interaction.user.roles):
            await interaction.response.send_message("Bunun için yetkiniz yok.", ephemeral=True)
            return

        if not isinstance(target_member, discord.Member):
            await interaction.response.send_message("Kullanıcı sunucuda bulunamadı.", ephemeral=True)
            return
            
        guild = interaction.guild
        
        # Define roles
        role_trial_staff = guild.get_role(config.ROLE_NEW_TRIAL_STAFF)
        role_reg_manager = guild.get_role(config.ROLE_REGISTRATION_MANAGER)
        role_staff = guild.get_role(config.ROLE_STAFF)
        role_senior_staff = guild.get_role(config.ROLE_SENIOR_STAFF)
        role_moderator = guild.get_role(config.ROLE_MODERATOR)

        if self.action == "trial_staff":
            await target_member.add_roles(role_trial_staff, role_reg_manager)
            await interaction.response.send_message(f"{target_member.mention} kullanıcısına başarıyla Trial Staff ve Registration Manager rolleri verildi.", ephemeral=True)
            
        elif self.action == "staff":
            if role_trial_staff not in target_member.roles:
                await interaction.response.send_message(f"HATA: Bu kişinin Staff olabilmesi için {role_trial_staff.mention} rolüne sahip olması zorunludur!", ephemeral=True)
                return
            await target_member.add_roles(role_staff)
            await target_member.remove_roles(role_trial_staff)
            await interaction.response.send_message(f"{target_member.mention} başarıyla Staff yapıldı.", ephemeral=True)
            
        elif self.action == "senior_staff":
            if role_staff not in target_member.roles:
                await interaction.response.send_message(f"HATA: Bu kişinin Senior Staff olabilmesi için {role_staff.mention} rolüne sahip olması zorunludur!", ephemeral=True)
                return
            await target_member.add_roles(role_senior_staff)
            await target_member.remove_roles(role_staff)
            await interaction.response.send_message(f"{target_member.mention} başarıyla Senior Staff yapıldı.", ephemeral=True)
            
        elif self.action == "moderator":
            if role_senior_staff not in target_member.roles:
                await interaction.response.send_message(f"HATA: Bu kişinin Moderatör olabilmesi için {role_senior_staff.mention} rolüne sahip olması zorunludur!", ephemeral=True)
                return
            await target_member.add_roles(role_moderator)
            await target_member.remove_roles(role_senior_staff, role_reg_manager)
            await interaction.response.send_message(f"{target_member.mention} başarıyla Moderatör yapıldı.", ephemeral=True)

class PromotionSelectView(discord.ui.View):
    def __init__(self, action: str):
        super().__init__(timeout=300)
        self.add_item(PromotionSelect(action))

class PromotionPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def check_permissions(self, interaction: discord.Interaction):
        allowed_roles = [config.ROLE_FOUNDER, config.ROLE_HEAD_ADMIN]
        if not any(r.id in allowed_roles for r in interaction.user.roles):
            await interaction.response.send_message("Bu paneli kullanmak için yeterli yetkiniz (Admin/Founder) yok.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Trial Staff", style=discord.ButtonStyle.primary, custom_id="prom_trial")
    async def btn_trial(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        await interaction.response.send_message("Trial Staff yapılacak kullanıcıyı seçin:", view=PromotionSelectView("trial_staff"), ephemeral=True)

    @discord.ui.button(label="Staff", style=discord.ButtonStyle.success, custom_id="prom_staff")
    async def btn_staff(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        await interaction.response.send_message("Staff yapılacak kullanıcıyı seçin:", view=PromotionSelectView("staff"), ephemeral=True)

    @discord.ui.button(label="Senior Staff", style=discord.ButtonStyle.danger, custom_id="prom_senior")
    async def btn_senior(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        await interaction.response.send_message("Senior Staff yapılacak kullanıcıyı seçin:", view=PromotionSelectView("senior_staff"), ephemeral=True)

    @discord.ui.button(label="Moderatör", style=discord.ButtonStyle.secondary, custom_id="prom_mod")
    async def btn_mod(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self.check_permissions(interaction): return
        await interaction.response.send_message("Moderatör yapılacak kullanıcıyı seçin:", view=PromotionSelectView("moderator"), ephemeral=True)

class Promotion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(PromotionPanelView())

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def yonetimpaneli(self, ctx):
        """Yönetim Kadro belirleme panelini gönderir."""
        embed = discord.Embed(
            title="Yönetim Kadro Belirleme",
            description="Lütfen terfi ettirmek istediğiniz rütbenin butonuna basın, ardından açılacak menüden kullanıcıyı seçin.\n\n"
                        "🔸 **Trial Staff**: Seçilen kişiye Trial Staff ve Registration Manager verir.\n"
                        "🔸 **Staff**: Seçilen kişinin Staff olmasını sağlar. (Trial Staff zorunludur).\n"
                        "🔸 **Senior Staff**: Seçilen kişinin Senior Staff olmasını sağlar. (Staff zorunludur).\n"
                        "🔸 **Moderatör**: Seçilen kişiyi Moderatör yapar. (Senior Staff zorunludur, ayrıca Senior Staff ve Registration Manager rolleri alınır).",
            color=discord.Color.dark_theme()
        )
        await ctx.send(embed=embed, view=PromotionPanelView())

async def setup(bot):
    await bot.add_cog(Promotion(bot))
