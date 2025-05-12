"""
Test Script for AutoGen Workflow

This script can be run directly to test the AutoGen functionality without going through the API.
It simulates a simple research workflow.

Example usage:
python -m app.autogen.test_workflow
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add parent directory to path to allow imports
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import our AutoGen modules
from app.autogen.agent_factory import (
    create_assistant,
    create_user_proxy,
    create_group_chat,
    create_group_chat_manager
)

async def test_simple_chat():
    """Test a simple chat between two agents."""
    logger.info("Testing simple chat between two agents")
    
    # Create a simple assistant
    assistant = create_assistant(
        name="SimpleAssistant",
        system_message="You are a helpful assistant. Answer questions concisely and accurately.",
        llm_config={
            "config_list": [
                {
                    "model": "gpt-3.5-turbo",
                    "api_key": os.environ.get("OPENAI_API_KEY", "your-api-key-here")
                }
            ],
            "temperature": 0.7
        }
    )
    
    # Create a user proxy
    user_proxy = create_user_proxy(
        name="UserProxy",
        human_input_mode="NEVER",  # No human input for this test
    )
    
    # Initialize the chat
    test_message = "What are the key benefits of using multi-agent systems with LLMs?"
    logger.info(f"Starting chat with message: {test_message}")
    
    await user_proxy.a_initiate_chat(
        assistant,
        message=test_message
    )
    
    # Display the results
    logger.info("Chat completed!")
    logger.info("--- Chat History ---")
    for i, message in enumerate(user_proxy.chat_messages[assistant]):
        logger.info(f"[{i}] {message['role']}: {message['content']}")
    
    return user_proxy.chat_messages[assistant]

async def test_group_chat():
    """Test a group chat with multiple specialized agents."""
    logger.info("Testing group chat with multiple agents")
    
    # Basic LLM config
    llm_config = {
        "config_list": [
            {
                "model": "gpt-3.5-turbo",
                "api_key": os.environ.get("OPENAI_API_KEY", "your-api-key-here")
            }
        ],
        "temperature": 0.7
    }
    
    # Create specialized agents
    researcher = create_assistant(
        name="Researcher",
        system_message="You are a thorough researcher who provides detailed information on topics.",
        llm_config=llm_config
    )
    
    critic = create_assistant(
        name="Critic",
        system_message="You evaluate information critically, pointing out gaps and biases.",
        llm_config=llm_config
    )
    
    user_proxy = create_user_proxy(
        name="User",
        human_input_mode="NEVER",  # No human input for this test
    )
    
    # Set up the group chat
    groupchat = create_group_chat(
        agents=[user_proxy, researcher, critic],
        messages=[],
        max_round=4  # Limit rounds to keep test short
    )
    
    # Create the manager
    manager = create_group_chat_manager(
        groupchat=groupchat,
        llm_config=llm_config
    )
    
    # Start the conversation
    test_message = "What are the advantages and limitations of multi-agent frameworks like AutoGen?"
    logger.info(f"Starting group chat with message: {test_message}")
    
    await user_proxy.a_initiate_chat(
        manager,
        message=test_message,
    )
    
    # Display the results
    logger.info("Group chat completed!")
    logger.info("--- Group Chat History ---")
    for i, message in enumerate(groupchat.messages):
        if isinstance(message, dict):
            logger.info(f"[{i}] {message.get('name', 'Unknown')}: {message.get('content', 'No content')}")
    
    return groupchat.messages

async def main():
    """Main test function."""
    logger.info("Starting AutoGen test workflow")
    
    # Check if API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY environment variable not set. Set it or modify this script with your API key.")
    
    # Test simple chat
    logger.info("\n--- SIMPLE CHAT TEST ---")
    try:
        chat_messages = await test_simple_chat()
        logger.info(f"Simple chat test completed with {len(chat_messages)} messages")
    except Exception as e:
        logger.error(f"Simple chat test failed: {str(e)}", exc_info=True)
    
    # Test group chat
    logger.info("\n--- GROUP CHAT TEST ---")
    try:
        group_messages = await test_group_chat()
        logger.info(f"Group chat test completed with {len(group_messages)} messages")
    except Exception as e:
        logger.error(f"Group chat test failed: {str(e)}", exc_info=True)
    
    logger.info("All tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 