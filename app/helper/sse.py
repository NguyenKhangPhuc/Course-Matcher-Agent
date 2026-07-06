import json

def sse(event_type: str, data) -> str:
    """Format a single Server-Sent Event JSON chunk."""
    return f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"