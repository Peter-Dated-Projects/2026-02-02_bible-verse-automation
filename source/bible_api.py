"""
API client for interacting with API.Bible.
"""
import os
import requests
import random
from typing import Dict, List, Optional

API_KEY = os.getenv('API_BIBLE_KEY')
API_ENDPOINT = os.getenv('API_BIBLE_ENDPOINT', 'https://api.bible')

# Curated list of popular inspirational Bible verses
# Format: "BOOK.CHAPTER.VERSE" or "BOOK.CHAPTER.VERSE-VERSE" for ranges
INSPIRATIONAL_VERSES = [
    "JHN.3.16",  # John 3:16 - For God so loved the world
    "PHP.4.13",  # Philippians 4:13 - I can do all things through Christ
    "PSA.23.1-6",  # Psalm 23 - The Lord is my shepherd
    "ROM.8.28",  # Romans 8:28 - All things work together for good
    "JER.29.11",  # Jeremiah 29:11 - Plans to prosper you
    "PRO.3.5-6",  # Proverbs 3:5-6 - Trust in the Lord
    "ISA.41.10",  # Isaiah 41:10 - Fear not, I am with you
    "MAT.11.28",  # Matthew 11:28 - Come to me, all who are weary
    "2CO.5.17",  # 2 Corinthians 5:17 - New creation
    "GAL.5.22-23",  # Galatians 5:22-23 - Fruit of the Spirit
    "ROM.12.2",  # Romans 12:2 - Be transformed
    "JOS.1.9",  # Joshua 1:9 - Be strong and courageous
    "PSA.46.1",  # Psalm 46:1 - God is our refuge
    "ISA.40.31",  # Isaiah 40:31 - Those who hope in the Lord
    "MAT.6.33",  # Matthew 6:33 - Seek first his kingdom
    "PHP.4.6-7",  # Philippians 4:6-7 - Do not be anxious
    "1CO.13.4-7",  # 1 Corinthians 13:4-7 - Love is patient
    "ROM.5.8",  # Romans 5:8 - God demonstrates his love
    "EPH.2.8-9",  # Ephesians 2:8-9 - Saved by grace
    "2TI.1.7",  # 2 Timothy 1:7 - Spirit of power and love
    "PSA.119.105",  # Psalm 119:105 - Lamp unto my feet
    "HEB.11.1",  # Hebrews 11:1 - Faith is confidence
    "JAS.1.2-3",  # James 1:2-3 - Consider it pure joy
    "1JN.4.19",  # 1 John 4:19 - We love because he first loved us
    "ROM.8.38-39",  # Romans 8:38-39 - Nothing can separate us
    "PSA.27.1",  # Psalm 27:1 - The Lord is my light
    "MAT.5.14-16",  # Matthew 5:14-16 - You are the light of the world
    "JHN.14.6",  # John 14:6 - I am the way, the truth, and the life
    "ACT.1.8",  # Acts 1:8 - You will receive power
    "COL.3.23",  # Colossians 3:23 - Work heartily
    "HEB.12.1-2",  # Hebrews 12:1-2 - Run with perseverance
    "PSA.37.4",  # Psalm 37:4 - Delight yourself in the Lord
    "MAT.28.19-20",  # Matthew 28:19-20 - Great Commission
    "REV.21.4",  # Revelation 21:4 - No more tears
    "MIC.6.8",  # Micah 6:8 - Act justly, love mercy
    "1PE.5.7",  # 1 Peter 5:7 - Cast all your anxiety
    "PSA.91.1-2",  # Psalm 91:1-2 - Dwelling in the shelter
    "JHN.15.5",  # John 15:5 - I am the vine
    "EPH.6.10-11",  # Ephesians 6:10-11 - Armor of God
    "1CO.10.13",  # 1 Corinthians 10:13 - God is faithful
]

# Cache for Bible versions
_bible_versions_cache = None

# Common English Bible versions to offer
COMMON_ENGLISH_VERSIONS = {
    'KJV': 'de4e12af7f28f599-02',   # King James Version
    'ASV': 'de4e12af7f28f599-01',   # American Standard Version (fallback if others not available)
    'WEB': '06125adad2d5898a-01',   # World English Bible (fallback)
}

def get_bible_versions() -> List[Dict]:
    """Fetches and caches available Bible translations."""
    global _bible_versions_cache
    
    if _bible_versions_cache is not None:
        return _bible_versions_cache
    
    try:
        headers = {'api-key': API_KEY}
        response = requests.get(f'{API_ENDPOINT}/v1/bibles', headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        _bible_versions_cache = data.get('data', [])
        return _bible_versions_cache
    except Exception as e:
        print(f"Error fetching Bible versions: {e}")
        return []

def get_common_english_versions() -> List[Dict]:
    """Returns the most common/popular English Bible versions available in API.Bible."""
    all_versions = get_bible_versions()
    
    # Filter to only English versions
    english_versions = [v for v in all_versions if v.get('language', {}).get('id') == 'eng']
    
    # Prioritize by these keywords in order of preference
    priority_keywords = [
        'King James',      # KJV and variants
        'World English',   # WEB - modern, free translation
        'Bible in Basic English',  # BBE - simple English
        'Webster',         # Webster's Bible
        'American Standard', # ASV
        'Darby',          # Darby Translation
    ]
    
    prioritized = []
    seen_ids = set()
    
    # First pass: get versions matching priority keywords
    for keyword in priority_keywords:
        for version in english_versions:
            vid = version.get('id')
            name = version.get('name', '').lower()
            
            if vid not in seen_ids and keyword.lower() in name:
                prioritized.append(version)
                seen_ids.add(vid)
                if len(prioritized) >= 6:  # Get up to 6 options
                    break
        if len(prioritized) >= 6:
            break
    
    # If we don't have enough, add remaining English versions
    if len(prioritized) < 4:
        for version in english_versions:
            vid = version.get('id')
            if vid not in seen_ids:
                prioritized.append(version)
                seen_ids.add(vid)
                if len(prioritized) >= 6:
                    break
    
    return prioritized[:6]  # Return up to 6 versions

def get_random_verse(bible_version: str) -> Optional[Dict]:
    """Selects verse from curated list and retrieves from API."""
    try:
        # Select random verse from curated list
        verse_id = random.choice(INSPIRATIONAL_VERSES)
        
        # Fetch verse from API
        headers = {'api-key': API_KEY}
        url = f'{API_ENDPOINT}/v1/bibles/{bible_version}/verses/{verse_id}'
        response = requests.get(url, headers=headers, timeout=10, params={'content-type': 'text'})
        response.raise_for_status()
        
        data = response.json()
        verse_data = data.get('data', {})
        
        return {
            'text': verse_data.get('content', ''),
            'reference': verse_data.get('reference', ''),
            'verse_id': verse_id
        }
    except Exception as e:
        print(f"Error fetching random verse: {e}")
        return None

def format_verse_reference(reference: str) -> str:
    """Formats verse references for display."""
    return reference
