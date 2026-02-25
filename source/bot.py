"""
Discord bot implementation with slash commands for Bible verse automation.
"""

import os
import discord
from discord import app_commands
from discord.ext import commands
import pytz
import re
from typing import Optional

from .bible_api import get_bible_versions, get_random_verse
from .storage import (
    save_user_settings,
    get_user_settings,
    has_been_greeted,
    mark_greeted,
)
from .scheduler import setup_user_schedule
from .conversation import ConversationManager


class BibleBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        """Sync commands with Discord."""
        # Global sync (propagates gradually, up to ~1 h)
        await self.tree.sync()
        print("Commands synced globally with Discord")

        # Instant guild sync — set DISCORD_GUILD_ID in .env.local to enable
        guild_id = os.getenv("DISCORD_GUILD_ID")
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Commands synced instantly to guild {guild_id}")

    async def on_interaction(self, interaction: discord.Interaction):
        """Greet new users with a DM when they first interact with the app."""
        user = interaction.user
        if user and not user.bot and not has_been_greeted(str(user.id)):
            mark_greeted(str(user.id))
            try:
                embed = discord.Embed(
                    title="👋 Welcome to Bible Verse Bot!",
                    description=(
                        "Thanks for adding the app! I'll send you a personalised "
                        "Bible verse every day at a time of your choosing.\n\n"
                        "To get started, run the **/setup** command and I'll walk "
                        "you through picking your Bible version, timezone, and "
                        "delivery time."
                    ),
                    color=discord.Color.blurple(),
                )
                embed.set_footer(text="Have a blessed day! 🙏")
                await user.send(embed=embed)
                print(f"Sent welcome DM to new user {user.id}")
            except discord.Forbidden:
                print(f"Could not DM new user {user.id} — DMs may be disabled")
            except Exception as e:
                print(f"Error sending welcome DM to user {user.id}: {e}")

    async def on_ready(self):
        """Called when bot is ready."""
        print(f"Logged in as {self.user} (ID: {self.user.id})")

        # Set bot status
        activity = discord.Activity(
            type=discord.ActivityType.watching, name="📖 Delivering Daily Bible Verses"
        )
        await self.change_presence(activity=activity, status=discord.Status.online)
        print(f"Status updated: {activity.name}")

        # Start scheduler (now that event loop is running)
        from .scheduler import start_scheduler, load_all_schedules
        from .storage import load_users
        import os

        print("Starting scheduler...")
        start_scheduler()

        # Load all user schedules
        print("Loading user schedules...")
        users = load_users()
        load_all_schedules(users, send_daily_verse)

        print(f"Bot is ready! Loaded {len(users)} user schedule(s)")

        # Send startup notification to owner
        owner_id = os.getenv("DISCORD_USER_ID")
        if owner_id:
            try:
                owner = await self.fetch_user(int(owner_id))
                embed = discord.Embed(
                    title="🤖 Bot Online",
                    description="Bible Verse Bot has successfully started!",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="📊 Status",
                    value=f"✅ Connected\n✅ Commands synced\n✅ Scheduler active\n📋 {len(users)} user schedule(s) loaded",
                    inline=False,
                )
                embed.add_field(
                    name="🌐 Server",
                    value="Flask keep-alive running on port 8080",
                    inline=False,
                )
                embed.set_footer(text=f"Logged in as {self.user.name}")

                await owner.send(embed=embed)
                print(f"Sent startup notification to user {owner_id}")
            except Exception as e:
                print(f"Could not send startup notification: {e}")

        print("------")


# Create bot instance
bot = BibleBot()

# Lazily initialised when the first /chat command fires
_conversation_manager: Optional[ConversationManager] = None


def _get_conversation_manager() -> ConversationManager:
    """Return a shared ConversationManager, creating it on first call."""
    global _conversation_manager
    if _conversation_manager is None:
        _conversation_manager = ConversationManager()
    return _conversation_manager


def validate_time_format(time_str: str) -> bool:
    """Validate time is in HH:MM format."""
    pattern = r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    return bool(re.match(pattern, time_str))


