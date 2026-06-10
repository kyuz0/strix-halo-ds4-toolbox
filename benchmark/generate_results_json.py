#!/usr/bin/env python3
import os
import json
import glob
import re

RESULTS_DIR = os.path.join(os.path.dirname(__file__), 'results')
DOCS_DIR = os.path.join(os.path.dirname(__file__), '..', 'docs')
OUTPUT_FILE = os.path.join(DOCS_DIR, 'results.json')

def parse_log(filepath):
    # Returns a dictionary mapping model_name to data points
    results = {}
    try:
        with open(filepath, 'r') as f:
            content = f.read()
            
        runs = content.split('ds4-bench -m')
        for run in runs[1:]: # skip preamble
            m = re.search(r'([^/\s]+\.gguf)', run)
            if not m:
                continue
            model_name = m.group(1)
            
            # Find the CSV block
            csv_match = re.search(r'ctx_tokens,prefill_tokens,prefill_tps,gen_tokens,gen_tps,kvcache_bytes\n(.*)', run, re.DOTALL)
            if not csv_match:
                continue
                
            data = []
            csv_lines = csv_match.group(1).strip().split('\n')
            for line in csv_lines:
                line = line.strip()
                if not line:
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
                        break # End of CSV block
                        
            if data:
                results[model_name] = data
                
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        
    return results

def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    all_results = {}
    
    log_files = glob.glob(os.path.join(RESULTS_DIR, "*.log"))
    if not log_files:
        print(f"No log files found in {RESULTS_DIR}. Please run the benchmarks first.")
        return
        
    for filepath in log_files:
        parsed_data = parse_log(filepath)
        for model_name, data in parsed_data.items():
            all_results[model_name] = data
            print(f"Parsed {len(data)} data points for model {model_name} from {os.path.basename(filepath)}")
            
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_results, f, indent=2)
        
    print(f"\nResults successfully parsed and saved to {OUTPUT_FILE}")

if __name__ == '__main__':
    main()
