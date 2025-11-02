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
import logging

from tortoise import Tortoise
import uvicorn
import importlib
import pkgutil
from discord import app_commands
import dotenv, os, asyncio, threading

from utils.db import ReporterSchema

dotenv.load_dotenv()
from utils.globals import *

DISCORD_TOKEN = os.environ.get("TOKEN")


def load_app_command_modules(tree: app_commands.CommandTree, package: str):
    pkg = importlib.import_module(package)

    for _finder, module_name, _is_pkg in pkgutil.walk_packages(pkg.__path__, prefix=package + "."):
        print(f"Trying module {module_name}")
        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            logger.error(f"Failed to import {module_name}: {e}")
            continue

        cmd = getattr(module, "command", None)
        if cmd is None:
            logger.error(f"No `command` export in {module_name}")
            continue

        if not isinstance(cmd, (app_commands.Command, app_commands.Group)):
            logger.error(f"`command` in {module_name} is not a Command or Group")
            continue

        try:
            tree.add_command(cmd)
            logger.info(f"Registered `{cmd.name}` from {module_name}")
        except Exception as e:
            logger.error(f"Could not register `{cmd.name}` from {module_name}: {e}")


set_up = False

async def setup(set_up: bool):
    if set_up: return
    set_up = True
    reporter_role = None
    guild_id = None

    if len(os.environ.get("REPORTER_ROLE")) == 0:
        raise ValueError("Empty reporter role id")
    else:
        reporter_role = os.environ.get("REPORTER_ROLE")

    if len(os.environ.get("GUILD_ID")) == 0:
        raise ValueError("Empty guild id")
    else:
        guild_id = os.environ.get("GUILD_ID")

    guild = bot.get_guild(guild_id)

    if not guild: return

    role = guild.get_role(reporter_role)
    if not role: return
    members = role.members

    for member in members:
        user_id = member.id
        existing = await ReporterSchema.get_or_none(user_id=user_id)
        if not existing:
            await ReporterSchema.create(user_id=user_id)


def start_api():
    uvicorn.run("utils.api:app", host="0.0.0.0", port=3000)

async def start_db():
    await Tortoise.init(
        db_url="sqlite://db.db",
        modules={"models": ["utils.db"]},

    )
    await Tortoise.generate_schemas()
    logger.error("Schema generated!")

@bot.event
async def on_ready():

    logger.error(f"Logged in as {bot.user} ({bot.user.id})")

    load_app_command_modules(bot.tree, "commands")
    await bot.tree.sync()
    logger.error("Commands synced")
    await setup(set_up)

    

asyncio.run(start_db())
api_thread = threading.Thread(target=start_api, daemon=True)
api_thread.start()
bot.run(DISCORD_TOKEN, log_handler=None)