def validate_timezone(tz_str: str) -> bool:
    """Validate timezone string."""
    try:
        pytz.timezone(tz_str)
        return True
    except:
        return False


@bot.tree.command(name="list", description="List all available Bible versions")
async def list_versions(interaction: discord.Interaction):
    """Displays all available Bible versions in a formatted embed."""
    await interaction.response.defer()

    try:
        from .bible_api import get_common_english_versions

        versions = get_common_english_versions()

        if not versions:
            embed = discord.Embed(
                title="❌ Error",
                description="Could not fetch Bible versions. Please try again later.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        # Create embed with list
        embed = discord.Embed(
            title="📖 Available Bible Versions",
            description=f"Popular English Bible versions available ({len(versions)} options)",
            color=discord.Color.blue(),
        )

        # Add all common versions
        versions_text = []
        for version in versions:
            vid = version.get("id", "")
            name = version.get("name", "Unknown")
            abbrev = version.get("abbreviation", version.get("abbreviationLocal", ""))
            if abbrev:
                versions_text.append(f"**{abbrev}** - {name}\n`{vid}`")
            else:
                versions_text.append(f"**{name}**\n`{vid}`")

        embed.add_field(
            name="Common English Versions:",
            value="\n\n".join(versions_text) if versions_text else "No versions found",
            inline=False,
        )

        embed.set_footer(text="Use /setup to configure your daily verses")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in list command: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while fetching Bible versions.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed)


