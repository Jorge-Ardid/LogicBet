# Football Data Multi-Source System

This enhanced football data system integrates multiple data sources to provide comprehensive football analytics and betting predictions with intelligent fallback mechanisms.

## 🏈 Data Sources

### 1. Football-Data.org (Recommended Primary)
- **Cost**: Free tier available
- **Rate Limit**: 10 requests/minute
- **Coverage**: Top 5 European leagues + Champions League
- **Strengths**: Developer-friendly, excellent documentation, reliable
- **Setup**: Register at https://www.football-data.org/

### 2. API-Football via RapidAPI (Fallback)
- **Cost**: Free tier available
- **Rate Limit**: 100 requests/day
- **Coverage**: 800+ leagues worldwide
- **Strengths**: Extensive coverage, deep statistics
- **Setup**: Subscribe at https://rapidapi.com/api-sports/api/api-football/

### 3. Open Goal DB (Historical)
- **Cost**: Free (Open Source)
- **Coverage**: Historical match data
- **Strengths**: Great for training Elo models
- **Setup**: No API key required

## 🚀 Quick Start

### 1. Initial Setup
```bash
cd python
python setup.py
```

Follow the interactive setup to configure your API keys and preferences.

### 2. Run Sync
```bash
# Normal sync (respects cooldown)
python main.py

# Force sync (ignores cooldown)
python main.py --force

# Legacy mode (original sync engine)
python main.py --legacy

# Reconfigure settings
python main.py --setup
```

## 📁 File Structure

```
python/
├── main.py                    # Main entry point (updated for multi-source)
├── config_manager.py          # Configuration management
├── multi_source_sync.py       # Multi-source sync engine
├── football_data_client.py    # Football-Data.org API client
├── api_client.py             # Enhanced API-Football client
├── open_goal_loader.py       # Historical data loader
├── database.py              # Database layer (unchanged)
├── analytics.py             # Analytics engine (unchanged)
├── setup.py                 # Interactive setup script
└── ../data/
    ├── api_config.json       # API configuration
    └── sample_matches.json   # Sample historical data
```

## ⚙️ Configuration

### API Keys
The system supports multiple API keys with automatic fallback:

```python
from config_manager import ConfigManager

config = ConfigManager()
config.set_api_key('football_data_org', 'your_api_key_here')
config.set_api_key('api_football', 'your_rapidapi_key_here')
config.store_to_db()
```

### Data Source Priority
Configure primary and fallback data sources:

```python
config.set_data_sources(
    primary='football_data_org',  # Try this first
    fallback='api_football'       # Use if primary fails
)
```

### League Configuration
Enable specific leagues:

```python
config.set_enabled_leagues([39, 140, 78, 61, 135])  # PL, La Liga, Bundesliga, Serie A, Ligue 1
```

## 🔧 Advanced Usage

### Multi-Source Sync Engine
The new sync engine automatically:
1. Tries primary data source first
2. Falls back to secondary source if needed
3. Normalizes data from different APIs
4. Handles rate limiting gracefully
5. Maintains sync cooldowns

### Custom Sync Logic
```python
from multi_source_sync import MultiSourceSyncEngine

engine = MultiSourceSyncEngine()
engine.run_full_sync(force_sync=True)
engine.print_status()
```

### Historical Data Import
```python
from open_goal_loader import OpenGoalDBLoader

loader = OpenGoalDBLoader()
loader.download_historical_data()
loader.bulk_import_from_directory()
```

## 📊 API Features

### Football-Data.org Client
```python
from football_data_client import FootballDataClient

client = FootballDataClient(api_key='your_key')
matches = client.fetch_matches(competition_id='PL')
standings = client.fetch_standings('PL')
teams = client.fetch_teams('PL')
```

### Enhanced API-Football Client
```python
from api_client import APIFootballClient

client = APIFootballClient(api_key='your_key')
fixtures = client.fetch_fixtures(date='2026-04-13')
standings = client.fetch_standings(league_id=39)
predictions = client.fetch_predictions(fixture_id=123456)
lineups = client.fetch_lineups(fixture_id=123456)
events = client.fetch_events(fixture_id=123456)
```

## 🛡️ Rate Limiting

### Football-Data.org
- **Free Tier**: 10 requests/minute
- **Monitoring**: Automatic tracking of remaining requests
- **Handling**: Graceful fallback when limits reached

### API-Football
- **Free Tier**: 100 requests/day
- **Monitoring**: Daily limit tracking
- **Handling**: Cooldown management to prevent overuse

## 🔄 Fallback Strategy

The system implements intelligent fallback:

1. **Primary Source**: Attempts to fetch from configured primary source
2. **Secondary Source**: Falls back to secondary if primary fails
3. **Legacy Mode**: Falls back to original sync engine if both fail
4. **Offline Mode**: Works with local data if all sources fail

## 📈 Data Normalization

Different APIs return data in different formats. The system normalizes:

- Match fixtures and results
- Team names and IDs
- League information
- Score formats
- Status codes

## 🗄️ Database Schema

The existing database schema is maintained with new fields:

```sql
-- New config entries for API keys and settings
INSERT INTO config (key, value) VALUES 
('api_key_football_data_org', 'your_key'),
('api_key_api_football', 'your_key'),
('primary_data_source', 'football_data_org'),
('fallback_data_source', 'api_football'),
('sync_cooldown', '43200'),
('use_historical_data', 'true');
```

## 🐛 Troubleshooting

### Common Issues

1. **API Key Not Working**
   ```bash
   python setup.py  # Reconfigure API keys
   ```

2. **Rate Limit Exceeded**
   ```bash
   # Wait for cooldown or use --force
   python main.py --force
   ```

3. **Data Source Failing**
   ```bash
   # Check status and try legacy mode
   python main.py --legacy
   ```

4. **Configuration Issues**
   ```bash
   # Reset configuration
   rm ../data/api_config.json
   python setup.py
   ```

### Debug Mode
Enable detailed logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📝 API Reference

### League IDs
- **39**: Premier League (England)
- **140**: La Liga (Spain)
- **78**: Bundesliga (Germany)
- **61**: Serie A (Italy)
- **135**: Ligue 1 (France)
- **2**: Champions League
- **3**: Europa League

### Football-Data.org Competition Codes
- **PL**: Premier League
- **PD**: La Liga
- **BL1**: Bundesliga
- **SA**: Serie A
- **FL1**: Ligue 1
- **CL**: Champions League
- **EL**: Europa League

## 🔄 Migration from Legacy

If you're upgrading from the original system:

1. **Backup Database**
   ```bash
   cp ../godot_app/logicbet.db ../godot_app/logicbet_backup.db
   ```

2. **Run Setup**
   ```bash
   python setup.py
   ```

3. **Test New System**
   ```bash
   python main.py --force
   ```

4. **Fallback Available**
   ```bash
   python main.py --legacy  # If needed
   ```

## 🚨 Security Notes

- API keys are stored in configuration file and database
- Keys are masked in status output
- Consider using environment variables for production
- Never commit API keys to version control

## 📚 Additional Resources

- [Football-Data.org Documentation](https://www.football-data.org/documentation)
- [API-Football Documentation](https://rapidapi.com/api-sports/api/api-football/)
- [Open Goal DB GitHub](https://github.com/football-data/football-data.org)

## 🤝 Contributing

To add new data sources:

1. Create API client class following existing patterns
2. Add normalization logic in `multi_source_sync.py`
3. Update configuration in `config_manager.py`
4. Test with `setup.py`

## 📄 License

This system maintains the same license as the original project. External APIs have their own terms of service.
