"""
Bible Verse Discord Bot - Main Application Entry Point
Sends automated daily Bible verses via Discord DMs
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

from source.server import start_server
from source.bot import get_bot
from source import storage
from source.scheduler import load_all_schedules, start_scheduler

def main():
    """Main application entry point."""
    print("=" * 50)
    print("Bible Verse Discord Bot Starting...")
    print("=" * 50)

    # Load (or create) persist.json into memory first
    storage.init()
    
    # Verify environment variables
    discord_token = os.getenv('DISCORD_API_KEY')
    api_bible_key = os.getenv('API_BIBLE_KEY')
    
    if not discord_token:
        print("ERROR: DISCORD_API_KEY not found in environment variables")
        return
    
    if not api_bible_key:
        print("ERROR: API_BIBLE_KEY not found in environment variables")
        return
    
    # Start Flask keep-alive server
    print("\n[1/2] Starting Flask keep-alive server...")
    start_server()
    
    # Get bot instance (scheduler will start in on_ready)
    bot = get_bot()
    
    print("[2/2] Starting Discord bot...")
    print("=" * 50 + "\n")
    
    # Run bot (scheduler and schedules load in on_ready)
    bot.run(discord_token)

if __name__ == "__main__":
    main()
