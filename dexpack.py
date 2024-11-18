import re
from base64 import b64decode
from contextlib import suppress
from dataclasses import dataclass
from dataclasses import field as datafield
from datetime import datetime
from logging import getLogger
from os import mkdir, path
from pathlib import Path
from shutil import rmtree
from time import time

from discord import Color, Embed
from discord.ext import commands
from requests import codes as request_codes
from requests import get as request_get
from yaml import dump as yaml_dump
from yaml import safe_load as yaml_load

dir_type = "ballsdex" if path.isdir("ballsdex") else "carfigures"

if dir_type == "ballsdex":
    from ballsdex.settings import settings
else:
    from carfigures.settings import settings


log = getLogger(f"{dir_type}.core.dexpack")

__version__ = "0.1"

verified = False
verified_packages = {}


class Package:
    def __init__(self, yml):
        self.__dict__.update(yml)


def verify_packages():
    request = request_get(
        "https://api.github.com/repos/Dotsian/DexPack/contents/verified.txt"
    )

    if r.status_code != request_codes.ok:
        log.warning("Failed to verify packages.")
        return

    for line in verified.split("\n"):
        if line.startswith("#") or line == "":
            continue
        
        split = line.split(" : ")
        verified_packages[split[0]] = f"https://github.com/{split[1]}"

def fetch_package(name):
    """
    Returns package information based on the name passed.

    Parameters
    ----------
    name: str
        The name of the package you want to return.
    """

    package_path = f"{dir_type}/data/{name}.yml"

    if not path.isfile(package_path):
        return None

    return Package(yaml_load(Path(f"{dir_type}/data/{name}.yml").read_text()))


