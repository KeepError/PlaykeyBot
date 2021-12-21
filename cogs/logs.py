from datetime import datetime

import discord
from discord.ext import commands


class Logs(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.client.log_error = self.log_error
        self.config = client.config

    @commands.Cog.listener()
    async def on_ready(self):
        self.errors_channel = self.client.get_channel(int(self.config["Client"]["ErrorChannelId"]))

    async def log_error(self, text, error=None):
        try:
            print(text)
            embed = discord.Embed(
                title="An error has occurred",
                description=text,
                color=0xFF0000,
                timestamp=datetime.utcnow()
            )
            if error:
                embed.add_field(name="Error text", value=error.text)
            await self.errors_channel.send(embed=embed)
        except Exception as e:
            print(e)
            print("Sending error message failed")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound) or isinstance(error, commands.DisabledCommand) or isinstance(error, commands.CheckFailure):
            return
        raise error


def setup(client):
    client.add_cog(Logs(client))
