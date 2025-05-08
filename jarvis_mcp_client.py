import requests
from typing import Any, Dict
import os                 # Added for os.getenv
from dotenv import load_dotenv # Added for .env loading

# Load environment variables from .env file, if it exists
load_dotenv()

class MCPClient:
    def __init__(self, base_url: str = None):
        if base_url is None:
            # Get MCP_SERVER from environment, default if not found
            self.base_url = os.getenv("MCP_SERVER", "http://localhost:9000").rstrip("/")
        else:
            # Allow overriding via direct parameter for flexibility/testing
            self.base_url = base_url.rstrip("/")
        
        print(f"MCPClient initialized with base URL: {self.base_url}") # Added for confirmation

    def _invoke(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Generic invoke: sends {"name": tool_name, "arguments": {...}} 
        to /invoke and returns the parsed JSON result.
        """
        payload = {
            "name": tool_name,
            "arguments": arguments
        }
        resp = requests.post(f"{self.base_url}/invoke", json=payload)
        resp.raise_for_status()
        body = resp.json()
        return body.get("result", body)

    def get_manifest(self) -> Dict[str, Any]:
        """Fetch the raw manifest.json so Jarvis can dynamically learn tools."""
        resp = requests.get(f"{self.base_url}/manifest")
        resp.raise_for_status()
        return resp.json()

    def list_jira_issues(self, jql: str) -> Any:
        return self._invoke("jira_list_issues", {"jql": jql})

    def create_jira_issue(self, project_key: str, summary: str, description: str="", issue_type: str="Task") -> Any:
        return self._invoke("jira_create_issue", {
            "project_key": project_key,
            "summary": summary,
            "description": description,
            "issue_type": issue_type
        })

    def list_calendar_events(self, start: str, end: str) -> Any:
        return self._invoke("outlook_list_events", {
            "start_datetime": start,
            "end_datetime": end
        })

    def create_calendar_event(self, subject: str, start: str, end: str, attendees: list[str]=[]) -> Any:
        return self._invoke("outlook_create_event", {
            "subject": subject,
            "start_datetime": start,
            "end_datetime": end,
            "attendees": attendees
        })

    def list_emails(self, folder: str, top: int = 5) -> Any:
        return self._invoke("outlook_list_messages", {"folder": folder, "top": top})

    def send_email(self, to: list[str], subject: str, body: str) -> Any:
        return self._invoke("outlook_send_message", {
            "to": to, "subject": subject, "body": body
        }) 