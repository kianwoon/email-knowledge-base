# Placeholder for jarvis_app.py
from backend.app.services.jarvis_mcp_client import MCPClient
import requests # For requests.exceptions.HTTPError
import json     # For pretty printing the output

def format_jira_issues_reply(issues: list) -> str:
    """Formats a list of Jira issues into a user-friendly string."""
    if not issues:
        return "No open Jira issues found matching your criteria."

    reply = "Okay, here are the open Jira issues I found:\n"
    for issue in issues:
        key = issue.get("key", "N/A")
        fields = issue.get("fields", {})
        summary = fields.get("summary", "No summary")
        status_info = fields.get("status", {})
        status_name = status_info.get("name", "No status")
        assignee_info = fields.get("assignee")
        assignee_name = "Unassigned"
        if assignee_info and isinstance(assignee_info, dict):
            assignee_name = assignee_info.get("displayName", "Unassigned")

        reply += f"  - [{key}] {summary} (Status: {status_name}, Assignee: {assignee_name})\n"
    return reply

def handle_list_jira_issues(client: MCPClient):
    print("\n--- List Jira Issues ---")
    jql_query = input("Enter JQL query (e.g., project = BYS AND status = \"To Do\"): ")
    if not jql_query:
        print("JQL query cannot be empty.")
        return

    try:
        issues_result = client.list_jira_issues(jql=jql_query)
        print("\nRaw response from MCP server for Jira issues:")
        try:
            print(json.dumps(issues_result, indent=2))
        except TypeError:
            print(issues_result)

        issues_data = []
        if isinstance(issues_result, list):
            issues_data = issues_result
        elif isinstance(issues_result, dict) and "issues" in issues_result and isinstance(issues_result["issues"], list):
            issues_data = issues_result["issues"]
        elif isinstance(issues_result, dict):
            print(f"Received a dictionary, but couldn't find an 'issues' list. Content: {issues_result}")
        else:
            print(f"Unexpected format for issues_result. Expected a list or a dict. Got: {type(issues_result)}")

        reply = format_jira_issues_reply(issues_data)
        print(f"\nJarvis: {reply}")
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}")
        if e.response is not None: print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def handle_send_email(client: MCPClient):
    print("\n--- Send Email ---")
    to_str = input("To (comma-separated emails): ")
    subject = input("Subject: ")
    body = input("Body: ")

    if not to_str or not subject or not body:
        print("To, Subject, and Body are required.")
        return
    
    to_list = [email.strip() for email in to_str.split(',')]

    try:
        result = client.send_email(to=to_list, subject=subject, body=body)
        print("\nRaw response from MCP server for send email:")
        try:
            print(json.dumps(result, indent=2))
        except TypeError:
            print(result)
        print("\nJarvis: Email sent successfully (or request submitted).") # MCP server handles actual sending
    except requests.exceptions.HTTPError as e:
        print(f"Error sending email: {e}")
        if e.response is not None: print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def handle_create_event(client: MCPClient):
    print("\n--- Create Calendar Event ---")
    subject = input("Event Subject: ")
    start_datetime = input("Start (YYYY-MM-DDTHH:MM:SS): ") # e.g., 2024-08-15T10:00:00
    end_datetime = input("End (YYYY-MM-DDTHH:MM:SS): ")     # e.g., 2024-08-15T11:00:00
    attendees_str = input("Attendees (comma-separated emails, optional): ")

    if not subject or not start_datetime or not end_datetime:
        print("Subject, Start, and End times are required.")
        return

    attendees_list = [email.strip() for email in attendees_str.split(',')] if attendees_str else []

    try:
        result = client.create_calendar_event(subject=subject, start=start_datetime, end=end_datetime, attendees=attendees_list)
        print("\nRaw response from MCP server for create event:")
        try:
            print(json.dumps(result, indent=2))
        except TypeError:
            print(result)
        print("\nJarvis: Calendar event created successfully (or request submitted).")
    except requests.exceptions.HTTPError as e:
        print(f"Error creating event: {e}")
        if e.response is not None: print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def main():
    print("Jarvis app started.")
    mcp_client = MCPClient()
    print("MCPClient initialized.")

    while True:
        print("\nJarvis: What would you like to do?")
        print("  1: List Jira Issues")
        print("  2: Send Email")
        print("  3: Create Calendar Event")
        print("  exit: Exit Jarvis")
        choice = input("> ").strip().lower()

        if choice == '1' or choice == 'list jira':
            handle_list_jira_issues(mcp_client)
        elif choice == '2' or choice == 'send email':
            handle_send_email(mcp_client)
        elif choice == '3' or choice == 'create event':
            handle_create_event(mcp_client)
        elif choice == 'exit':
            print("Jarvis: Goodbye!")
            break
        else:
            print("Jarvis: Sorry, I didn't understand that. Please choose an option from the list.")

if __name__ == "__main__":
    main() 