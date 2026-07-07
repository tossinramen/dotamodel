import os
import requests
import pandas as pd

def main():
    
    os.makedirs('data', exist_ok=True)
    
    
    print("Fetching Esports Pro Matches...")
    pro_matches_url = "https://api.opendota.com/api/proMatches"
    pro_response = requests.get(pro_matches_url)
    
    if pro_response.status_code == 200:
        pro_df = pd.DataFrame(pro_response.json())
        # Save to CSV in the data folder
        pro_df.to_csv('data/pro_matches.csv', index=False)
        print(f"✅ Saved {len(pro_df)} pro matches to data/pro_matches.csv")
    else:
        print("Failed to fetch pro matches.")

    
    print("\nFetching Hero Stats (Solo Queue Meta)...")
    hero_stats_url = "https://api.opendota.com/api/heroStats"
    hero_response = requests.get(hero_stats_url)
    
    if hero_response.status_code == 200:
        hero_df = pd.DataFrame(hero_response.json())
        
        
        hero_df.to_csv('data/hero_meta_stats.csv', index=False)
        print(f"✅ Saved stats for {len(hero_df)} heroes to data/hero_meta_stats.csv")
    else:
        print("Failed to fetch hero stats.")

if __name__ == "__main__":
    main()