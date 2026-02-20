import pandas as pd
import csv

file_path = r"c:\Users\user\.gemini\antigravity\NEW PROIECT\docs\seler (1).csv"

print("--- RAW TEXT HEAD (LATIN-1) ---")
with open(file_path, 'r', encoding='latin-1') as f:
    for i in range(3):
        print(f.readline().strip())

print("\n--- PANDAS READ ---")
try:
    df = pd.read_csv(file_path, header=None, encoding='latin-1')
    print(df.head(3).to_string())
    
    # Print sample row detailed
    print("\n--- COLUMN MAPPING ---")
    row = df.iloc[0]
    for i, val in enumerate(row):
        print(f"Col {i}: {val}")
        
except Exception as e:
    print(e)

