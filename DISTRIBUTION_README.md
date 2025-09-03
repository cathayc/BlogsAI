# BlogsAI Desktop Application - Distribution

## For End Users

### Quick Start
1. **Download** `BlogsAI-Desktop.zip`
2. **Unzip** the file anywhere on your computer
3. **Double-click** `BlogsAI.app` to run
4. **No installation required!**

### Features
- AI-powered news analysis
- Government source scraping (DOJ, SEC, CFTC)
- Manual URL scraping with AI parsing
- HTML/PDF report generation
- Zoom functionality (Ctrl/Cmd +/-)
- Light theme interface (no dark mode)

## For Developers

### Build Instructions
To rebuild the application:

```bash
# Install dependencies
poetry install

# Build application
python build.py
```

This creates `dist/BlogsAI-Desktop.zip` ready for distribution.

### Project Structure
```
BlogsAI/
├── blogsai/           # Main application code
├── config/            # Configuration files
├── prompts/          # AI prompts
├── data/             # Database and reports
├── build.py          # Simple build script
├── standalone_app.py # PyInstaller entry point
└── pyproject.toml    # Dependencies
```

### Key Features
- **Standalone**: No Python installation required
- **Cross-platform**: Works on macOS (Windows build available)
- **Light theme**: Enforced light mode, no dark theme
- **Complete**: Includes database, prompts, and configuration
- **Professional**: Native .app bundle for macOS

## Technical Details

- **Size**: ~181MB (includes Python runtime and all dependencies)
- **Framework**: PyQt5 for cross-platform GUI
- **Database**: SQLite for local data storage
- **AI**: OpenAI API integration for analysis
- **Packaging**: PyInstaller for standalone executable
