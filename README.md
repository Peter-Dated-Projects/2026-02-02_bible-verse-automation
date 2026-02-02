# Bible Verse Discord Bot 📖

Automated Discord bot that sends daily inspirational Bible verses via DM with customizable scheduling and timezone support.

## Features

- 🕐 **Customizable Scheduling** - Set your preferred delivery time in any timezone
- 📚 **40 Curated Verses** - Hand-picked inspirational passages from the Bible
- 🌍 **Timezone Support** - Full timezone awareness with EST as default
- 💬 **Discord Slash Commands** - Easy `/list` and `/setup` commands
- 🔄 **Persistent Storage** - Settings saved across bot restarts
- 🚀 **Repl.it Ready** - Flask keep-alive server for free hosting

## Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment** (`.env.local`):
   ```env
   DISCORD_API_KEY=your_discord_token_here
   API_BIBLE_KEY=your_api_bible_key_here
   API_BIBLE_ENDPOINT=https://api.bible
   ```

3. **Run the Bot**:
   ```bash
   python main.py
   ```

## Usage

### List Available Bible Versions
```
/list
```

### Setup Daily Verses
```
/setup version:de4e12af7f28f599-02 time:08:00
```

### Setup with Custom Timezone
```
/setup version:de4e12af7f28f599-02 time:14:30 timezone:America/Los_Angeles
```

## Deployment to Repl.it

1. Upload project files to Repl.it
2. Add environment variables to Secrets
3. Run the bot
4. Use [UptimeRobot](https://uptimerobot.com/) to ping your Repl URL every 5 minutes to keep it alive

The Flask server runs on port 8080 and responds to GET requests at `/` for keep-alive monitoring.

## Project Structure

```
├── main.py                 # Application entry point
├── requirements.txt        # Python dependencies
├── assets/
│   └── persist.json       # User preferences
└── source/
    ├── bot.py             # Discord bot & commands
    ├── bible_api.py       # API.Bible client
    ├── storage.py         # JSON persistence
    ├── scheduler.py       # Job scheduling
    └── server.py          # Flask keep-alive
```

## Curated Verses

Includes popular inspirational passages:
- John 3:16 - "For God so loved the world..."
- Psalm 23:1-6 - "The Lord is my shepherd..."
- Philippians 4:13 - "I can do all things through Christ..."
- And 37 more!

## License

Built for personal use with API.Bible and Discord API.