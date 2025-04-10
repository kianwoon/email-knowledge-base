import json
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI

from app.config import settings
from app.models.email import EmailContent, EmailAnalysis, SensitivityLevel, Department, PIIType
from app.models.user import User # Assuming User model is here
# Import RAG components
from app.services.embedder import create_embedding, search_qdrant_knowledge


# Initialize OpenAI client
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def analyze_email_content(email: EmailContent) -> EmailAnalysis:
    """
    Analyze email content using ChatGPT-4o mini to extract knowledge, tags, and detect PII
    """
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
        print(f"Error analyzing email: {str(e)}")
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


# Updated function to accept user email for collection targeting
async def generate_openai_rag_response(
    message: str, 
    user: User, # Add user parameter
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Generates a chat response using RAG, targeting the user's specific embedding collection.
    # ... (rest of docstring) ...
    """
    try:
        # 1. Create embedding for the user message
        print(f"Creating embedding for message: '{message[:50]}...' ")
        query_embedding = await create_embedding(message)
        print("Embedding created.")

        # 2. Determine user-specific collection name for RAG and search
        sanitized_email = user.email.replace('@', '_').replace('.', '_')
        # *** CORRECTED: Use _knowledge_base for RAG search ***
        collection_to_search = f"{sanitized_email}_knowledge_base" 
        
        print(f"Searching RAG collection '{collection_to_search}' for relevant context for user {user.email}...")
        search_results = await search_qdrant_knowledge(
            query_embedding=query_embedding, 
            limit=3, 
            collection_name=collection_to_search # Pass the RAG collection name
        )
        print(f"Found {len(search_results)} context documents from RAG collection.")

        # 3. Format context and augment prompt
        context_str = ""
        if search_results:
            context_str += "Relevant Context From Knowledge Base:\n---\n"
            for i, result in enumerate(search_results):
                # Ensure 'raw_text' is the correct key in the _knowledge_base payload
                payload_text = result.get('payload', {}).get('raw_text', '') 
                context_str += f"Context {i+1} (Score: {result.get('score'):.4f}):\n{payload_text}\n---\n"
            context_str += "End of Context\n\n"
        else:
            context_str = "No relevant context found in the knowledge base.\n\n"

        system_prompt = f"""You are a helpful AI assistant. Answer the user's question based *only* on the provided context from the knowledge base. If the context doesn't contain the answer, state that the information is not available in the knowledge base. Do not use prior knowledge outside the provided context.

{context_str}User Question: {message}

Answer:"""
        messages = []
        messages.append({"role": "system", "content": system_prompt})

        # 4. Call OpenAI
        print(f"Calling OpenAI model '{settings.LLM_MODEL}' with augmented prompt...")
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL, 
            messages=messages,
            temperature=0.1,
        )
        response_content = response.choices[0].message.content
        print("Received response from OpenAI.")
        return response_content if response_content else "Sorry, I couldn't generate a response based on the context."
    
    except Exception as e:
        print(f"Error during RAG generation for user {user.email}: {str(e)}")
        # Log the specific collection searched during the error
        collection_name_on_error = f"{user.email.replace('@', '_').replace('.', '_')}_knowledge_base"
        return f"Sorry, an error occurred while searching the '{collection_name_on_error}' knowledge base: {str(e)}"

# Keep the old simple chat function for now, or remove if replaced by RAG
# async def generate_openai_chat_response(message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> str:
#    ... (previous implementation) ...
