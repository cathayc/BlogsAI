# BlogsAI Distribution Guide

This guide explains how BlogsAI handles distribution, configuration, and data storage across different platforms and deployment scenarios.

## Distribution Modes

BlogsAI supports three distribution modes, inspired by Calibre's approach:

### 1. Development Mode
- **When**: Running from source code with `.git` directory present
- **Data Location**: Project directory (`./data/`)
- **Config Location**: Project directory (`./data/config/`)
- **Best For**: Development and testing

### 2. Production Mode
- **When**: Installed application without portable marker
- **Data Locations**:
  - **Windows**: `%APPDATA%\BlogsAI\`
  - **macOS**: `~/Library/Application Support/BlogsAI/`
  - **Linux**: `~/.local/share/blogsai/` (XDG compliant)
- **Config Locations**:
  - **Windows**: `%APPDATA%\BlogsAI\config\`
  - **macOS**: `~/Library/Preferences/BlogsAI/`
  - **Linux**: `~/.config/blogsai/`
- **Best For**: End-user installations

### 3. Portable Mode
- **When**: `PORTABLE` file exists in application directory
- **Data Location**: Application directory (`./data/`)
- **Config Location**: Application directory (`./data/config/`)
- **Best For**: USB drives, shared computers, no-install scenarios

## Directory Structure

```
BlogsAI Data Directory/
├── blogsai.db              # Main SQLite database
├── cache/                  # Temporary files and caches
├── logs/                   # Application logs
├── reports/                # Generated intelligence reports
└── config/
    ├── settings.yaml       # Application settings
    ├── sources.yaml        # Data source configurations
    ├── prompts/            # AI prompt templates
    ├── .credentials.enc    # Encrypted credentials (if available)
    └── .key               # Encryption key (if available)
```

## Secure Credential Storage

BlogsAI uses a multi-tier approach for storing sensitive data like API keys:

1. **System Keyring** (Preferred): Uses OS-native credential storage
   - Windows: Windows Credential Manager
   - macOS: Keychain
   - Linux: Secret Service API (GNOME Keyring, KWallet)

2. **Encrypted File Storage** (Fallback): AES encryption with machine-specific key
   - Uses `cryptography` library if available
   - Key derived from machine characteristics

3. **Plain Text** (Last Resort): Only if no encryption is available
   - File permissions restricted to owner only
   - Warning displayed to user

## CLI Management Tool

Use the distribution CLI tool to manage your BlogsAI installation:

```bash
# Show current distribution information
python -m blogsai.cli.distribution info

# Enable portable mode
python -m blogsai.cli.distribution portable --enable

# Disable portable mode
python -m blogsai.cli.distribution portable --disable

# Migrate data from old location
python -m blogsai.cli.distribution migrate /old/data/path

