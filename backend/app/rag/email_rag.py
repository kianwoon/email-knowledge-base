import logging
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.services.milvus import count_tokens, get_tokenizer_model_for_chat_model
from app.services.duckdb import query_iceberg_emails_duckdb
from app.services.client_factory import get_system_client

# Set up logger for this module
logger = logging.getLogger(__name__)
# Configure logger level based on LOG_LEVEL env var
logger.setLevel(getattr(logging, settings.LOG_LEVEL, logging.INFO))

async def analyze_email_content(email: EmailContent, client: AsyncOpenAI = None) -> EmailAnalysis:
    """
    Analyze email content using ChatGPT-4o mini to extract knowledge, tags, and detect PII
    """
    # Use provided client or fallback to system client
    if not client:
        client = get_system_client()
    
    # Prepare the content for analysis
    content_to_analyze = f"""
Subject: {email.subject}
From: {email.sender} <{email.sender_email}>
Date: {email.received_date.isoformat()}
Body:
{email.body}
    """
    
    # Add attachment content if available
    if email.attachments:
        content_to_analyze += "\n\nAttachments:"
        for attachment in email.attachments:
            if attachment.content:
                content_to_analyze += f"\n\n{attachment.name}:\n{attachment.content}"
    
    # Create the prompt for the LLM
    system_prompt = """
You are an AI assistant that analyzes emails to extract knowledge and detect sensitive information.
Analyze the provided email and extract the following information:
1. Sensitivity level (low, medium, high, critical)
2. Department the knowledge belongs to (general, engineering, product, marketing, sales, finance, hr, legal, other)
3. Relevant tags for categorizing the content (3-5 tags)
4. Whether the email contains private/confidential information (true/false)
5. Types of personal identifiable information (PII) detected (name, email, phone, address, ssn, passport, credit_card, bank_account, date_of_birth, salary, other)
6. Recommended action (store or exclude)
7. Brief summary of the content (1-2 sentences)
8. Key knowledge points extracted (3-5 bullet points)

Respond with a JSON object containing these fields.
"""
    
    user_prompt = f"""
Please analyze this email content:

{content_to_analyze}

Return a JSON object with the following fields:
- sensitivity: The sensitivity level (low, medium, high, critical)
- department: The department this knowledge belongs to (general, engineering, product, marketing, sales, finance, hr, legal, other)
- tags: Array of relevant tags for categorizing this content (3-5 tags)
- is_private: Boolean indicating if this contains private/confidential information
- pii_detected: Array of PII types detected (empty array if none)
- recommended_action: "store" or "exclude"
- summary: Brief summary of the content
- key_points: Array of key knowledge points extracted
"""
    
    try:
        # Call OpenAI API
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        
        # Create EmailAnalysis object
        analysis = EmailAnalysis(
            sensitivity=result.get("sensitivity", "low"),
            department=result.get("department", "general"),
            tags=result.get("tags", []),
            is_private=result.get("is_private", False),
            pii_detected=result.get("pii_detected", []),
            recommended_action=result.get("recommended_action", "exclude" if result.get("is_private", False) else "store"),
            summary=result.get("summary", ""),
            key_points=result.get("key_points", [])
        )
        
        return analysis
    
    except Exception as e:
        # Log the error and return a default analysis
        logger.error(f"Error analyzing email: {str(e)}", exc_info=True)
        return EmailAnalysis(
            sensitivity=SensitivityLevel.LOW,
            department=Department.GENERAL,
            tags=["error", "processing_failed"],
            is_private=True,  # Default to private if analysis fails
            pii_detected=[],
            recommended_action="exclude",
            summary="Analysis failed. Please review manually.",
            key_points=["Analysis failed due to an error."]
        )

