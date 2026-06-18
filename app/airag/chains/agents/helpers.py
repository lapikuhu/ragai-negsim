import json
from typing import Any
from langchain_core.messages import BaseMessage

### ------------------ GENERIC HELPERS FOR AGENTS ------------------ ###

CUSTOM_PROMPT_EXTENSION_HEADER = "CUSTOM PROMPT EXTENSION"


def json_dumps(value: Any) -> str:
	"""
	Serialize prompt values compactly while tolerating LangChain objects.
	Αrgs:
		value: The value to serialize, which may include LangChain objects or 
			other complex types.
	Returns:
		A JSON string representation of the value, with non-serializable 
			objects converted to strings.
	"""
	return json.dumps(value, default=str, ensure_ascii=False, indent=2)


def flatten_message_metadata(metadata: Any) -> dict[str, Any]:
	"""
	Flatten repeated metadata wrappers introduced by message round-tripping.
	Args:
		metadata: The metadata object to flatten, which may be nested.
	Returns:
		A flattened dictionary containing the metadata, with nested "metadata"
	"""
	if not isinstance(metadata, dict):
		return {}

	flattened: dict[str, Any] = {}
	current: Any = metadata
	while isinstance(current, dict):
		for key, value in current.items():
			if key != "metadata":
				flattened[key] = value
		current = current.get("metadata")
	return flattened


def append_missing_context_sections(
	prompt: str,
	template: str,
	sections: list[tuple[str, str, Any]],
) -> str:
	"""
	Append only the safe context sections omitted by a custom template.
	Args:
        prompt: The original prompt string.
        template: The custom template string.
        sections: A list of tuples containing placeholder, label, and 
			value for each context section.
    Returns:
        The prompt string with the missing context sections appended.
	"""
	appended = []
	for placeholder, label, value in sections:
		if placeholder not in template and value:
			appended.append(f"{label}\n{json_dumps(value)}")
	if not appended:
		return prompt
	return "\n\n".join([prompt, *appended])


def render_prompt_template(template: str, replacements: dict[str, Any]) -> str:
	"""
	Render a prompt template by replacing known placeholders.
	Args:
		template: The prompt template to render.
		replacements: Placeholder-to-value mappings.
	Returns:
		The rendered prompt template.
	"""
	prompt = template
	for placeholder, value in replacements.items():
		prompt = prompt.replace(placeholder, str(value))
	return prompt


def append_custom_prompt_extension(
	prompt: str,
	prompt_template: str | None,
	replacements: dict[str, Any],
) -> str:
	"""
	Append a rendered custom registry prompt without replacing the base prompt.
	Args:
		prompt: The rendered built-in prompt.
		prompt_template: Optional custom extension template.
		replacements: Placeholder-to-value mappings.
	Returns:
		The prompt with the custom extension appended, if present.
	"""
	if not prompt_template or not prompt_template.strip():
		return prompt

	extension = render_prompt_template(prompt_template, replacements).strip()
	if not extension:
		return prompt

	return "\n\n".join([prompt, CUSTOM_PROMPT_EXTENSION_HEADER, extension])


def format_messages(messages: list[Any] | None) -> str:
	"""
	Format messages for inclusion in the coach prompt, handling LangChain 
	message objects gracefully.
	Args:
        messages: A list of messages, which may include LangChain BaseMessage 
			objects or plain dicts.
    Returns:
        A string representation of the messages suitable for inclusion in 
		the coach prompt.
	"""
	if not messages:
		return "[]"

	formatted_messages = []
	for message in messages:
		if isinstance(message, BaseMessage):
			formatted: dict[str, Any] = {
				"type": message.type,
				"content": message.content,
			}
			if message.name:
				formatted["name"] = message.name
			if message.additional_kwargs:
				metadata = flatten_message_metadata(message.additional_kwargs)
				formatted.update(
					{
						key: value
						for key, value in message.additional_kwargs.items()
						if key != "metadata"
					}
				)
				if metadata:
					formatted["metadata"] = metadata
			formatted_messages.append(formatted)
		else:
			if isinstance(message, dict) and isinstance(message.get("metadata"), dict):
				formatted_messages.append(
					{
						**message,
						"metadata": flatten_message_metadata(message["metadata"]),
					}
				)
			else:
				formatted_messages.append(message)

	return json_dumps(formatted_messages)
