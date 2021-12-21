import discord
from discord.ext import commands

from consts import DatabaseKeys


class Announcer(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.channels = client.data[DatabaseKeys.announce_channels]

    @commands.Cog.listener()
    async def on_message(self, message):
        for channel_id in self.channels:
            if channel_id == message.channel.id:
                return await message.publish()

    @commands.command(name="announceadd")
    async def announcement_channel_add(self, ctx, channel_id: int):
        """Adds announcement channel to database"""

        try:
            self.client.data[DatabaseKeys.announce_channels].append(channel_id)
        except Exception as e:
            return await ctx.message.add_reaction("❌")
        await ctx.message.add_reaction("✅")
        self.client.save_data()

    @commands.command(name="announceremove")
    async def announcement_channels_remove(self, ctx, channel_id: int):
        """Removes announcement channel from database"""

        try:
            self.client.data[DatabaseKeys.announce_channels].remove(channel_id)
        except Exception as e:
            return await ctx.message.add_reaction("❌")
        await ctx.message.add_reaction("✅")
        self.client.save_data()

    @commands.command(name="announcelist")
    async def announcement_channels_list(self, ctx):
        """Shows list of announcement channels in database"""

        embed = discord.Embed(
            title="Announcement Channels"
        )
        channels = []
        for channel_id in self.channels:
            channels.append(f"<#{channel_id}> ({channel_id})")
        embed.description = "\n".join(channels)
        await ctx.send(embed=embed)

    @commands.command(name="publish")
    async def publish(self, ctx, channel_id: int, message_id: int):
        """Publishes message"""

        channel = self.client.get_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.publish()

        await ctx.message.add_reaction("✅")


def setup(client):
    client.add_cog(Announcer(client))
