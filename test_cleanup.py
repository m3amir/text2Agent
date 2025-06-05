#!/usr/bin/env python3
"""
Test script for LogManager cleanup functionality
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Logs.log_manager import LogManager

def test_cleanup():
    """Test the cleanup functionality"""
    print("🧪 Testing LogManager Cleanup")
    print("=" * 50)
    
    # Initialize LogManager
    log_manager = LogManager('amir@m3labs.co.uk')
    
    # Check current log files
    logs_dir = Path('Logs')
    log_files = list(logs_dir.glob('*.log'))
    print(f"📁 Current log files: {len(log_files)}")
    for log_file in log_files:
        print(f"   • {log_file.name}")
    
    if not log_files:
        print("ℹ️  No log files to clean up")
        return
    
    print("\n🔄 Syncing logs first...")
    sync_results = log_manager.sync_logs(older_than_hours=0, delete_after_sync=False)
    print(f"Sync Results: {sync_results}")
    
    print("\n🧹 Testing cleanup of synced files...")
    deleted_count = log_manager.cleanup_synced_logs(sync_results)
    print(f"✅ Cleaned up {deleted_count} files")
    
    # Check remaining files
    remaining_files = list(logs_dir.glob('*.log'))
    print(f"\n📁 Remaining log files: {len(remaining_files)}")
    for log_file in remaining_files:
        print(f"   • {log_file.name}")

def test_aggressive_cleanup():
    """Test aggressive cleanup (all files)"""
    print("\n🧪 Testing Aggressive Cleanup")
    print("=" * 50)
    
    log_manager = LogManager('amir@m3labs.co.uk')
    
    # Show current files
    logs_dir = Path('Logs')
    log_files = list(logs_dir.glob('*.log'))
    print(f"📁 Current log files: {len(log_files)}")
    
    if log_files:
        print("\n🧹 Cleaning up ALL log files (with S3 verification)...")
        deleted_count = log_manager.cleanup_all_logs(verify_in_s3=True)
        print(f"✅ Cleaned up {deleted_count} files")
        
        # Check what's left
        remaining_files = list(logs_dir.glob('*.log'))
        print(f"\n📁 Remaining log files: {len(remaining_files)}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "aggressive":
        test_aggressive_cleanup()
    else:
        test_cleanup()
        
    print("\n💡 Usage:")
    print("  python test_cleanup.py          # Test normal cleanup")
    print("  python test_cleanup.py aggressive  # Test aggressive cleanup") 