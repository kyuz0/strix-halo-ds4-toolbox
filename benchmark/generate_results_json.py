#!/usr/bin/env python3
import os
import json
import glob
import re

RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'results')
DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs')
OUTPUT_FILE = os.path.join(DOCS_DIR, 'results.json')

def parse_log(filepath):
    data = []
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            
        # Find the CSV block
        match = re.search(r'ctx_tokens,prefill_tokens,prefill_tps,gen_tokens,gen_tps,kvcache_bytes\n(.*)', content, re.DOTALL)
        if not match:
            return data
            
        csv_lines = match.group(1).strip().split('\n')
        for line in csv_lines:
            if not line.strip():
                continue
            parts = line.split(',')
            if len(parts) >= 5:
                try:
                    data.append({
                        'ctx': int(parts[0]),
                        'prefill_tps': float(parts[2]),
                        'gen_tps': float(parts[4])
                    })
                except ValueError:
                    continue
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        
    return data

def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    all_results = {}
    
    log_files = glob.glob(os.path.join(RESULTS_DIR, "*.log"))
    if not log_files:
        print(f"No log files found in {RESULTS_DIR}. Please run the benchmarks first.")
        return
        
    for filepath in log_files:
        basename = os.path.basename(filepath)
        toolbox_name = basename.replace('.log', '')
        
        parsed_data = parse_log(filepath)
        if parsed_data:
            all_results[toolbox_name] = parsed_data
            print(f"Parsed {len(parsed_data)} data points for {toolbox_name}")
        else:
            print(f"Warning: No valid CSV data found in {filepath}")
            
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_results, f, indent=2)
        
    print(f"\nResults successfully parsed and saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
