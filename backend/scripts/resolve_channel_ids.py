"""Resolve YouTube channel handles (@...) to channel IDs using the YouTube Data API."""

import asyncio
import json
from pathlib import Path

import httpx

from app.config import settings

SEED_FILE = Path(__file__).parent.parent / "data" / "seed_channels.json"

HANDLES = [
    ("Lofi Girl", "@LofiGirl"),
    ("Fantastic Music", "@fantasticmusicyoutube"),
    ("Stay See", "@stayseemusic"),
    ("LTB Music", "@LTBMusic"),
    ("Chillhop Music", "@ChillhopMusic"),
    ("Settle", "@settlefm"),
    ("EYM", "@EYMmusic"),
    ("Starburst", "@starburstmusic"),
    ("College Music", "@CollegeMusic"),
    ("Nice Guys", "@NiceGuys"),
    ("Cafe Music BGM Channel", "@cafemusicbgmchannel"),
    ("The Jazz Hop Café", "@jazzhopcafe"),
    ("Steezyasfuck", "@steezyasfvck"),
    ("Fluidified", "@Fluidified"),
    ("Gravity Music", "@gravitymusic1324"),
    ("Fasol Prod", "@FasolProd"),
    ("chilli music", "@chillimusicrecords"),
    ("A Lofi Soul", "@A-Lofi-Soul"),
    ("Soulfi Room", "@SoulFiRoomOfficial"),
    ("Afro Lofi", "@afrolofi"),
    ("Asthenic", "@Asthenic"),
    ("Anjunadeep", "@anjunadeep"),
    ("MrSuicideSheep", "@MrSuicideSheep"),
    ("Dreamy", "@dreamylofi"),
    ("Sound Territory", "@Sound_Territory"),
    ("ravenwings", "@tried_b4"),
    ("devs FM", "@devsfm"),
    ("Music Brokers", "@musicbrokers"),
    ("TheSoundYouNeed", "@thesoundyouneed1"),
    ("Elegance", "@0xtabs"),
    ("Alejandro Torres", "@theoneplanetnomad"),
    ("NEON NOIRE", "@neonoire"),
    ("Seven Beats Music", "@SevenBeatsmusic"),
    ("Spaceambient", "@SpaceAmbient"),
    ("Lepreezy", "@Lepreezy"),
    ("Coffee shop vibes", "@CoffeeShopVibes"),
    ("relaxdaily", "@relaxdaily"),
    ("Chill Music Lab", "@MusicLabChill"),
    ("Justin Johnson", "@justinjohnsonlive"),
    ("Juan Manuel Rivas", "@JuanManuelRivasMusic"),
    ("Gentle Lo-Fi Days", "@gentlelofidays"),
    ("REMEMBERED", "@REMEMBERED216"),
    ("Retroera", "@Retroeramelody"),
]


async def resolve_handles() -> None:
    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        print("Error: YOUTUBE_API_KEY not set in .env")
        return

    channels: list[dict[str, str]] = []
    failed: list[str] = []

    async with httpx.AsyncClient(timeout=30) as client:
        for name, handle in HANDLES:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={
                    "part": "id",
                    "forHandle": handle.lstrip("@"),
                    "key": api_key,
                },
            )
            data = response.json()
            items = data.get("items", [])

            if items:
                channel_id = items[0]["id"]
                channels.append({
                    "channel_id": channel_id,
                    "channel_name": name,
                })
                print(f"  ✓ {name}: {channel_id}")
            else:
                failed.append(f"{name} ({handle})")
                print(f"  ✗ {name} ({handle}): not found")

    # Write to seed_channels.json
    with open(SEED_FILE, "w") as f:
        json.dump(channels, f, indent=2)

    print(f"\nDone: {len(channels)} resolved, {len(failed)} failed")
    if failed:
        print("Failed:")
        for f_name in failed:
            print(f"  - {f_name}")
    print(f"\nQuota used: {len(HANDLES)} units")


if __name__ == "__main__":
    asyncio.run(resolve_handles())
