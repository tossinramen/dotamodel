import os
import time
import requests
import pandas as pd

# Your OpenDota Premium API Key
API_KEY = "3e35d8d3-98cc-4dde-806e-36250ed17283"

os.makedirs('data', exist_ok=True)

def fetch_massive_dataset(target_match_count=15000):
    print(f"Starting extraction for {target_match_count} matches with Premium Limits...")
    
    csv_file = 'data/massive_pro_dataset.csv'
    all_detailed_matches = []
    
    # 1. Resume Logic
    if os.path.exists(csv_file):
        existing_df = pd.read_csv(csv_file)
        all_detailed_matches = existing_df.to_dict('records')
        print(f"Resuming from existing {len(all_detailed_matches)} matches in CSV...")

    match_ids_to_fetch = []
    lowest_match_id = None
    
    print("\n[Phase 1] Collecting Match IDs...")
    while len(match_ids_to_fetch) + len(all_detailed_matches) < target_match_count:
        url = "https://api.opendota.com/api/proMatches"
        
        # Inject API key securely as a parameter
        params = {'api_key': API_KEY}
        if lowest_match_id:
            params['less_than_match_id'] = lowest_match_id
            
        res = requests.get(url, params=params)
        
        if res.status_code != 200:
            print(f"API Error {res.status_code}. Waiting 5s...")
            time.sleep(5)
            continue
            
        batch = res.json()
        if not batch: 
            break
        
        existing_ids = {m['match_id'] for m in all_detailed_matches}
        new_ids = [m['match_id'] for m in batch if m['match_id'] not in existing_ids]
        match_ids_to_fetch.extend(new_ids)
        
        lowest_match_id = min([m['match_id'] for m in batch])
        
        # Premium limit is 50 requests/sec. 0.05s wait is extremely safe and fast.
        time.sleep(0.05)  
        print(f"Collected {len(match_ids_to_fetch) + len(all_detailed_matches)} / {target_match_count} IDs...")

    match_ids_to_fetch = match_ids_to_fetch[:target_match_count - len(all_detailed_matches)]
    
    print(f"\n[Phase 2] Fetching Detailed Draft Data for {len(match_ids_to_fetch)} matches...")
    for i, match_id in enumerate(match_ids_to_fetch):
        url = f"https://api.opendota.com/api/matches/{match_id}"
        
        success = False
        retries = 0
        
        # 2. Robust Retry Logic implemented here
        while not success and retries < 5:
            res = requests.get(url, params={'api_key': API_KEY})
            
            if res.status_code == 200:
                data = res.json()
                
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
                    
                    match_row[f'{side}_player_{idx}'] = name
                    match_row[f'{side}_hero_{idx}'] = hero_id
                    
                all_detailed_matches.append(match_row)
                
                # Update: Only save every 50 matches so Pandas writing doesn't slow down your fast API requests
                if i % 50 == 0: 
                    pd.DataFrame(all_detailed_matches).to_csv(csv_file, index=False)
                    
                print(f"Processed match {i+1}/{len(match_ids_to_fetch)} (ID: {match_id})")
                success = True 
                
            elif res.status_code == 429:
                wait_time = 5 * (2 ** retries) # Shorter backoff penalty for Premium users
                print(f"Rate limited! Pausing for {wait_time}s before retrying {match_id}...")
                time.sleep(wait_time)
                retries += 1
            else:
                print(f"Unexpected Error {res.status_code} on match {match_id}. Skipping.")
                break 
                
        # 0.05 seconds ensures you hover around 20 requests per second, safely below the 50/sec limit.
        time.sleep(0.05) 

    df = pd.DataFrame(all_detailed_matches)
    df.to_csv(csv_file, index=False)
    print(f"\n✅ Finished! Saved {len(df)} detailed matches to {csv_file}")

if __name__ == "__main__":
    fetch_massive_dataset(target_match_count=15000)