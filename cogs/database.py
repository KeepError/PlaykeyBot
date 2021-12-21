from discord.ext import commands
import json

from consts import DatabaseKeys


class Database(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.init_database()
        client.save_data = self.save_database
        client.save_data()

    def save_database(self):
        with open(self.client.config["Database"]["Filename"], "w", encoding="UTF-8") as f:
            json.dump(self.client.data, f)

    def init_database(self):
        try:
            with open(self.client.config["Database"]["Filename"], "r", encoding="UTF-8") as f:
                self.client.data = json.load(f)
        except FileNotFoundError:
            self.client.data = {}
        self.client.data[DatabaseKeys.announce_channels] = self.client.data.get(DatabaseKeys.announce_channels, [])
        self.client.data[DatabaseKeys.vk] = self.client.data.get(DatabaseKeys.vk, {})
        self.client.data[DatabaseKeys.vk][DatabaseKeys.vk_communities] = self.client.data[DatabaseKeys.vk].get(DatabaseKeys.vk_communities, [])


def setup(client):
    client.add_cog(Database(client))
