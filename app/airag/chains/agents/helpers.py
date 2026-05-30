import json
from typing import Any
from langchain_core.messages import BaseMessage

### ------------------ GENERIC HELPERS FOR AGENTS ------------------ ###

def json_dumps(value: Any) -> str:
	"""Serialize prompt values compactly while tolerating LangChain objects."""
	return json.dumps(value, default=str, ensure_ascii=False, indent=2)


def format_messages(messages: list[Any] | None) -> str:
	"""
	Format messages for inclusion in the coach prompt, handling LangChain message objects gracefully.
	Args:
        messages: A list of messages, which may include LangChain BaseMessage objects or plain dicts.
    Returns:
        A string representation of the messages suitable for inclusion in the coach prompt.
	"""
	if not messages:
		return "[]"

	formatted_messages = []
	for message in messages:
		if isinstance(message, BaseMessage):
			formatted_messages.append(
				{
					"type": message.type,
					"content": message.content,
				}
			)
		else:
			formatted_messages.append(message)

	return json_dumps(formatted_messages)