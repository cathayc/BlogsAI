"""Timezone utilities for consistent date handling."""

from datetime import datetime, timezone
from typing import Optional
import pytz


def get_utc_now() -> datetime:
    """Get current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Convert datetime to UTC.
    
    Args:
        dt: datetime object (naive or timezone-aware)
        
    Returns:
        datetime: UTC datetime with timezone info
    """
    if dt is None:
        return None
        
    if dt.tzinfo is None:
        # Assume naive datetime is in local timezone
        local_tz = pytz.timezone('UTC')  # Default to UTC for safety
        try:
            import time
            local_tz = pytz.timezone(time.tzname[0])
        except:
            pass
        dt = local_tz.localize(dt)
    
    return dt.astimezone(timezone.utc)


def to_local_timezone(dt: datetime) -> datetime:
    """Convert UTC datetime to user's local timezone.
    
    Args:
        dt: UTC datetime object
        
    Returns:
        datetime: datetime in local timezone
    """
    if dt is None:
        return None
        
    # Ensure the datetime is timezone-aware and in UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    elif dt.tzinfo != timezone.utc:
        dt = dt.astimezone(timezone.utc)
    
    # Get system's local timezone
    try:
        import time
        local_tz = pytz.timezone(time.tzname[time.daylight])
    except:
        # Fallback to system default
        local_tz = datetime.now().astimezone().tzinfo
        
    return dt.astimezone(local_tz)


def format_local_datetime(dt: datetime, format_str: str = "%Y-%m-%d %H:%M") -> str:
    """Format UTC datetime as local timezone string.
    
    Args:
        dt: UTC datetime object
        format_str: strftime format string
        
    Returns:
        str: formatted datetime string in local timezone
    """
    if dt is None:
        return ""
        
    local_dt = to_local_timezone(dt)
    return local_dt.strftime(format_str)


def format_local_date(dt: datetime, format_str: str = "%Y-%m-%d") -> str:
    """Format UTC datetime as local date string.
    
    Args:
        dt: UTC datetime object
        format_str: strftime format string
        
    Returns:
        str: formatted date string in local timezone
    """
    if dt is None:
        return ""
        
    local_dt = to_local_timezone(dt)
    return local_dt.strftime(format_str)


def parse_date_to_utc(date_str: str, source_timezone: Optional[str] = None) -> Optional[datetime]:
    """Parse date string and convert to UTC.
    
    Args:
        date_str: date string to parse
        source_timezone: timezone of the source date (defaults to UTC)
        
    Returns:
        datetime: UTC datetime with timezone info, or None if parsing fails
    """
    if not date_str:
        return None
        
    # Common date formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds
        "%Y-%m-%dT%H:%M:%SZ",     # ISO with seconds
        "%Y-%m-%dT%H:%M:%S",      # ISO without timezone
        "%Y-%m-%d %H:%M:%S",      # Standard SQL format
        "%Y-%m-%d",               # Date only
        "%B %d, %Y",              # "January 1, 2024"
        "%b %d, %Y",              # "Jan 1, 2024"
        "%b. %d, %Y",             # "Jan. 1, 2024"
        "%m/%d/%Y",               # "1/1/2024"
        "%Y/%m/%d",               # "2024/01/01"
        "%m.%d.%Y",               # "1.1.2024"
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            
            # If timezone info is already present, convert to UTC
            if dt.tzinfo is not None:
                return dt.astimezone(timezone.utc)
            
            # For naive datetime, assume source timezone or UTC
            if source_timezone:
                try:
                    source_tz = pytz.timezone(source_timezone)
                    dt = source_tz.localize(dt)
                    return dt.astimezone(timezone.utc)
                except:
                    pass
            
            # Default to UTC for naive datetime
            return dt.replace(tzinfo=timezone.utc)
            
        except ValueError:
            continue
    
    return None
