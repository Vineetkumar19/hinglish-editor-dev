"""Move only Cortana's unused legacy cloud key to DPAPI, without transmitting it."""
import os
import re
import sys
from pathlib import Path
from uuid import uuid4
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root/'agent'),str(root)]
from core.config import settings
from core import secret_store


def main():
    source = root/'agent/.env'
    if not source.exists():
        print('No Cortana environment file to migrate.')
        return
    text = source.read_text(encoding='utf-8')
    pattern = re.compile(r'^\s*CORTANA_CLOUD_FALLBACK_API_KEY\s*=.*$',re.M)
    if not pattern.search(text) or not settings.cloud_fallback_api_key:
        print('No populated legacy credential found in the Cortana environment file.')
        return
    # Preserve the exact parsed value encrypted before removing plaintext.
    name='legacy.cloud_fallback_api_key'
    secret_store.save(name,settings.cloud_fallback_api_key)
    if secret_store.read(name) != settings.cloud_fallback_api_key:
        raise RuntimeError('Encrypted value did not round-trip; environment file was preserved.')
    replacement=pattern.sub('# Legacy cloud key preserved in the user-bound Cortana DPAPI vault.',text)
    temporary=source.with_name('.env.'+uuid4().hex+'.tmp')
    try:
        temporary.write_text(replacement,encoding='utf-8')
        os.replace(temporary,source)
    finally:
        temporary.unlink(missing_ok=True)
    print('Legacy credential encrypted and verified; plaintext entry removed. No cloud call or account change.')


if __name__ == '__main__':
    main()
