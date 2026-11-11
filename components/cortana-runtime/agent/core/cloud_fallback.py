"""Cloud inference is unavailable until payload-bound consent is implemented.

Legacy provider credentials may remain in .env, but cannot enable transmission.
"""
class CloudFallbackNotConfigured(Exception):
    pass


def is_configured() -> bool:
    return False


async def call_cloud_fallback(client, messages, tools=None):
    raise CloudFallbackNotConfigured(
        'Cloud inference is disabled for this milestone. No information was uploaded.'
    )
