import json
from .privacy import redact_payload

def render(meta, data, options):
    safe_data = redact_payload(data, options)
    payload = {
        'generated_at': meta.get('generated_at'),
        'machine': meta.get('machine'),
        'sections': safe_data,
    }
    return json.dumps(payload, indent=2, default=str)


