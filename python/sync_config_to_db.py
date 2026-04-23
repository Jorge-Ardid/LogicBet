import sys
import os

# Add python directory to path
sys.path.append(os.getcwd())

from config_manager import ConfigManager

config = ConfigManager()
config.store_to_db()
print("✅ API keys synchronized to database.")