@bot.tree.command(
    name="quote", description="Get a random inspirational Bible verse instantly"
)
async def get_quote(interaction: discord.Interaction):
    """Returns an instant random Bible verse."""
    await interaction.response.defer()

    try:
        # Get user's saved Bible version, or default to KJV
        user_settings = get_user_settings(str(interaction.user.id))

        if user_settings and user_settings.get("bible_version"):
            bible_version = user_settings.get("bible_version")
        else:
            # Default to King James Version
            bible_version = "de4e12af7f28f599-01"  # KJV

        # Get random verse
        verse_data = get_random_verse(bible_version)

        if not verse_data:
            embed = discord.Embed(
                title="❌ Error",
                description="Could not fetch verse. Please try again.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        # Create embed with gold border
        embed = discord.Embed(
            title=verse_data.get("text", ""), description="", color=discord.Color.gold()
        )
        embed.add_field(
            name="Reference", value=verse_data.get("reference", "Unknown"), inline=True
        )
        embed.add_field(name="Version", value=f"`{bible_version}`", inline=True)
        embed.set_footer(text="Use /setup to configure daily verses 🙏")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        print(f"Error in quote command: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description="An error occurred while fetching a verse.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed)


@bot.tree.command(
    name="setup", description="Configure your daily Bible verse delivery (interactive)"
)
async def setup_verse(interaction: discord.Interaction):
    """Interactive multi-step setup for daily Bible verses."""
    await interaction.response.defer()

    try:
        from .interactive_ui import (
            SetupState,
            BibleVersionView,
            TimezoneView,
            TimeSelectionView,
            ConfirmationView,
        )
        from .bible_api import get_common_english_versions

        # Initialize setup state
        state = SetupState(interaction.user.id)

        # Step 1: Bible Version Selection (only common English versions)
        versions = get_common_english_versions()
        if not versions:
            embed = discord.Embed(
                title="❌ Error",
                description="Could not fetch Bible versions. Please try again later.",
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed)
            return

        # Callback for version selection
        async def on_version_selected(inter: discord.Interaction, version: dict):
            state.bible_version = version.get("id")
            version_name = version.get("name", "Unknown")

            # Step 2: Timezone Selection
            embed = discord.Embed(
                title="🌍 Step 2: Select Timezone",
                description="Choose your timezone for accurate delivery times",
                color=discord.Color.blue(),
            )
            embed.add_field(
                name="Selected Bible Version:", value=f"✅ {version_name}", inline=False
            )

            tz_view = TimezoneView(on_timezone_selected)
            tz_view.message = await inter.message.edit(embed=embed, view=tz_view)

        # Callback for timezone selection
        async def on_timezone_selected(inter: discord.Interaction, timezone: str):
            state.timezone = timezone

            # Step 3: Time Selection
            time_view = TimeSelectionView(on_time_selected)
            time_view.message = await inter.message.edit(
                embed=time_view.create_embed(), view=time_view
            )

        # Callback for time selection
        async def on_time_selected(inter: discord.Interaction, time_slot: str):
            state.time = time_slot

            # Step 4: Confirmation
            # Get version name for display
            version_obj = next(
                (v for v in versions if v.get("id") == state.bible_version), None
            )
            version_name = (
                version_obj.get("name", "Unknown") if version_obj else "Unknown"
            )

            confirm_view = ConfirmationView(state, version_name, on_confirmation)
            confirm_view.message = await inter.message.edit(
                embed=confirm_view.create_embed(), view=confirm_view
            )

        # Callback for confirmation
        async def on_confirmation(inter: discord.Interaction, confirmed: bool):
            if confirmed:
                # Save settings
                success = save_user_settings(
                    str(state.user_id), state.bible_version, state.time, state.timezone
                )

                if not success:
                    embed = discord.Embed(
                        title="❌ Error",
                        description="Failed to save your settings. Please try again.",
                        color=discord.Color.red(),
                    )
                    await inter.message.edit(embed=embed, view=None)
                    return

                # Set up schedule
                setup_user_schedule(
                    str(state.user_id), state.time, state.timezone, send_daily_verse
                )

                # Success message
                hour, minute = state.time.split(":")
                display_time = f"{int(hour)}:{minute} AM"
                tz_display = state.timezone.split("/")[-1].replace("_", " ")

                embed = discord.Embed(
                    title="✅ Setup Complete!",
                    description="Your daily Bible verse has been configured successfully!",
                    color=discord.Color.green(),
                )
                embed.add_field(
                    name="📖 Bible Version",
                    value=f"`{state.bible_version}`",
                    inline=False,
                )
                embed.add_field(
                    name="⏰ Delivery Time",
                    value=f"{display_time} ({tz_display})",
                    inline=False,
                )
                embed.add_field(
                    name="📬 Delivery Method", value="Direct Message (DM)", inline=False
                )
                embed.set_footer(
                    text="You will receive your first verse at the scheduled time!"
                )

                await inter.message.edit(embed=embed, view=None)

        # Start the flow with version selection
        version_view = BibleVersionView(versions, on_version_selected)
        version_view.message = await interaction.followup.send(
            embed=version_view.create_embed(), view=version_view
        )

    except Exception as e:
        print(f"Error in setup command: {e}")
        import traceback

        traceback.print_exc()
        embed = discord.Embed(
            title="❌ Error",
            description="An unexpected error occurred. Please try again.",
            color=discord.Color.red(),
        )
        try:
            await interaction.followup.send(embed=embed)
        except:
            await interaction.edit_original_response(embed=embed)


async def send_daily_verse(user_id: str):
    """Sends formatted verse via DM."""
    try:
        # Get user settings
        settings = get_user_settings(user_id)
        if not settings:
            print(f"No settings found for user {user_id}")
            return

        bible_version = settings.get("bible_version")

        # Get random verse
        verse_data = get_random_verse(bible_version)
        if not verse_data:
            print(f"Failed to fetch verse for user {user_id}")
            return

        # Get user object
        user = await bot.fetch_user(int(user_id))
        if not user:
            print(f"Could not find user {user_id}")
            return

        # Create embed with gold border
        embed = discord.Embed(
            title=verse_data.get("text", ""), description="", color=discord.Color.gold()
        )
        embed.add_field(
            name="Reference", value=verse_data.get("reference", "Unknown"), inline=True
        )
        embed.add_field(name="Version", value=f"`{bible_version}`", inline=True)
        embed.set_footer(text="Have a blessed day! 🙏")

        # Send DM
        try:
            await user.send(embed=embed)
            print(f"Sent daily verse to user {user_id}")
        except discord.Forbidden:
            print(f"Cannot send DM to user {user_id} - DMs are disabled")
        except Exception as e:
            print(f"Error sending DM to user {user_id}: {e}")

    except Exception as e:
        print(f"Error in send_daily_verse for user {user_id}: {e}")


# ---------------------------------------------------------------------------
# Owner-only sync commands (prefix-based, work instantly in DMs too)
# ---------------------------------------------------------------------------


@bot.command(name="sync", hidden=True)
@commands.is_owner()
async def sync_commands(ctx: commands.Context):
    """
    Force a global slash-command sync.

    Global syncs still propagate over Discord's network (up to ~1 h), but
    re-posting them refreshes Discord's registration. DM the bot ``!sync``
    to trigger this without needing a server.
    """
    await ctx.typing()
    synced = await bot.tree.sync()
    await ctx.send(f"✅ Synced **{len(synced)}** global command(s).")
    print(f"[sync] Owner triggered global sync — {len(synced)} command(s)")


@bot.command(name="syncguild", hidden=True)
@commands.is_owner()
async def sync_guild_commands(ctx: commands.Context):
    """
    Instantly copy and sync all commands to *this* guild.

    Guild-scoped commands appear in Discord within seconds, making this
    the fastest way to test new slash commands in a server you control.
    Only works inside a server (not in DMs).
    """
    if ctx.guild is None:
        await ctx.send("⚠️ Run this inside a server, not a DM.")
        return

    bot.tree.copy_global_to(guild=ctx.guild)
    synced = await bot.tree.sync(guild=ctx.guild)
    await ctx.send(
        f"✅ Synced **{len(synced)}** command(s) to **{ctx.guild.name}** instantly."
    )
    print(
        f"[syncguild] Owner synced {len(synced)} command(s) to guild {ctx.guild.id}"
    )


@sync_commands.error
@sync_guild_commands.error
async def sync_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.NotOwner):
        await ctx.send("🚫 Only the bot owner can use this command.", delete_after=5)