# Setup credentials interactively
python -m blogsai.cli.distribution credentials
```

## Configuration Management

### Automatic Configuration Creation

BlogsAI automatically creates default configuration files if they don't exist:

- `settings.yaml`: Application settings (database, AI models, etc.)
- `sources.yaml`: Data source configurations (DOJ, SEC, CFTC, etc.)

### Environment Variables

The following environment variables are supported:

- `BLOGSAI_PORTABLE=1`: Force portable mode
- `BLOGSAI_DEV=1`: Force development mode
- `BLOGSAI_DATA_DIR`: Override data directory
- `BLOGSAI_CONFIG_DIR`: Override config directory
- `OPENAI_API_KEY`: OpenAI API key (migrated to secure storage)

### Credential Migration

When upgrading, BlogsAI automatically migrates credentials from environment variables to secure storage.

## Platform-Specific Considerations

### Windows
- Uses `%APPDATA%` and `%LOCALAPPDATA%` for data storage
- Integrates with Windows Credential Manager
- Supports both installer and portable distributions

### macOS
- Follows Apple's application guidelines
- Uses `~/Library/` directories appropriately
- Integrates with macOS Keychain
- Supports app bundle distribution

### Linux
- Follows XDG Base Directory Specification
- Uses `~/.local/share/`, `~/.config/`, `~/.cache/`
- Integrates with Secret Service API
- Supports package manager distribution

## Deployment Scenarios

### End-User Installation
1. Install BlogsAI using platform-specific installer
2. Run application - it automatically creates necessary directories
3. Use GUI or CLI to configure API keys securely
4. Data stored in user-specific directories

### Portable Deployment
1. Extract BlogsAI to desired location (USB drive, shared folder)
2. Create `PORTABLE` file in application directory
3. Run application - all data stays within application folder
4. Perfect for shared computers or no-install scenarios

### Enterprise Deployment
1. Use production mode with centralized configuration
2. Pre-configure settings files in deployment package
3. Use environment variables for initial setup
4. Credentials managed through enterprise credential systems

### Development Setup
1. Clone repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run from source - automatically uses development mode
4. All data stored in project directory for easy cleanup

## Security Features

### Credential Protection
- Never stores credentials in plain text configuration files
- Uses OS-native secure storage when available
- Falls back to encrypted file storage with machine-specific keys
- Automatic migration from insecure environment variables

### File Permissions
- Restricts access to credential files (600 permissions)
- Creates directories with appropriate permissions
- Warns users about insecure storage methods

### Data Isolation
- Each user gets their own data directory in production mode
- Portable mode isolates data within application folder
- No cross-user data leakage

## Migration and Backup

### Upgrading BlogsAI
1. New versions automatically detect and migrate old data formats
2. Configuration files are preserved and updated as needed
3. Database schema migrations are applied automatically

### Backing Up Data
```bash
# Backup entire data directory
cp -r "$(python -m blogsai.cli.distribution info | grep 'Data:' | cut -d' ' -f4-)" ./blogsai-backup/

# Or use the migration tool
python -m blogsai.cli.distribution migrate /current/data /backup/location
```

### Moving Between Computers
1. Export data from old computer using migration tool
2. Install BlogsAI on new computer
3. Import data using migration tool
4. Reconfigure credentials if needed

## Troubleshooting

### Common Issues

**"No such file or directory" errors**
- Check if configuration files exist in expected locations
- Run `python -m blogsai.cli.distribution info` to see current paths
- Ensure proper permissions on data directories

**"Failed to store credentials" warnings**
- Install `keyring` package for system keyring support
- Install `cryptography` package for encrypted file storage
- Check file permissions in config directory

**Database connection errors**
- Verify database file exists and is readable
- Check if data directory has write permissions
- Run database migration if upgrading from old version

### Getting Help

1. Run `python -m blogsai.cli.distribution info` to see current configuration
2. Check log files in the logs directory
3. Verify file permissions and directory structure
4. Try portable mode if having permission issues

## Best Practices

### For End Users
- Use production mode for regular use
- Keep credentials in secure storage (not environment variables)
- Regularly backup your data directory
- Update BlogsAI regularly for security fixes

### For Developers
- Use development mode for testing
- Keep test data separate from production data
- Use environment variables for development credentials
- Test both portable and production modes

### For System Administrators
- Use centralized configuration management
- Deploy in production mode with proper permissions
- Monitor log files for security issues
- Implement backup strategies for user data

## Advanced Configuration

### Custom Data Locations
```python
# Override data directory programmatically
import os
os.environ['BLOGSAI_DATA_DIR'] = '/custom/path'

# Or use distribution manager directly
from blogsai.config.distribution import get_distribution_manager
dist_manager = get_distribution_manager()
```

### Integration with External Systems
- Use secure credential storage APIs
- Implement custom configuration providers
- Integrate with enterprise identity systems
- Use external database systems instead of SQLite

This distribution system ensures BlogsAI works reliably across different platforms and deployment scenarios while maintaining security and user data integrity.
