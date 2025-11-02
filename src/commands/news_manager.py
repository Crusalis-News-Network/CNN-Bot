# news_commands.py

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2025 charis_k
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/gpl-3.0.html>.
from __future__ import annotations
from typing import Dict, Sequence, Optional, Any, List

import discord
from discord import app_commands
import os

from utils.db import *

GUILD_ID = discord.Object(id=int(os.environ["GUILD_ID"]))

NEWS_CHANNEL_ID = int(os.environ["NEWS_CHANNEL_ID"])

ADMIN_ID = [
    s.strip()
    for s in str(os.environ.get("ADMIN_ID", "")).split(",")
    if s.strip()
]


class NewsCommands(app_commands.Group):
    def __init__(self):
        super().__init__(name="news", description="Manage and post news")

    @app_commands.command(name="add", description="Add and post a news item")
    @app_commands.describe(
        title="The title of the news item",
        description="A short description",
        image_url="Image URL to include in the embed",
        credit="Credit for the news item (e.g., source or author)",
        category="Category of this news item (choose from EMC categories)",
        region="The region this news item is about (defaults to 'Global')",
    )
    async def add(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        image_url: str,
        credit: str,
        category: Category  = Category.WORLD,
        region: Region = Region.Global,
    ) -> None:
        reporter = await ReporterSchema.get_or_none(user_id=interaction.user.id)
        if reporter is None:
            await interaction.response.send_message(
                "You are not registered as a reporter.", ephemeral=True
            )
            return
        try:
            _f = int(credit)
        except Exception:
            await interaction.response.send_message("Use a fucking user id")
            return

        news = await NewsSchema.create(
            title=title,
            description=description,
            image_url=image_url,
            credit=credit,
            reporter=str(interaction.user.id),
            editor=reporter,
            region=region,
            category=category.value,
        )
        if news is None:
            await interaction.response.send_message("Failed to create news item.", ephemeral=True)
            return

        embed = news.to_embed()

        main_guild = interaction.client.get_guild(GUILD_ID.id)
        if main_guild is None:
            await interaction.response.send_message("News saved but main guild not found.", ephemeral=True)
            return

        main_channel = main_guild.get_channel(NEWS_CHANNEL_ID)
        if not isinstance(main_channel, discord.TextChannel):
            await interaction.response.send_message("News saved but main news channel is invalid.", ephemeral=True)
            return

        msg = await main_channel.send(embed=embed)
        await msg.publish()

        news.message_id = msg.id
        await news.save()

        reporter.posts += 1
        await reporter.save()


    @app_commands.command(
        name="edit",
        description="Edit an existing news item (and update all previous embeds)."
    )
    @app_commands.describe(
        news_id="The ID of the news item to edit",
        title="(Optional) New title",
        description="(Optional) New description",
        image_url="(Optional) New image URL",
        credit="(Optional) New credit/source",
        category="(Optional) New category",
        region="(Optional) New region",
    )

    async def edit(
        self,
        interaction: discord.Interaction,
        news_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        image_url: Optional[str] = None,
        credit: Optional[str] = None,
        category: Optional[Category] = None,
        region: Optional[Region] = None,
    ) -> None:
        news = await NewsSchema.get_or_none(id=news_id)
        if news is None:
            await interaction.response.send_message(
                "News ID not found.", ephemeral=True
            )
            return

        is_reporter = (int(news.reporter) == interaction.user.id)
        is_admin = (str(interaction.user.id) in ADMIN_ID)
        if not (is_reporter or is_admin):
            await interaction.response.send_message(
                "You are not allowed to edit this item.", ephemeral=True
            )
            return

        updated_fields = []
        if title is not None:
            news.title = title
            updated_fields.append("title")
        if description is not None:
            news.description = description
            updated_fields.append("description")
        if image_url is not None:
            news.image_url = image_url
            updated_fields.append("image_url")
        if credit is not None:
            news.credit = credit
            updated_fields.append("credit")
        if category is not None:
            news.category = category.value
            updated_fields.append("category")
        if region is not None:
            news.region = region
            updated_fields.append("region")


        if not updated_fields:
            await interaction.response.send_message(
                "No changes specified. Provide at least one field to edit.", ephemeral=True
            )
            return

        await news.save(update_fields=updated_fields)

        new_embed = news.to_embed()

        msg: discord.Message = await interaction.guild.get_channel(NEWS_CHANNEL_ID).fetch_message(NewsSchema.message_id)

        await msg.edit(embed=new_embed)

        await interaction.response.send_message("Updated message.")
        return
    @app_commands.command(name="delete", description="Delete a news item by ID")
    @app_commands.describe(news_id="The ID of the news item to delete")
    async def delete(self, interaction: discord.Interaction, news_id: int) -> None:
        news: Optional[NewsSchema] = await NewsSchema.get_or_none(id=news_id)
        if news is None:
            await interaction.response.send_message("Not found.", ephemeral=True)
            return

        is_reporter: bool = (int(news.reporter) == interaction.user.id)
        is_admin: bool = (str(interaction.user.id) in ADMIN_ID)
        if not (is_reporter or is_admin):
            await interaction.response.send_message(
                "You are not allowed to delete this", ephemeral=True
            )
            return

        msg: discord.Message = await interaction.guild.get_channel(NEWS_CHANNEL_ID).fetch_message(NewsSchema.message_id)
        await msg.delete()

        await news.delete()
        await news.reset_sqlite_autoincrement("newsschema")

        await interaction.response.send_message(
            f"🗑Deleted news `{news_id}` from all subscribers.", ephemeral=True
        )

    @app_commands.command(name="lookup", description="Lookup news by filters")
    @app_commands.describe(
        topic="Topic to search for",
        nation="Nation to search for",
        author="Author to search for",
    )
    async def lookup(
        self,
        interaction: discord.Interaction,
        topic: str = "",
        nation: str = "",
        author: str = "",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        results: Sequence[NewsSchema] = await NewsSchema.search_query(
            topic=topic or None,
            nation=nation or None,
            author=author or None,
        )
        if not results:
            await interaction.followup.send("🔍 No matching news.", ephemeral=True)
            return

        for n in results[:5]:
            await interaction.followup.send(embed=n.to_embed(), ephemeral=True)

    @app_commands.command(name="recent", description="Show recent news")
    @app_commands.describe(
        limit="How many items to show (max 10)",
    )
    async def recent(
        self,
        interaction: discord.Interaction,
        limit: int = 5,
    ) -> None:
        limit = min(limit, 10)
        items: Sequence[NewsSchema] = await NewsSchema.get_recent(limit)
        if not items:
            await interaction.response.send_message("No recent news found.", ephemeral=True)
            return

        for n in items:
            await interaction.response.send_message(embed=n.to_embed(), ephemeral=True)


command = NewsCommands()