async def summarize_email_batch(
    email_batch: List[Dict[str, Any]], 
    original_query: str,
    batch_llm_client: AsyncOpenAI, 
    batch_model_name: str,         
    max_chars_per_email: int = 1000, 
    batch_max_tokens_for_llm: int = 1024 
) -> str:
    """Summarizes a batch of emails focusing on relevance to the original query."""
    logger.debug(f"Starting summary for batch of {len(email_batch)} emails, LLM max_tokens: {batch_max_tokens_for_llm}.")
    if not email_batch: return "" # Return empty string if batch is empty

    # Helper to truncate email body within the batch context
    def _truncate_email_body(text: str, max_len: int) -> str:
        text_str = str(text) if text is not None else ''
        if len(text_str) > max_len: return text_str[:max_len] + "... [TRUNCATED FOR SUMMARY]"; return text_str

    # Format the batch context
    batch_context_parts = []
    for i, email in enumerate(email_batch): 
        # Extract only essential fields for summarization
        sender = email.get('sender', 'Unknown Sender')
        subject = email.get('subject', 'No Subject')
        received_date = email.get('received_datetime_utc', 'Unknown Date')
        body_text = email.get('body_text', '')
        quoted_text = email.get('quoted_raw_text', '') 
        full_body = f"{body_text}\n\n--- Quoted Text ---\n{quoted_text}".strip()
        truncated_body = _truncate_email_body(full_body, max_chars_per_email)

        # Build the entry string incrementally
        entry_str = f"--- Email {i+1} ---\n"
        entry_str += f"From: {sender}\n"
        entry_str += f"Subject: {subject}\n"
        entry_str += f"Date: {received_date}\n"
        entry_str += f"Body:\n{truncated_body}\n"
        entry_str += f"--- End Email {i+1} ---"
        batch_context_parts.append(entry_str)
    batch_context_str = "\n\n".join(batch_context_parts)

    # Define the summarization prompt
    summary_system_prompt = (
        f"You are an expert summarizer. Your task is to read the following batch of emails and extract ALL key information, specific details, updates, developments, decisions, action items, figures, names, dates, or news that are **directly relevant** to the user's original query: \"{original_query}\".\n" \
        f"Your primary goal is to be **extremely thorough and detailed** for the given query. Do not omit any potentially relevant piece of information, even if it seems minor. Capture the nuances and specifics from the emails.\n" \
        f"Produce an **expansive and highly detailed summary** of all relevant points. Aim to utilize a significant portion of the available token limit for your response if the source material contains sufficient relevant detail. If the batch is rich in relevant information, your summary should reflect that richness in length and detail.\n" \
        f"IMPORTANT: When referencing dates, ALWAYS maintain the EXACT years as they appear in the source emails. Do NOT change years or assume current year. If an email from 2023 is referenced, use '2023' not the current year or any other year.\n" \
        f"For relative time expressions like 'last week', use the actual date range with correct years from the retrieved emails.\\n" \
        f"CRITICAL: If the emails contain information about multiple distinct entities, projects, or clients (e.g., UOB, OCBC), ensure your summary explicitly and accurately attributes details to the correct entity. Do not blend information or misattribute details between entities.\\n" \
        f"If, and only if, no relevant information is found, state that clearly. Otherwise, be exhaustive.\n" \
        f"Present the summary clearly. For multiple points, use detailed bullet points or paragraphs. Ensure all key facts, figures, and statements from the emails that pertain to the query are retained in your summary."
    )
    
    summary_user_prompt = f"Email Batch Context:\n{batch_context_str}"

    try:
        # Call the LLM for summarization
        response = await batch_llm_client.chat.completions.create(
            model=batch_model_name,
            messages=[
                {"role": "system", "content": summary_system_prompt},
                {"role": "user", "content": summary_user_prompt}
            ],
            temperature=0.4, # Increased temperature for potentially more detailed summaries
            max_tokens=batch_max_tokens_for_llm # Use the new parameter
        )
        summary = response.choices[0].message.content.strip()
        logger.debug(f"Batch summary generated (length {len(summary)}): {summary[:100]}...")
        return summary
    except Exception as e:
        logger.error(f"Error during email batch summarization LLM call: {e}", exc_info=True)
        return "Error summarizing this email batch." # Return error message

async def get_email_context(
    max_items: int, 
    max_chunk_chars: int,
    user_client: AsyncOpenAI, 
    search_params: dict, 
    user_email: str
) -> List[Dict[str, Any]]:
    """Retrieves email context by calling query_iceberg_emails_duckdb."""
    logger.debug(f"get_email_context called with params: {search_params}, limit: {max_items}")
    try:
        # Determine provider based on client type or add as parameter if needed
        # This assumes user_client is configured for a specific provider (OpenAI/Deepseek)
        # A more robust way might involve passing the provider string explicitly
        provider = "openai" # Default assumption, adjust if necessary
        if hasattr(user_client, 'base_url') and 'deepseek' in str(user_client.base_url):
            provider = "deepseek"
            
        email_results = await query_iceberg_emails_duckdb(
            user_email=user_email,
            sender_filter=search_params.get("sender_filter"),
            subject_filter=search_params.get("subject_filter"),
            start_date=search_params.get("start_date"),
            end_date=search_params.get("end_date"),
            search_terms=search_params.get("search_terms"),
            limit=max_items, # Pass the calculated limit
            user_client=user_client, # Pass the client
            provider=provider, # Pass determined provider
            token=None # Pass token if applicable/available
        )
        logger.info(f"get_email_context retrieved {len(email_results)} emails.")
        return email_results
    except Exception as e_iceberg:
        logger.error(f"Error calling query_iceberg_emails_duckdb within get_email_context: {e_iceberg}", exc_info=True)
        return [] # Return empty list on error

