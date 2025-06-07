#!/usr/bin/env python3
"""
Migration runner script
"""
import asyncio
import logging
from app.core.dependencies import get_supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the avatar and lyrical themes migration"""
    try:
        # Read migration file
        with open('migrations/add_avatar_and_lyrical_themes.sql', 'r') as f:
            migration_sql = f.read()
        
        logger.info("🔄 Running migration: add_avatar_and_lyrical_themes.sql")
        
        # Get Supabase client
        supabase = get_supabase()
        
        # Execute migration using Supabase RPC
        # Since it's DDL, we'll execute it via raw SQL through RPC
        result = supabase.rpc('exec_sql', {'sql': migration_sql}).execute()
        
        if result.data is not None:
            logger.info("✅ Migration completed successfully")
        else:
            logger.error("❌ Migration may have failed - please check Supabase console")
        
    except Exception as e:
        # For DDL statements, we may need to run them directly in Supabase
        logger.error(f"❌ Migration failed: {e}")
        logger.info("💡 Please run the migration SQL directly in your Supabase SQL Editor:")
        logger.info("   1. Go to your Supabase Dashboard")
        logger.info("   2. Navigate to SQL Editor")
        logger.info("   3. Copy and run the contents of migrations/add_avatar_and_lyrical_themes.sql")

if __name__ == "__main__":
    run_migration() 