class DexPack(commands.Cog):
    """
    DexPack commands
    """

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def check_version():
        if not script_settings.outdated_warnings:
            return None

        request = request_get(
            "https://api.github.com/repos/Dotsian/DexPack/contents/pyproject.toml"
        )

        if r.status_code != request_codes.ok:
            return

        content = b64decode(r.json()["content"]).decode("UTF-8").rstrip()
        new_version = content.split('version = "')[1].split('"')[0]

        if new_version != __version__:
            return (
                f"DexPack v{__version__} is outdated. "
                f"Please update to v{new_version} "
                f"using `{settings.prefix}update-dp`."
            )

        return None

    @commands.command()
    @commands.is_owner()
    async def view(self, ctx: commands.Context, package: str = "DexPack"):
        """
        Displays information about a package.

        Parameters
        ----------
        package: str
            The package you want to view. Default is DexPack.
        """

        embed = Embed(
            title="DexPack - ALPHA",
            description=(
                "DexPack, derived from DexScript, is a set of commands created by DotZZ "
                "that allows you to easily install packages for your Ballsdex bot.\n\n"
                "For a guide on how to use DexPack, use the `/help` command."
            ),
            color=Color.from_str("#03BAFC"),
        )

        version_check = "OUTDATED" if self.check_version() is not None else "LATEST"

        embed.set_thumbnail(url="https://i.imgur.com/uKfx0qO.png")
        embed.set_footer(text=f"DexPack {__version__} ({version_check})")

        if package != "DexPack":
            info = fetch_package(package)

            if info is None:
                await ctx.send("The package you entered does not exist.")
                return

            color = info.color if hasattr(info, "color") else "03BAFC"

            embed.title = package
            embed.description = info.description
            embed.color = Color.from_str(f"#{color}")

            if hasattr(info, "logo"):
                embed.set_thumbnail(url=info.logo)

            embed.set_footer(text=f"{package} {info.version}")

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def uninstall(self, ctx: commands.Context, package: str):
        """
        Uninstalls a package.

        Parameters
        ----------
        package: str
            The package you want to uninstall.
        """

        embed = Embed(
            title=f"Removed {package.title()}",
            description=f"The {package.title()} package has been removed from your bot.",
            color=Color.red(),
            timestamp=datetime.now(),
        )

        rmtree(f"{dir_type}/packages/{package}")

        await self.bot.unload_extension(f"{dir_type}/packages/{package}")
        await self.bot.tree.sync()

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def verify(self, ctx: commands.Context):
        """
        Verifies you want to install a package.
        """

        global verified

        verified = True

        await ctx.message.add_reaction("✅")

    @commands.command()
    @commands.is_owner()
    async def install(self, ctx: commands.Context, package: str):
        """
        Installs a package to your Discord bot.

        Parameters
        ----------
        package: str
            The package you want to install.
            If the package isn't verified, it must be a GitHub link 
            with a `package.yml` file.
        """

        global verified

        is_verified = False

        if package.startswith("https://github.com/"):
            package_info = package.replace("https://github.com/", "").split("/")
        else:
            found_package = [x for x in verified_packages.items() if x[0] == package]
            exists = True

            try:
                found_package[0]
            except IndexError:
                exists = False

            if not exists:
                await ctx.send("The link you sent is not a valid GitHub link.")
                return

            is_verified = True
            package_info = list(found_package)
        
        original_name = package_info[1]

        if script_settings.safe_mode and not verified and not is_verified:
            await ctx.send(
                "**CAUTION:** this package has not been verified. "
                "Are you sure you want to install this package?\n"
                "All packages you install can modify your Discord bot.\n"
                f"Run the `{settings.prefix}verify` comamnd to verify "
                "you want to install this package."
            )

            return

        if is_verified:
            package_info[1] = verified_packages[original_name]

        if verified:
            verified = False

        t1 = time()

        link = f"https://api.github.com/repos/{package_info[0]}/{package_info[1]}/contents/"

        request = request_get(f"{link}package.yml")

        if request.status_code == request_codes.ok:
            content = b64decode(request.json()["content"])

            with open(f"{dir_type}/data/{package_info[1]}.yml", "w") as package_file:
                package_file.write(content.decode("UTF-8"))

            yaml_content = yaml_load(content)
            package_info = Package(yaml_content)

            if dir_type not in package_info.supported:
                await ctx.send(f"This package does not support {dir_type}.")
                return

            color = package_info.color if hasattr(package_info, "color") else "03BAFC"

            embed = Embed(
                title=f"Installing {original_name}",
                description=(
                    f"{original_name} is being installed on your bot.\n"
                    "Please do not turn off your bot."
                ),
                color=Color.from_str(f"#{color}"),
                timestamp=datetime.now(),
            )

            if hasattr(package_info, "logo"):
                embed.set_thumbnail(url=package_info.logo)

            original_message = await ctx.send(embed=embed)
        else:
            await ctx.send(
                f"Failed to install {package_info[1]}.\n"
                f"Report this issue to `{package_info[0]}`.\n"
                f"```ERROR CODE: {request.status_code}```"
            )
            return

        with suppress(FileExistsError):
            mkdir(f"{dir_type}/packages/{package_info.name}")

        for file in package_info.files:
            file_path = f"{package_info.name}/{file}"
            request_content = request_get(f"{link}{file_path}")

            if request_content.status_code == request_codes.ok:
                content = b64decode(request_content.json()["content"])

                with open(f"{dir_type}/packages/{file_path}", "w") as opened_file:
                    opened_file.write(content.decode("UTF-8"))
            else:
                await ctx.send(
                    f"Failed to install the `{file}` file.\n"
                    f"Report this issue to `{package_info.author}`.\n"
                    f"```ERROR CODE: {request_content.status_code}```"
                )

        try:
            await self.bot.load_extension(f"{dir_type}.packages.{package_info.name}")
        except commands.ExtensionAlreadyLoaded:
            await self.bot.reload_extension(f"{dir_type}.packages.{package_info.name}")

        t2 = time()

        embed.title = f"{original_name} Installed"

        embed.description = (
            f"{original_name} has been installed to your bot\n{package_info.description}"
        )

        embed.set_footer(text=f"{original_name} took {round((t2 - t1) * 1000)}ms to install")

        await original_message.edit(embed=embed)

    @commands.command(name="update-dp")
    @commands.is_owner()
    async def update_dp(self, ctx: commands.Context):
        """
        Updates DexPack to the latest version.
        """

        request = request_get(
            "https://api.github.com/repos/Dotsian/DexPack/contents/installer.py"
        )

        if r.status_code == request_codes.ok:
            content = b64decode(r.json()["content"])
            await ctx.invoke(self.bot.get_command("eval"), body=content.decode("UTF-8"))
        else:
            await ctx.send(
                "Failed to update DexPack.\n"
                "Report this issue to `dot_zz` on Discord.\n"
                f"```ERROR CODE: {request.status_code}```"
            )

    @commands.command(name="reload-dp")
    @commands.is_owner()
    async def reload_dp(self, ctx: commands.Context):
        """
        Reloads DexPack.
        """

        await self.bot.reload_extension(f"{dir_type}.core.dexpack")
        await ctx.send("Reloaded DexPack")

verify_packages()

async def setup(bot):
    await bot.add_cog(DexPack(bot))
