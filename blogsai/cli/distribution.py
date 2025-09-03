"""
CLI tool for managing BlogsAI distribution settings.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add the project root to the path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from blogsai.config.distribution import get_distribution_manager
from blogsai.config.config import ConfigManager


def show_info():
    """Show distribution information."""
    dist_manager = get_distribution_manager()
    info = dist_manager.get_distribution_info()

    print("BlogsAI Distribution Information")
    print("=" * 40)
    print(f"Mode: {info['mode']}")
    print(f"Platform: {info['platform']}")
    print()
    print("Directories:")
    print(f"  Data: {info['data_directory']}")
    print(f"  Config: {info['config_directory']}")
    print(f"  Cache: {info['cache_directory']}")
    print(f"  Logs: {info['logs_directory']}")
    print()
    print("Files:")
    print(f"  Database: {info['database_path']}")
    print(f"  Settings: {info['settings_path']}")
    print(f"  Sources: {info['sources_path']}")
    print(f"  Prompts: {info['prompts_directory']}")
    print(f"  Reports: {info['reports_directory']}")


def enable_portable():
    """Enable portable mode."""
    dist_manager = get_distribution_manager()

    if dist_manager.is_portable:
        print("Portable mode is already enabled.")
        return

    print("Enabling portable mode...")
    dist_manager.create_portable_marker()
    print("Portable mode enabled. Restart the application for changes to take effect.")


def disable_portable():
    """Disable portable mode."""
    dist_manager = get_distribution_manager()

    if not dist_manager.is_portable:
        print("Portable mode is already disabled.")
        return

    print("Disabling portable mode...")
    dist_manager.remove_portable_marker()
    print("Portable mode disabled. Restart the application for changes to take effect.")


def migrate_data(source_dir: str, target_dir: Optional[str] = None):
    """Migrate data between directories."""
    import shutil

    source_path = Path(source_dir)
    if not source_path.exists():
        print(f"Error: Source directory does not exist: {source_path}")
        return False

    dist_manager = get_distribution_manager()

    if target_dir:
        target_path = Path(target_dir)
    else:
        target_path = dist_manager.get_data_directory()

    print(f"Migrating data from {source_path} to {target_path}")

    # Create target directory
    target_path.mkdir(parents=True, exist_ok=True)

    # Copy files
    try:
        for item in source_path.iterdir():
            if item.is_file():
                shutil.copy2(item, target_path / item.name)
                print(f"  Copied: {item.name}")
            elif item.is_dir():
                shutil.copytree(item, target_path / item.name, dirs_exist_ok=True)
                print(f"  Copied directory: {item.name}")

        print("Migration completed successfully.")
        return True

    except Exception as e:
        print(f"Error during migration: {e}")
        return False


def setup_credentials():
    """Interactive credential setup."""
    import getpass

    config_manager = ConfigManager()

    print("BlogsAI Credential Setup")
    print("=" * 30)

    # OpenAI API Key
    current_key = config_manager.get_openai_api_key()
    if current_key:
        print("OpenAI API key is already configured.")
        update = input("Update it? (y/N): ").lower().strip()
        if update != "y":
            print("Keeping existing API key.")
            return

    try:
        api_key = getpass.getpass("Enter your OpenAI API key: ").strip()
        if api_key:
            if config_manager.set_openai_api_key(api_key):
                print("OpenAI API key stored securely.")
            else:
                print("Failed to store API key.")
        else:
            print("No API key entered.")
    except KeyboardInterrupt:
        print("\nSetup cancelled.")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="BlogsAI Distribution Management Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s info                    # Show distribution information
  %(prog)s portable --enable       # Enable portable mode
  %(prog)s portable --disable      # Disable portable mode
  %(prog)s migrate /old/data       # Migrate data to current location
  %(prog)s credentials             # Setup credentials interactively
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Info command
    subparsers.add_parser("info", help="Show distribution information")

    # Portable mode command
    portable_parser = subparsers.add_parser("portable", help="Manage portable mode")
    portable_group = portable_parser.add_mutually_exclusive_group(required=True)
    portable_group.add_argument(
        "--enable", action="store_true", help="Enable portable mode"
    )
    portable_group.add_argument(
        "--disable", action="store_true", help="Disable portable mode"
    )

    # Migration command
    migrate_parser = subparsers.add_parser(
        "migrate", help="Migrate data between directories"
    )
    migrate_parser.add_argument(
        "source", help="Source directory containing data to migrate"
    )
    migrate_parser.add_argument(
        "--target", help="Target directory (default: current data directory)"
    )

    # Credentials command
    subparsers.add_parser("credentials", help="Setup credentials interactively")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "info":
            show_info()
        elif args.command == "portable":
            if args.enable:
                enable_portable()
            elif args.disable:
                disable_portable()
        elif args.command == "migrate":
            migrate_data(args.source, args.target)
        elif args.command == "credentials":
            setup_credentials()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
