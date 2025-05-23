import re
import os
import argparse
from datetime import datetime, timedelta

def parse_srt_time(time_str):
    """Convert SRT timestamp to seconds"""
    # Format: 00:01:23,456 -> hours:minutes:seconds,milliseconds
    time_part, ms_part = time_str.split(',')
    h, m, s = map(int, time_part.split(':'))
    ms = int(ms_part)
    return h * 3600 + m * 60 + s + ms / 1000

def seconds_to_srt_time(seconds):
    """Convert seconds back to SRT timestamp format"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

def parse_srt_file(filename):
    """Parse SRT file into list of subtitle entries"""
    with open(filename, 'r', encoding='utf-8') as file:
        content = file.read()
    
    # Split by double newlines (subtitle blocks)
    blocks = content.strip().split('\n\n')
    subtitles = []
    
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) >= 3:
            # Extract subtitle number
            try:
                number = int(lines[0])
            except ValueError:
                continue
            
            # Extract timestamps
            timestamp_line = lines[1]
            if ' --> ' in timestamp_line:
                start_time, end_time = timestamp_line.split(' --> ')
                start_seconds = parse_srt_time(start_time.strip())
                end_seconds = parse_srt_time(end_time.strip())
                
                # Extract text (everything after the timestamp line)
                text = '\n'.join(lines[2:])
                
                subtitles.append({
                    'number': number,
                    'start': start_seconds,
                    'end': end_seconds,
                    'text': text
                })
    
    return subtitles

def split_srt_by_time(subtitles, chunk_duration_minutes=30, overlap_minutes=2):
    """Split subtitles into chunks with overlap"""
    chunk_duration = chunk_duration_minutes * 60  # Convert to seconds
    overlap_duration = overlap_minutes * 60  # Convert to seconds
    
    if not subtitles:
        return []
    
    chunks = []
    total_duration = max(sub['end'] for sub in subtitles)
    
    chunk_start = 0
    chunk_number = 1
    
    while chunk_start < total_duration:
        chunk_end = chunk_start + chunk_duration
        
        # For overlap, start the next chunk earlier
        next_chunk_start = chunk_end - overlap_duration
        
        # Get subtitles that fall within this chunk
        chunk_subtitles = []
        for sub in subtitles:
            # Include subtitle if it starts within chunk or overlaps with chunk
            if (sub['start'] >= chunk_start and sub['start'] < chunk_end) or \
               (sub['end'] > chunk_start and sub['start'] < chunk_end):
                chunk_subtitles.append(sub)
        
        if chunk_subtitles:
            # Calculate actual time range for this chunk
            actual_start = min(sub['start'] for sub in chunk_subtitles)
            actual_end = max(sub['end'] for sub in chunk_subtitles)
            
            chunks.append({
                'number': chunk_number,
                'start_time': actual_start,
                'end_time': actual_end,
                'subtitles': chunk_subtitles,
                'planned_start': chunk_start,
                'planned_end': chunk_end
            })
            
            chunk_number += 1
        
        # Move to next chunk
        chunk_start = next_chunk_start
        
        # Prevent infinite loop
        if next_chunk_start >= total_duration:
            break
    
    return chunks

def save_chunk_as_srt(chunk, output_filename):
    """Save a chunk as an SRT file"""
    with open(output_filename, 'w', encoding='utf-8') as file:
        for i, subtitle in enumerate(chunk['subtitles'], 1):
            file.write(f"{i}\n")
            start_time = seconds_to_srt_time(subtitle['start'])
            end_time = seconds_to_srt_time(subtitle['end'])
            file.write(f"{start_time} --> {end_time}\n")
            file.write(f"{subtitle['text']}\n\n")

def save_chunk_as_txt(chunk, output_filename):
    """Save a chunk as a plain text file"""
    with open(output_filename, 'w', encoding='utf-8') as file:
        # Write header with time range
        start_time = seconds_to_srt_time(chunk['start_time'])
        end_time = seconds_to_srt_time(chunk['end_time'])
        file.write(f"Music Therapy Session - Chunk {chunk['number']}\n")
        file.write(f"Time Range: {start_time} to {end_time}\n")
        file.write(f"Duration: {(chunk['end_time'] - chunk['start_time'])/60:.1f} minutes\n")
        file.write("=" * 50 + "\n\n")
        
        # Write all text content
        for subtitle in chunk['subtitles']:
            timestamp = seconds_to_srt_time(subtitle['start'])
            file.write(f"[{timestamp}] {subtitle['text']}\n")

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Split SRT files into chunks for LLM processing')
    parser.add_argument('input_file', help='Path to the SRT file to split')
    parser.add_argument('-d', '--duration', type=int, default=30, 
                       help='Duration of each chunk in minutes (default: 30)')
    parser.add_argument('-o', '--overlap', type=int, default=2,
                       help='Overlap between chunks in minutes (default: 2)')
    parser.add_argument('-f', '--format', choices=['srt', 'txt', 'both'], default='both',
                       help='Output format (default: both)')
    parser.add_argument('--output-dir', default=None,
                       help='Output directory (default: auto-generated from input filename)')
    
    args = parser.parse_args()
    
    # Configuration from command line arguments
    input_file = args.input_file
    chunk_duration_minutes = args.duration
    overlap_minutes = args.overlap
    output_format = args.format
    
    # Auto-generate output directory if not specified
    if args.output_dir:
        output_dir = args.output_dir
    else:
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_dir = f"{base_name}_chunks"
    
    print(f"Processing SRT file: {input_file}")
    print(f"Chunk duration: {chunk_duration_minutes} minutes")
    print(f"Overlap: {overlap_minutes} minutes")
    print("-" * 50)
    
    # Parse the SRT file
    try:
        subtitles = parse_srt_file(input_file)
        print(f"Loaded {len(subtitles)} subtitle entries")
        
        if not subtitles:
            print("No subtitles found in the file!")
            return
        
        total_duration = max(sub['end'] for sub in subtitles) / 60  # Convert to minutes
        print(f"Total duration: {total_duration:.1f} minutes")
        
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found!")
        print("Please make sure the file exists and update the 'input_file' variable.")
        return
    except Exception as e:
        print(f"Error parsing SRT file: {e}")
        return
    
    # Split into chunks
    chunks = split_srt_by_time(subtitles, chunk_duration_minutes, overlap_minutes)
    print(f"Created {len(chunks)} chunks")
    print("-" * 50)
    
    # Create output directory
    output_dir = "session_chunks"
    os.makedirs(output_dir, exist_ok=True)
    
    # Save chunks
    for chunk in chunks:
        chunk_num = chunk['number']
        start_min = chunk['start_time'] / 60
        end_min = chunk['end_time'] / 60
        duration = (chunk['end_time'] - chunk['start_time']) / 60
        
        print(f"Chunk {chunk_num}: {start_min:.1f}-{end_min:.1f} min ({duration:.1f} min duration)")
        
        if output_format in ["srt", "both"]:
            srt_filename = f"{output_dir}/chunk_{chunk_num:02d}.srt"
            save_chunk_as_srt(chunk, srt_filename)
        
        if output_format in ["txt", "both"]:
            txt_filename = f"{output_dir}/chunk_{chunk_num:02d}.txt"
            save_chunk_as_txt(chunk, txt_filename)
    
    print("-" * 50)
    print(f"All chunks saved to '{output_dir}' directory")
    print("\nNext steps:")
    print("1. Review the chunks to ensure they split at reasonable points")
    print("2. Process each chunk through your LLM (DeepSeek R1 70B or Mixtral)")
    print("3. Combine the summaries for final analysis")
    print(f"\nExample usage for next file:")
    print(f"python split_srt.py another_session.srt -d 25 -o 3 -f txt")

if __name__ == "__main__":
    main()
