"""
Community Events Check

Checks if the repository organizes or participates in community events.
"""
import os
import re
import logging
import datetime
from typing import Dict, Any, List, Set

# Setup logging
logger = logging.getLogger(__name__)

def check_community_events(repo_path: str = None, repo_data: Dict = None) -> Dict[str, Any]:
    """
    Check for community events in the repository
    
    Args:
        repo_path: Path to the repository on local filesystem
        repo_data: Repository data from API (used if repo_path is not available)
        
    Returns:
        Dictionary with check results
    """
    result = {
        "has_events": False,
        "event_types": [],
        "upcoming_events": 0,
        "past_events": 0,
        "participates_in_hackathons": False,
        "has_meetups": False,
        "has_conferences": False,
        "has_regular_meetings": False,
        "event_files": [],
        "event_urls": [],
        "analysis_method": "local_clone" if repo_path and os.path.isdir(repo_path) else "api"
    }
    
    # Prioritize local repository analysis
    if repo_path and os.path.isdir(repo_path):
        logger.debug(f"Analyzing community events in local repository")
        
        # Files and directories that may contain event information
        event_file_patterns = [
            "EVENTS.md", "events.md", "MEETUPS.md", "meetups.md",
            "COMMUNITY.md", "community.md", "CONTRIBUTING.md",
            "docs/events.md", "docs/community.md", 
            "docs/meetups.md", "community/events.md",
            "HACKATHON.md", "hackathon.md", "HACKATHONS.md",
            "CONFERENCE.md", "conference.md", "CONFERENCES.md",
            "MEETING.md", "meetings.md", "community-meetings.md"
        ]
        
        # Directories that may contain event information
        event_directories = [
            "events", "docs/events", "community/events",
            "meetups", "docs/meetups", "community/meetups",
            "conferences", "docs/conferences", "community/conferences",
            "meetings", "docs/meetings", "community/meetings"
        ]
        
        # Event keywords to search for in files
        event_keywords = [
            "meetup", "conference", "hackathon", "webinar", "workshop", 
            "sprint", "talk", "presentation", "community call", "office hours",
            "town hall", "ama", "ask me anything", "community meeting"
        ]
        
        # Event type classification
        event_type_patterns = {
            "meetup": [r'meetup', r'meeting', r'gathering'],
            "conference": [r'conference', r'summit', r'convention', r'forum'],
            "hackathon": [r'hackathon', r'codeathon', r'code sprint', r'hack day'],
            "webinar": [r'webinar', r'web seminar', r'online workshop', r'web workshop'],
            "workshop": [r'workshop', r'training', r'class', r'seminar'],
            "community_meeting": [r'community call', r'community meeting', r'office hours', r'town hall']
        }
        
        # Find event files and directories
        found_event_files = []
        
        # Check for event files
        for pattern in event_file_patterns:
            file_path = os.path.join(repo_path, pattern)
            if os.path.isfile(file_path):
                rel_path = os.path.relpath(file_path, repo_path)
                found_event_files.append(rel_path)
                result["event_files"].append(rel_path)
                result["has_events"] = True
        
        # Check for event directories
        for dir_pattern in event_directories:
            dir_path = os.path.join(repo_path, dir_pattern)
            if os.path.isdir(dir_path):
                rel_path = os.path.relpath(dir_path, repo_path)
                result["event_files"].append(rel_path)
                result["has_events"] = True
                
                # Check files in the events directory
                for root, _, files in os.walk(dir_path):
                    for file in files:
                        if file.endswith(('.md', '.txt', '.html')):
                            file_path = os.path.join(root, file)
                            rel_file_path = os.path.relpath(file_path, repo_path)
                            found_event_files.append(rel_file_path)
        
        # Look for GitHub discussion categories related to events
        discussion_dir = os.path.join(repo_path, ".github/DISCUSSION_TEMPLATE")
        if os.path.isdir(discussion_dir):
            for file in os.listdir(discussion_dir):
                if file.endswith('.md'):
                    file_path = os.path.join(discussion_dir, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            if any(keyword in content for keyword in event_keywords):
                                rel_path = os.path.relpath(file_path, repo_path)
                                found_event_files.append(rel_path)
                                result["has_events"] = True
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
        
        # If we don't have specific event files, check in README and community docs
        if not found_event_files:
            general_docs = ["README.md", "COMMUNITY.md", "CONTRIBUTING.md", "docs/README.md", 
                           "GOVERNANCE.md", "SUPPORT.md", "docs/community/README.md"]
            
            for doc in general_docs:
                file_path = os.path.join(repo_path, doc)
                if os.path.isfile(file_path):
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            
                            # Look for event mentions
                            if any(keyword in content for keyword in event_keywords):
                                rel_path = os.path.relpath(file_path, repo_path)
                                found_event_files.append(rel_path)
                                result["event_files"].append(rel_path)
                                result["has_events"] = True
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {e}")
        
        # Extract event details from files
        upcoming_count = 0
        past_count = 0
        event_types = set()
        event_urls = []
        
        for file_path in found_event_files:
            full_path = os.path.join(repo_path, file_path)
            if not os.path.isfile(full_path):
                continue
                
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().lower()
                    
                    # Look for event types
                    for event_type, patterns in event_type_patterns.items():
                        if any(re.search(pattern, content) for pattern in patterns):
                            event_types.add(event_type)
                            
                            # Update specific event type flags
                            if event_type == "meetup":
                                result["has_meetups"] = True
                            elif event_type == "conference":
                                result["has_conferences"] = True
                            elif event_type == "hackathon":
                                result["participates_in_hackathons"] = True
                            elif event_type == "community_meeting":
                                result["has_regular_meetings"] = True
                    
                    # Look for dates to categorize upcoming vs past events
                    # Common date formats: YYYY-MM-DD, Month DD YYYY, DD Month YYYY
                    date_patterns = [
                        r'(\d{4}-\d{1,2}-\d{1,2})',  # YYYY-MM-DD
                        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}',  # Month DD YYYY
                        r'\d{1,2} (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}'  # DD Month YYYY
                    ]
                    
                    dates = []
                    for pattern in date_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        dates.extend(matches)
                    
                    # Convert dates to datetime objects
                    parsed_dates = []
                    today = datetime.datetime.now().date()
                    
                    for date_str in dates:
                        if isinstance(date_str, tuple):  # For capturing groups in regex
                            date_str = date_str[0]
                            
                        try:
                            # Try to parse ISO format first
                            parsed_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                            parsed_dates.append(parsed_date)
                        except ValueError:
                            try:
                                # Try Month DD YYYY format
                                parsed_date = datetime.datetime.strptime(date_str, '%b %d, %Y').date()
                                parsed_dates.append(parsed_date)
                            except ValueError:
                                try:
                                    parsed_date = datetime.datetime.strptime(date_str, '%b %d %Y').date()
                                    parsed_dates.append(parsed_date)
                                except ValueError:
                                    try:
                                        # Try DD Month YYYY format
                                        parsed_date = datetime.datetime.strptime(date_str, '%d %b %Y').date()
                                        parsed_dates.append(parsed_date)
                                    except ValueError:
                                        pass  # Ignore dates we can't parse
                    
                    # Categorize events as upcoming or past
                    for date in parsed_dates:
                        if date >= today:
                            upcoming_count += 1
                        else:
                            past_count += 1
                    
                    # Extract URLs for event-related sites
                    url_patterns = [
                        r'https?://(?:www\.)?meetup\.com/[^\s\)\"\']+',
                        r'https?://(?:www\.)?eventbrite\.com/[^\s\)\"\']+',
                        r'https?://(?:www\.)?conference[s]?\.io/[^\s\)\"\']+',
                        r'https?://(?:www\.)?hopin\.com/[^\s\)\"\']+',
                        r'https?://(?:www\.)?zoom\.us/[^\s\)\"\']+',
                        r'https?://(?:www\.)?discord\.gg/[^\s\)\"\']+',
                        r'https?://(?:meet\.)?google\.com/[^\s\)\"\']+',
                        r'https?://(?:teams\.)?microsoft\.com/[^\s\)\"\']+',
                        r'https?://(?:www\.)?slido\.com/[^\s\)\"\']+',
                        r'https?://(?:www\.)?(?:devpost|challengepost)\.com/[^\s\)\"\']+',
                        r'https?://(?:www\.)?youtube\.com/[^\s\)\"\']+',
                        r'https?://(?:www\.)?twitch\.tv/[^\s\)\"\']+',
                    ]
                    
                    for pattern in url_patterns:
                        matches = re.findall(pattern, content)
                        for url in matches:
                            if url not in event_urls:
                                event_urls.append(url)
            except Exception as e:
                logger.error(f"Error analyzing event file {full_path}: {e}")
        
        # Check for calendar files
        calendar_files = [
            'calendar.md', 'Calendar.md', 'CALENDAR.md',
            'schedule.md', 'Schedule.md', 'SCHEDULE.md',
            'agenda.md', 'Agenda.md', 'AGENDA.md',
            'docs/calendar.md', 'docs/schedule.md',
            'events/calendar.md', 'events/schedule.md',
            'community/calendar.md', 'community/schedule.md',
            'events.ics', 'calendar.ics', 'schedule.ics',
            'meetings.json', 'events.json', 'calendar.json'
        ]
        
        for cal_file in calendar_files:
            file_path = os.path.join(repo_path, cal_file)
            if os.path.isfile(file_path):
                result["has_events"] = True
                rel_path = os.path.relpath(file_path, repo_path)
                if rel_path not in result["event_files"]:
                    result["event_files"].append(rel_path)
        
        # Check for event mentions in CI files (some projects have scheduled events via workflows)
        ci_files = [
            '.github/workflows/meetup.yml', '.github/workflows/meeting.yml',
            '.github/workflows/event.yml', '.github/workflows/community.yml',
            '.github/workflows/schedule.yml'
        ]
        
        for ci_file in ci_files:
            file_path = os.path.join(repo_path, ci_file)
            if os.path.isfile(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read().lower()
                        
                        # Look for event-related keywords in workflow
                        if any(keyword in content for keyword in event_keywords):
                            result["has_events"] = True
                            result["has_regular_meetings"] = True
                            rel_path = os.path.relpath(file_path, repo_path)
                            if rel_path not in result["event_files"]:
                                result["event_files"].append(rel_path)
                except Exception as e:
                    logger.error(f"Error reading CI file {file_path}: {e}")
        
        # Check for community discussions in the issue tracker
        issue_files_path = os.path.join(repo_path, ".github", "ISSUE_TEMPLATE")
        if os.path.isdir(issue_files_path):
            for file in os.listdir(issue_files_path):
                if file.endswith('.md') or file.endswith('.yaml') or file.endswith('.yml'):
                    file_path = os.path.join(issue_files_path, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            
                            # Look for community events/meetings in issue templates
                            if any(keyword in content for keyword in event_keywords):
                                result["has_events"] = True
                                result["has_regular_meetings"] = True
                                rel_path = os.path.relpath(file_path, repo_path)
                                if rel_path not in result["event_files"]:
                                    result["event_files"].append(rel_path)
                    except Exception as e:
                        logger.error(f"Error reading issue template {file_path}: {e}")
        
        # Update result with findings
        result["upcoming_events"] = upcoming_count
        result["past_events"] = past_count
        result["event_types"] = list(event_types)
        result["event_urls"] = event_urls
    
    # If we didn't find anything through local analysis, use API data as fallback
    elif repo_data and "events" in repo_data:
        logger.info("No local repository information available. Using API data for events.")
        result["analysis_method"] = "api"
        
        events_data = repo_data["events"]
        
        # Extract basic event information from API data
        result["has_events"] = events_data.get("has_events", False)
        result["upcoming_events"] = events_data.get("upcoming", 0)
        result["past_events"] = events_data.get("past", 0)
        result["event_types"] = events_data.get("types", [])
        result["event_urls"] = events_data.get("urls", [])
        
        # Extract event-specific flags
        result["participates_in_hackathons"] = "hackathon" in result["event_types"]
        result["has_meetups"] = "meetup" in result["event_types"]
        result["has_conferences"] = "conference" in result["event_types"]
        result["has_regular_meetings"] = "community_meeting" in result["event_types"] or events_data.get("regular_meetings", False)
    
    # Calculate event engagement score (0-100 scale)
    score = calculate_event_score(result)
    result["event_score"] = score
    
    return result

def calculate_event_score(metrics: Dict[str, Any]) -> float:
    """Calculate community events score based on metrics"""
    score = 0
    
    # Points for having any events
    if metrics.get("has_events", False):
        score += 40
        
        # Points for different types of events (up to 30 points)
        event_types = metrics.get("event_types", [])
        if event_types:
            type_points = min(30, len(event_types) * 10)
            score += type_points
        
        # Points for upcoming events (up to 20 points)
        upcoming = metrics.get("upcoming_events", 0)
        if upcoming > 0:
            upcoming_points = min(20, upcoming * 10)
            score += upcoming_points
        
        # Points for past events (up to 10 points)
        past = metrics.get("past_events", 0)
        if past > 0:
            past_points = min(10, past * 2)
            score += past_points
        
        # Points for regular meetings
        if metrics.get("has_regular_meetings", False):
            score += 10
    
    # Ensure score is within 0-100 range
    return min(100, max(0, score))

def run_check(repository: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the community events check
    
    Args:
        repository: Repository data dictionary which might include a local_path
        
    Returns:
        Check results with score on 0-100 scale
    """
    try:
        # Check if we have a local path to the repository
        local_path = repository.get('local_path')
        
        # Run the check
        result = check_community_events(local_path, repository)
        
        # Return the result with the score
        return {
            "status": "completed",
            "score": result.get("event_score", 0),
            "result": result,
            "errors": None
        }
    except Exception as e:
        logger.error(f"Error running community events check: {e}")
        return {
            "status": "failed",
            "score": 0,
            "result": {},
            "errors": str(e)
        }