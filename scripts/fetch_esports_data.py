import os
import time
import requests
import pandas as pd

# Create data directory if it doesn't exist
os.makedirs('data', exist_ok=True)

def fetch_historical_pro_matches(target_match_count=500):
    """
    Paginates backward through OpenDota to get historical matches.
    Change target_match_count to a higher number (e.g., 10000) to get years of data.
    """
    print(f"Fetching {target_match_count} historical pro matches...")
    all_matches = []
    lowest_match_id = None
    
    while len(all_matches) < target_match_count:
        url = "https://api.opendota.com/api/proMatches"
        if lowest_match_id:
            url += f"?less_than_match_id={lowest_match_id}"
            
        response = requests.get(url)
        
        if response.status_code != 200:
            print(f"Error fetching data. Status code: {response.status_code}")
            break
            
        batch = response.json()
        if not batch:
            break # No more matches available
            
        all_matches.extend(batch)
        
        # Get the lowest match_id in this batch to use for the next API call
        lowest_match_id = min([match['match_id'] for match in batch])
        print(f"Fetched {len(all_matches)} matches so far. Paginating past match ID: {lowest_match_id}...")
        
        # Respect OpenDota's rate limit of 60 requests per minute
        time.sleep(1.1) 
        
    # Trim to exactly the amount requested and save
    all_matches = all_matches[:target_match_count]
    df = pd.DataFrame(all_matches)
    df.to_csv('data/historical_pro_matches.csv', index=False)
    print(f"✅ Saved {len(df)} historical matches to data/historical_pro_matches.csv")


def fetch_match_roster(match_id):
    """
    Fetches the detailed roster, player names, and heroes picked for a specific match.
    """
    print(f"\nFetching detailed roster data for Match ID: {match_id}...")
    url = f"https://api.opendota.com/api/matches/{match_id}"
    response = requests.get(url)
    
    if response.status_code == 200:
        match_data = response.json()
        
        print(f"\n--- Match {match_id} Roster ---")
        # The 'players' array contains data for all 10 people in the game
        for player in match_data.get('players', []):
            side = "Radiant" if player['isRadiant'] else "Dire"
            player_name = player.get('name') or player.get('personaname') or "Unknown Player"
            hero_id = player.get('hero_id')
            
            print(f"{side} Team | Player: {player_name} | Hero ID Picked: {hero_id}")
    else:
        print(f"Failed to fetch match details. Status code: {response.status_code}")


if __name__ == "__main__":
    # 1. Run the loop to get 500 historical matches (increase this number for 3 years of data)
    fetch_historical_pro_matches(target_match_count=500)
    
    # 2. Example: Fetch the exact hero roster for one of the games from your screenshot
    fetch_match_roster(8885195986)