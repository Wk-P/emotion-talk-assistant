"""CA pinning for the one external TLS endpoint this backend talks to: the
OpenAI API.

This is defense-in-depth against CA-compromise events (e.g. the Oct 2026
eMudhra/emSign intermediate key leak) where a certificate forged by a
different, unrelated CA would otherwise still pass normal chain validation
because that CA is in the OS/Python trust store. Instead of trusting the
full system CA bundle, this builds an SSLContext that trusts *only* the
specific root that actually anchors api.openai.com's certificate (Google
Trust Services' "GTS Root R4", captured on 2026-10-27 via:

    openssl s_client -connect api.openai.com:443 -servername api.openai.com -showcerts

A forged certificate chaining through a compromised, unrelated CA will not
validate against this restricted trust store even if the OS trust store
would accept it.

If OpenAI rotates to a different issuing CA, requests will start failing
closed with a certificate verify error — update pinned_ca/openai_root.pem
with the new root rather than falling back to the system trust store.
"""

from __future__ import annotations

import ssl
from pathlib import Path

_PINNED_CA_DIR = Path(__file__).parent / "pinned_ca"


def pinned_context(ca_filename: str) -> ssl.SSLContext:
    """Build an SSLContext trusting only the given pinned CA file."""
    cafile = _PINNED_CA_DIR / ca_filename
    context = ssl.create_default_context(cafile=str(cafile))
    # The pinned file holds an intermediate CA cert, not a self-signed root,
    # so OpenSSL needs explicit permission to treat it as a trust anchor
    # rather than continuing to chase an issuer we deliberately did not pin.
    context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    return context


def openai_ssl_context() -> ssl.SSLContext:
    return pinned_context("openai_root.pem")
