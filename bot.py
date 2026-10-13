import discord
from discord.ext import commands
import os
from config import TOKEN, GUILD_ID
from database import init_db

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
intents.presences = True

class GararjClassBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        init_db()
        # Load extensions
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
        
        # Sync slash commands
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')

bot = GararjClassBot()

if __name__ == '__main__':
    if not TOKEN:
        print("Error: TOKEN is not set in config.py / env")
    else:
        bot.run(TOKEN)