# ---------------------------------------------------------------------------
# Conversation commands
# ---------------------------------------------------------------------------


@bot.tree.command(
    name="chat",
    description="Have a conversation with the Bible assistant powered by Gemini",
)
@app_commands.describe(message="Your message or question for the Bible assistant")
async def chat_command(interaction: discord.Interaction, message: str):
    """Send a message to the Gemini-powered Bible assistant."""
    await interaction.response.defer(thinking=True)

    try:
        manager = _get_conversation_manager()
        reply = await manager.chat(
            user_id=str(interaction.user.id),
            user_message=message,
        )

        # Truncate to Discord's plain-message limit (2000 chars)
        truncated = reply if len(reply) <= 2000 else reply[:1997] + "…"

        await interaction.followup.send(truncated)

    except Exception as e:
        print(f"[chat_command] Error for user {interaction.user.id}: {e}")
        embed = discord.Embed(
            title="\u274c Error",
            description="Something went wrong while processing your message. Please try again.",
            color=discord.Color.red(),
        )
        await interaction.followup.send(embed=embed)


@bot.tree.command(
    name="clearchat",
    description="Reset your conversation history with the Bible assistant",
)
async def clearchat_command(interaction: discord.Interaction):
    """Clear the user's stored conversation history."""
    try:
        manager = _get_conversation_manager()
        manager.reset(user_id=str(interaction.user.id))

        embed = discord.Embed(
            title="\u2705 Conversation Cleared",
            description="Your chat history has been reset. Start fresh with a new question!",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        print(f"[clearchat_command] Error for user {interaction.user.id}: {e}")
        await interaction.response.send_message(
            "\u274c Failed to clear history. Please try again.", ephemeral=True
        )


# ---------------------------------------------------------------------------
# Bot accessor
# ---------------------------------------------------------------------------


def get_bot():
    """Returns the bot instance."""
    return bot
