import json
from autogen.io.websockets import IOWebsockets
import autogen

def on_connect(iostream: IOWebsockets):
    # Receive the initial message (should be JSON)
    initial_payload = iostream.input()
    if isinstance(initial_payload, str):
        data = json.loads(initial_payload)
    else:
        data = initial_payload

    message = data["message"]
    agents_config = data["agents"]
    model_id = data.get("model_id", "gpt-4")
    temperature = data.get("temperature", 0.7)

    # Instantiate agents
    agent_list = []
    for agent_cfg in agents_config:
        agent = autogen.ConversableAgent(
            name=agent_cfg["name"],
            system_message=agent_cfg["systemMessage"],
            llm_config={
                "model": model_id,
                "temperature": temperature,
                "stream": True,
            }
        )
        agent_list.append(agent)

    # Create user proxy
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        code_execution_config=False,
    )

    # Start the chat (streaming output to the websocket)
    user_proxy.initiate_chat(
        agent_list[0] if len(agent_list) == 1 else agent_list,
        message=message,
        iostream=iostream
    ) 