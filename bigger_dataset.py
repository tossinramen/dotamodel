import os
import time
import requests
import pandas as pd


os.makedirs('data', exist_ok=True)

def fetch_test_dataset(target_match_count=10):
    print(f"Starting test extraction for {target_match_count} matches...")
    csv_file = 'data/test_pro_dataset.csv'
    all_detailed_matches = []
    
    
    print("\n[Phase 1] Collecting Match IDs...")
    url = "https://api.opendota.com/api/proMatches"
    res = requests.get(url)
    
    if res.status_code != 200:
        print(f"Failed to get match IDs. API status code: {res.status_code}")
        return
        
    batch = res.json()
    
    match_ids_to_fetch = [m['match_id'] for m in batch[:target_match_count]]
    print(f"Successfully collected {len(match_ids_to_fetch)} test Match IDs.")

    
    print(f"\n[Phase 2] Fetching Detailed Draft Data for the {len(match_ids_to_fetch)} matches...")
    for i, match_id in enumerate(match_ids_to_fetch):
        url = f"https://api.opendota.com/api/matches/{match_id}"
        res = requests.get(url)
        
        if res.status_code == 200:
            data = res.json()
            
            # Setup the base row for the CSV
            match_row = {
                'match_id': data.get('match_id'),
                'league_id': data.get('leagueid'),
                'radiant_win': data.get('radiant_win'),
                'duration': data.get('duration'),
                'radiant_team': data.get('radiant_team', {}).get('name', 'Unknown'),
                'dire_team': data.get('dire_team', {}).get('name', 'Unknown')
            }
            
            
            for player in data.get('players', []):
                slot = player.get('player_slot', 0)
                side = "radiant" if slot < 128 else "dire"
                idx = (slot if slot < 128 else slot - 128) + 1 
                
                name = player.get('name') or player.get('personaname') or "Unknown"
                hero_id = player.get('hero_id')
                
                # Dynamic column mapping
                match_row[f'{side}_player_{idx}'] = name
                match_row[f'{side}_hero_{idx}'] = hero_id
                
            all_detailed_matches.append(match_row)
            print(f"Processed match {i+1}/{len(match_ids_to_fetch)} (ID: {match_id})")
        else:
            print(f"API Error {res.status_code} on match ID {match_id}.")
            
        time.sleep(1.1) 

    
    df = pd.DataFrame(all_detailed_matches)
    df.to_csv(csv_file, index=False)
    print(f"\n✅ Test Finished! Saved {len(df)} detailed rows to {csv_file}")
    print("You can open this file now to inspect your flattened features.")

if __name__ == "__main__":
    fetch_test_dataset(target_match_count=10)