async def extract_email_search_parameters_for_iceberg(message: str, client: AsyncOpenAI, model: str) -> Dict[str, Any]:
    """Uses LLM to extract structured search parameters for querying emails in Iceberg."""
    logger.info(f"extract_email_search_parameters_for_iceberg called for message: '{message[:100]}...'")
    
    # Use Singapore timezone for date calculations
    singapore_tz = ZoneInfo("Asia/Singapore")
    now_sg = datetime.now(singapore_tz)
    now_sg_iso = now_sg.isoformat()
    
    logger.info(f"Current Singapore time: {now_sg_iso}")
    
    # Helper to calculate past/future dates for examples, using Singapore timezone
    def calculate_example_date(days_offset: int, start_of_day: bool = False, end_of_day: bool = False) -> str:
        try:
            target_dt = now_sg + timedelta(days=days_offset)
            if start_of_day:
                target_dt = target_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            elif end_of_day:
                target_dt = target_dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            return target_dt.isoformat()
        except Exception as e_date_calc:
            logger.error(f"Error in calculate_example_date: {e_date_calc}")
            return f"[date_calc_error_offset_{days_offset}]"

    # Define example dates for the prompt using Singapore timezone
    example_dates = {
        "now_sg_iso": now_sg_iso,
        "today_start": calculate_example_date(0, start_of_day=True),
        "today_end": calculate_example_date(0, end_of_day=True),
        "yesterday_start": calculate_example_date(-1, start_of_day=True),
        "yesterday_end": calculate_example_date(-1, end_of_day=True),
        "last_3_days_start": calculate_example_date(-3, start_of_day=True),
        "last_7_days_start": calculate_example_date(-7, start_of_day=True),
        "tomorrow_start": calculate_example_date(1, start_of_day=True),
        "tomorrow_end": calculate_example_date(1, end_of_day=True),
        "next_7_days_end": calculate_example_date(7, end_of_day=True),
    }
    
    # Log the dates we're using
    logger.info(f"Today in Singapore: {example_dates['today_start'].split('T')[0]}")

    # Extract just the date portion for the template
    today_date = example_dates['today_start'].split('T')[0]

    extraction_prompt_template = (
        f"You are an expert parameter extractor for email searches. Current time in Asia/Singapore is {{now_sg_iso}}.\n"
        f"Analyze the user's message: \"{{message}}\"\n"
        f"Extract the following parameters for searching emails. If a parameter is not mentioned or cannot be inferred, use null.\n"
        f"  - sender: The name or email address of the sender.\n"
        f"  - subject: Specific keywords or phrases that MUST be in the email subject. If keywords are general search terms for body/subject, use 'search_terms' instead and leave subject null.\n"
        f"  - start_date_utc: The start date for the search in ISO format. Calculate from relative terms like 'today', 'yesterday', 'last week' using Singapore time zone (UTC+8). For 'today', use {{today_start}}; for 'yesterday', use {{yesterday_start}}. For general queries about events happening 'today' or 'by today', consider a recent window for when the arrangement email might have been sent (e.g., last 3 days).\n"
        f"  - end_date_utc: The end date for the search in ISO format. For 'today' or 'yesterday', this would be the end of that day. For 'today', use {{today_end}}; for 'yesterday', use {{yesterday_end}}. For ranges like 'last week', use current time.\n"
        f"  - search_terms: A list of general keywords or phrases (e.g., from the query that are not senders or direct subject lines) to search in email body or subject. If user mentions multiple terms like 'meeting OR interview', list them as [\"meeting\", \"interview\"].\n"
        f"Respond ONLY with a single JSON object containing these keys: \"sender\", \"subject\", \"start_date_utc\", \"end_date_utc\", \"search_terms\".\n"
        f"Examples (Current Singapore time is {{now_sg_iso}}):\n"
        f"  1. User: \"emails from jeff last week about the UOB project\" -> {{{{ \"sender\": \"jeff\", \"subject\": \"UOB project\", \"start_date_utc\": \"{{last_7_days_start}}\", \"end_date_utc\": \"{{now_sg_iso}}\", \"search_terms\": [\"UOB project\"]}}}})\n"
        f"  2. User: \"any meeting or interview arranged by today? \" -> {{{{ \"sender\": null, \"subject\": null, \"start_date_utc\": \"{{last_3_days_start}}\", \"end_date_utc\": \"{{today_end}}\", \"search_terms\": [\"meeting\", \"interview\"]}}}})\n"
        f"  3. User: \"show me emails from yesterday regarding customer feedback\" -> {{{{ \"sender\": null, \"subject\": \"customer feedback\", \"start_date_utc\": \"{{yesterday_start}}\", \"end_date_utc\": \"{{yesterday_end}}\", \"search_terms\": [\"customer feedback\"]}}}})\n"
        f"  4. User: \"any new emails on the Project X topic?\" (Implies recent, e.g. today) -> {{{{ \"sender\": null, \"subject\": null, \"start_date_utc\": \"{{today_start}}\", \"end_date_utc\": \"{{today_end}}\", \"search_terms\": [\"Project X\"]}}}})\n"
        f"  5. User: \"search for emails about 'launch plan' from alice next week\" -> {{{{ \"sender\": \"alice\", \"subject\": \"launch plan\", \"start_date_utc\": \"{{tomorrow_start}}\", \"end_date_utc\": \"{{next_7_days_end}}\", \"search_terms\": [\"launch plan\"]}}}})\n"
        f"IMPORTANT: Remember that 'today' refers to {today_date} in Singapore time.\n"
        f"JSON Response:\"\n"
    )
    
    final_extraction_prompt = extraction_prompt_template.format(message=message, **example_dates)
    
    messages = [
        {"role": "system", "content": "You are an expert at extracting structured search parameters from user queries for email searches. You must calculate dates accurately based on the Singapore timezone (UTC+8) and relative terms. Respond only with the specified JSON object."},
        {"role": "user", "content": final_extraction_prompt}
    ]
    
    extracted_params_str = ""
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        extracted_params_str = response.choices[0].message.content
        logger.info(f"Raw LLM output for params: {extracted_params_str}")
        raw_params = json.loads(extracted_params_str)
        
        # Validate and parse dates - convert to UTC for database queries
        start_date_obj, end_date_obj = None, None
        raw_start = raw_params.get("start_date_utc")
        raw_end = raw_params.get("end_date_utc")

        if raw_start:
            try: 
                # Parse date with timezone info preserved
                start_date_obj = datetime.fromisoformat(str(raw_start).replace('Z', '+00:00'))
                logger.info(f"Parsed start_date: {start_date_obj.isoformat()}")
            except (ValueError, TypeError): 
                logger.warning(f"Invalid start_date_utc from LLM: {raw_start}")
        if raw_end:
            try: 
                # Parse date with timezone info preserved
                end_date_obj = datetime.fromisoformat(str(raw_end).replace('Z', '+00:00'))
                logger.info(f"Parsed end_date: {end_date_obj.isoformat()}")
            except (ValueError, TypeError): 
                logger.warning(f"Invalid end_date_utc from LLM: {raw_end}")

        if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
            logger.warning(f"LLM returned start_date > end_date ({start_date_obj} > {end_date_obj}). Discarding dates.")
            start_date_obj, end_date_obj = None, None
            
        # Ensure search_terms is a list of strings
        search_terms_val = raw_params.get("search_terms")
        if not isinstance(search_terms_val, list) or not all(isinstance(st, str) for st in search_terms_val):
            logger.warning(f"LLM returned invalid search_terms: {search_terms_val}. Setting to empty list or using subject.")
            search_terms_val = [raw_params.get("subject")] if isinstance(raw_params.get("subject"), str) else []
            search_terms_val = [st for st in search_terms_val if st] # filter out None/empty from subject fallback
            
        return {
            "sender_filter": raw_params.get("sender") if isinstance(raw_params.get("sender"), str) else None,
            "subject_filter": raw_params.get("subject") if isinstance(raw_params.get("subject"), str) else None,
            "start_date": start_date_obj,
            "end_date": end_date_obj,
            "search_terms": search_terms_val
        }

    except json.JSONDecodeError as e_json:
        logger.error(f"JSONDecodeError: {e_json}. Raw LLM output: {extracted_params_str}")
    except Exception as e_param:
        logger.error(f"Unexpected error: {e_param}", exc_info=True)
    
    return {} # Return empty dict on error, so downstream uses defaults 