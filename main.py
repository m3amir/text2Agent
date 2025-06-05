#!/usr/bin/env python3
"""
Main Entry Point for AI Colleagues Application
"""

import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Global.Components.colleagues import Colleague
from Logs.log_manager import LogManager

# Configuration
USER_EMAIL = "amir@m3labs.co.uk"
AUTO_SYNC_HOURS = 1/60  # How often to sync logs to S3 (1 minute)
CLEANUP_AFTER_SYNC = True  # Delete local files after S3 upload
KEEP_RUNNING = True  # Keep program alive to test auto-sync (set False for normal operation)

if __name__ == "__main__":
    # Signed-in user
    user_email = USER_EMAIL
    
    # Initialize LogManager and AI Colleagues
    try:
        log_manager = LogManager(email=user_email)
        
        # Start auto sync scheduler
        try:
            log_manager.auto_sync_scheduler(
                interval_hours=AUTO_SYNC_HOURS, 
                cleanup_after_sync=CLEANUP_AFTER_SYNC
            )
            cleanup_msg = " with cleanup" if CLEANUP_AFTER_SYNC else ""
            
            # Format time display
            if AUTO_SYNC_HOURS < 1:
                time_display = f"{int(AUTO_SYNC_HOURS * 60)} min"
            else:
                time_display = f"{AUTO_SYNC_HOURS}h"
                
            print(f"⏰ Auto-sync scheduler started (every {time_display}{cleanup_msg})")
        except Exception as e:
            print(f"⚠️ Auto-sync setup failed: {e}")
        
        colleague = Colleague(user_email=user_email, log_manager=log_manager)
        
        # Run analysis
        task = "How can we improve team productivity using AI automation?"
        result = colleague.update_message([task])
        
        print(f"\n📋 Result: {result[:150]}...")
        
        # Keep program running to test auto-sync scheduler
        if KEEP_RUNNING:
            print(f"\n🔄 Program staying alive to test auto-sync (every {int(AUTO_SYNC_HOURS * 60)} min)")
            print("💡 Press Ctrl+C to exit")
            try:
                import time
                while True:
                    time.sleep(10)  # Sleep in 10-second intervals
            except KeyboardInterrupt:
                print("\n👋 Exiting gracefully...")
        
    except Exception as e:
        print(f"❌ Error: {e}") 