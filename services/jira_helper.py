import os
import requests
from typing import Optional
from dotenv import load_dotenv
from models.jira_model import JiraTicket

load_dotenv()

BASE_URL = "https://tusharsoni1420014.atlassian.net/rest/api/2"

email = os.getenv("JIRA_EMAIL")
api_token = os.getenv("JIRA_API_TOKEN")

if not email or not api_token:
    raise ValueError("JIRA_EMAIL and JIRA_API_TOKEN must be set in .env")

def get_ticket(ticket_key: str) -> Optional[JiraTicket]:
    """
        Fetch JIRA ticket details and return as Pydantic model.
        
        Args:
            ticket_key: JIRA ticket key (e.g., 'SCRUM-1')
            
        Returns:
            JiraTicket model instance or None if failed
            
        Raises:
            requests.exceptions.RequestException: Network/HTTP errors
            ValueError: Invalid response structure
        """
    url = f"{BASE_URL}/issue/{ticket_key}"
    params = {
            "fields": "key,summary,status,project,description,resolution,assignee"
        }
        
    try:
        response = requests.get(
            url,
            params=params,
            auth=(email, api_token),
            timeout=10
        )
        response.raise_for_status()
            
        data = response.json()
        fields = data.get("fields", {})
            
        # Extract nested data safely
        assignee = fields.get("assignee") or {}
        project = fields.get("project") or {}
        status = fields.get("status") or {}
            
        ticket = JiraTicket(
            key=data.get("key"),
            summary=fields.get("summary"),
            project_name=project.get("name"),
            description=fields.get("description"),
            assignee_email=assignee.get("emailAddress"),
            assignee_name=assignee.get("displayName", "Unassigned"),
            resolution=fields.get("resolution"),
            status_name=status.get("name")
        )
            
        return ticket
            
    except requests.exceptions.Timeout:
        print(f"Error: Request timeout for ticket {ticket_key}")
        return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("Error: Authentication failed. Check JIRA credentials.")
        elif e.response.status_code == 404:
            print(f"Error: Ticket {ticket_key} not found.")
        else:
            print(f"Error: HTTP {e.response.status_code} - {e.response.text}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error: Network error - {str(e)}")
        return None
    except ValueError as e:
        print(f"Error: Invalid response structure - {str(e)}")
        return None