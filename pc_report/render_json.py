import json

from .privacy import redact_meta, redact_payload


def render(meta, data, options):
    meta = redact_meta(meta, options)
    payload = {
        'generated_at': meta.get('generated_at'),
        'machine': meta.get('machine'),
        'elevated': meta.get('elevated'),
        'nvc_version': meta.get('nvc_version'),
        'elapsed_by_section': meta.get('elapsed_by_section'),
        'sections': redact_payload(data, options),
    }
    return json.dumps(payload, indent=2, default=str)


