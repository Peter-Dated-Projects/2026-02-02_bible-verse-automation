"""
Interactive Discord UI components for multi-step setup flow.
"""
import discord
from discord.ui import Button, View, Select
from typing import Optional, Callable
import math

class SetupState:
    """Stores state during multi-step setup process."""
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.bible_version: Optional[str] = None
        self.timezone: Optional[str] = None
        self.time: Optional[str] = None

# Common timezones for selection
COMMON_TIMEZONES = [
    "America/New_York",      # EST
    "America/Chicago",        # CST
    "America/Denver",         # MST
    "America/Los_Angeles",    # PST
    "America/Phoenix",        # Arizona
    "America/Anchorage",      # Alaska
    "Pacific/Honolulu",       # Hawaii
    "Europe/London",          # UK
    "Europe/Paris",           # Central Europe
    "Asia/Tokyo",             # Japan
]

# Time slots (6:00 AM to 11:00 AM in 30-minute increments)
TIME_SLOTS = [
    "06:00", "06:30", "07:00", "07:30", "08:00", "08:30",
    "09:00", "09:30", "10:00", "10:30", "11:00"
]

class PaginatedView(View):
    """Base class for paginated selection views."""
    
    def __init__(self, items: list, items_per_page: int = 5, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.items = items
        self.items_per_page = items_per_page
        self.current_page = 0
        self.total_pages = math.ceil(len(items) / items_per_page)
        self.selected_value = None
        self.message = None
        
    def get_page_items(self):
        """Get items for current page."""
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        return self.items[start:end]
    
    async def on_timeout(self):
        """Disable all buttons on timeout."""
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

class BibleVersionView(PaginatedView):
    """Paginated view for selecting Bible version."""
    
    def __init__(self, versions: list, callback: Callable, timeout: float = 180):
        super().__init__(versions, items_per_page=6, timeout=timeout)
        self.callback = callback
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page."""
        self.clear_items()
        
        # Add selection buttons for current page items
        page_items = self.get_page_items()
        for idx, version in enumerate(page_items):
            button = Button(
                label=f"{idx + 1}. {version.get('name', 'Unknown')[:40]}",
                style=discord.ButtonStyle.primary,
                custom_id=f"version_{idx}"
            )
            button.callback = self.create_select_callback(version)
            self.add_item(button)
        
        # Add navigation buttons
        prev_button = Button(
            label="◀ Previous",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0)
        )
        prev_button.callback = self.previous_page
        self.add_item(prev_button)
        
        # Page indicator
        page_info = Button(
            label=f"Page {self.current_page + 1}/{self.total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True
        )
        self.add_item(page_info)
        
        next_button = Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.total_pages - 1)
        )
        next_button.callback = self.next_page
        self.add_item(next_button)
        
        # Cancel button
        cancel_button = Button(
            label="✖ Cancel",
            style=discord.ButtonStyle.danger
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    def create_select_callback(self, version):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.selected_value = version.get('id')
            self.stop()
            await self.callback(interaction, version)
        return callback
    
    async def previous_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.message.edit(embed=self.create_embed(), view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.message.edit(embed=self.create_embed(), view=self)
    
    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="Setup process has been cancelled.",
            color=discord.Color.red()
        )
        await interaction.message.edit(embed=embed, view=None)
    
    def create_embed(self):
        """Create embed showing current page of versions."""
        embed = discord.Embed(
            title="📖 Step 1: Select Bible Version",
            description="Choose a Bible version for your daily verses",
            color=discord.Color.blue()
        )
        
        page_items = self.get_page_items()
        versions_text = []
        for idx, version in enumerate(page_items):
            vid = version.get('id', '')
            name = version.get('name', 'Unknown')
            lang = version.get('language', {}).get('name', 'Unknown')
            versions_text.append(f"**{idx + 1}.** {name}\n`{vid}` • {lang}")
        
        embed.add_field(
            name="Available Versions:",
            value="\n\n".join(versions_text),
            inline=False
        )
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages}")
        
        return embed

class TimezoneView(View):
    """View for selecting timezone."""
    
    def __init__(self, callback: Callable, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.callback = callback
        self.selected_value = None
        self.message = None
        self.setup_buttons()
    
    def setup_buttons(self):
        """Setup timezone selection buttons."""
        # Split timezones into rows of 2
        for i in range(0, len(COMMON_TIMEZONES), 2):
            for tz in COMMON_TIMEZONES[i:i+2]:
                # Format timezone name nicely
                display_name = tz.split('/')[-1].replace('_', ' ')
                if '/' in tz:
                    region = tz.split('/')[0]
                    display_name = f"{display_name} ({region})"
                
                button = Button(
                    label=display_name,
                    style=discord.ButtonStyle.primary,
                    custom_id=f"tz_{tz}"
                )
                button.callback = self.create_select_callback(tz)
                self.add_item(button)
        
        # Cancel button
        cancel_button = Button(
            label="✖ Cancel",
            style=discord.ButtonStyle.danger
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    def create_select_callback(self, timezone):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.selected_value = timezone
            self.stop()
            await self.callback(interaction, timezone)
        return callback
    
    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="Setup process has been cancelled.",
            color=discord.Color.red()
        )
        await interaction.message.edit(embed=embed, view=None)
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

class TimeSelectionView(PaginatedView):
    """View for selecting time slot."""
    
    def __init__(self, callback: Callable, timeout: float = 180):
        super().__init__(TIME_SLOTS, items_per_page=5, timeout=timeout)
        self.callback = callback
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page."""
        self.clear_items()
        
        # Add selection buttons for current page items
        page_items = self.get_page_items()
        for idx, time_slot in enumerate(page_items):
            # Format time nicely (e.g., 06:00 -> 6:00 AM)
            hour, minute = time_slot.split(':')
            display_time = f"{int(hour)}:{minute} AM"
            
            button = Button(
                label=f"{idx + 1}. {display_time}",
                style=discord.ButtonStyle.primary,
                custom_id=f"time_{idx}"
            )
            button.callback = self.create_select_callback(time_slot)
            self.add_item(button)
        
        # Add navigation buttons
        prev_button = Button(
            label="◀ Previous",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0)
        )
        prev_button.callback = self.previous_page
        self.add_item(prev_button)
        
        next_button = Button(
            label="Next ▶",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.total_pages - 1)
        )
        next_button.callback = self.next_page
        self.add_item(next_button)
        
        # Cancel button
        cancel_button = Button(
            label="✖ Cancel",
            style=discord.ButtonStyle.danger
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    def create_select_callback(self, time_slot):
        async def callback(interaction: discord.Interaction):
            await interaction.response.defer()
            self.selected_value = time_slot
            self.stop()
            await self.callback(interaction, time_slot)
        return callback
    
    async def previous_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.message.edit(embed=self.create_embed(), view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.message.edit(embed=self.create_embed(), view=self)
    
    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.stop()
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="Setup process has been cancelled.",
            color=discord.Color.red()
        )
        await interaction.message.edit(embed=embed, view=None)
    
    def create_embed(self):
        """Create embed showing current page of time slots."""
        embed = discord.Embed(
            title="⏰ Step 3: Select Time",
            description="Choose when you'd like to receive your daily verse",
            color=discord.Color.blue()
        )
        
        page_items = self.get_page_items()
        times_text = []
        for idx, time_slot in enumerate(page_items):
            hour, minute = time_slot.split(':')
            display_time = f"{int(hour)}:{minute} AM"
            times_text.append(f"**{idx + 1}.** {display_time}")
        
        embed.add_field(
            name="Available Times:",
            value="\n".join(times_text),
            inline=False
        )
        embed.set_footer(text=f"Page {self.current_page + 1} of {self.total_pages}")
        
        return embed

class ConfirmationView(View):
    """View for final confirmation."""
    
    def __init__(self, state: SetupState, version_name: str, callback: Callable, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.state = state
        self.version_name = version_name
        self.callback = callback
        self.confirmed = False
        self.message = None
        self.setup_buttons()
    
    def setup_buttons(self):
        """Setup confirmation buttons."""
        confirm_button = Button(
            label="✅ Confirm Setup",
            style=discord.ButtonStyle.success
        )
        confirm_button.callback = self.confirm
        self.add_item(confirm_button)
        
        cancel_button = Button(
            label="❌ Cancel",
            style=discord.ButtonStyle.danger
        )
        cancel_button.callback = self.cancel
        self.add_item(cancel_button)
    
    async def confirm(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.confirmed = True
        self.stop()
        await self.callback(interaction, True)
    
    async def cancel(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.confirmed = False
        self.stop()
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="Setup process has been cancelled. No changes were made.",
            color=discord.Color.red()
        )
        await interaction.message.edit(embed=embed, view=None)
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)
    
    def create_embed(self):
        """Create confirmation embed."""
        # Format time display
        hour, minute = self.state.time.split(':')
        display_time = f"{int(hour)}:{minute} AM"
        
        # Format timezone display
        tz_display = self.state.timezone.split('/')[-1].replace('_', ' ')
        
        embed = discord.Embed(
            title="✅ Confirm Your Settings",
            description="Please review your daily verse settings:",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📖 Bible Version",
            value=f"{self.version_name}\n`{self.state.bible_version}`",
            inline=False
        )
        embed.add_field(
            name="🌍 Timezone",
            value=tz_display,
            inline=True
        )
        embed.add_field(
            name="⏰ Time",
            value=display_time,
            inline=True
        )
        embed.set_footer(text="Click Confirm to save or Cancel to abort")
        
        return embed
