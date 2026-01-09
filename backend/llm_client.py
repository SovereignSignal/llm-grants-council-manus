"""LLM client for making API requests to OpenAI-compatible endpoints."""

import os
import json
import httpx
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

# Initialize client - uses pre-configured base URL and API key
client = AsyncOpenAI()


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    timeout: float = 120.0,
    json_mode: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Query a single model via OpenAI-compatible API.

    Args:
        model: Model identifier (e.g., "gpt-4.1-mini")
        messages: List of message dicts with 'role' and 'content'
        temperature: Sampling temperature
        timeout: Request timeout in seconds
        json_mode: Whether to request JSON output

    Returns:
        Response dict with 'content', or None if failed
    """
    try:
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,
        }
        
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = await client.chat.completions.create(**kwargs)
        
        return {
            'content': response.choices[0].message.content,
            'model': model,
            'usage': {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
            }
        }

    except Exception as e:
        print(f"Error querying model {model}: {e}")
        return None


async def query_models_parallel(
    models_with_messages: List[Dict[str, Any]],
    temperature: float = 0.7,
    json_mode: bool = False
) -> Dict[str, Optional[Dict[str, Any]]]:
    """
    Query multiple models in parallel with potentially different messages.

    Args:
        models_with_messages: List of dicts with 'model', 'messages', and optional 'agent_id'
        temperature: Sampling temperature
        json_mode: Whether to request JSON output

    Returns:
        Dict mapping agent_id (or model) to response dict (or None if failed)
    """
    import asyncio

    async def query_single(item):
        agent_id = item.get('agent_id', item['model'])
        result = await query_model(
            item['model'],
            item['messages'],
            temperature=temperature,
            json_mode=json_mode
        )
        return agent_id, result

    tasks = [query_single(item) for item in models_with_messages]
    results = await asyncio.gather(*tasks)
    
    return {agent_id: result for agent_id, result in results}


async def query_with_structured_output(
    model: str,
    messages: List[Dict[str, str]],
    output_schema: Dict[str, str],
    temperature: float = 0.7
) -> Optional[Dict[str, Any]]:
    """
    Query model and parse structured JSON output.

    Args:
        model: Model identifier
        messages: List of message dicts
        output_schema: Expected output fields and types
        temperature: Sampling temperature

    Returns:
        Parsed JSON response or None if failed
    """
    # Add schema instruction to system message
    schema_instruction = f"""
You must respond with valid JSON matching this schema:
{json.dumps(output_schema, indent=2)}

Respond ONLY with the JSON object, no additional text."""

    enhanced_messages = messages.copy()
    if enhanced_messages and enhanced_messages[0]['role'] == 'system':
        enhanced_messages[0]['content'] += "\n\n" + schema_instruction
    else:
        enhanced_messages.insert(0, {
            'role': 'system',
            'content': schema_instruction
        })

    response = await query_model(
        model,
        enhanced_messages,
        temperature=temperature,
        json_mode=True
    )

    if response is None:
        return None

    try:
        content = response['content']
        # Handle potential markdown code blocks
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        
        parsed = json.loads(content.strip())
        return {
            'data': parsed,
            'model': response['model'],
            'usage': response['usage']
        }
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Raw content: {response['content'][:500]}")
        return None
