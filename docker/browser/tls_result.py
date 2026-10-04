"""Exact expected TLS causes; DNS/timeouts/tool errors are never TLS evidence."""


def tls_failure(message, engine):
    markers = {
        "chromium": {
            "authority": ("net::ERR_CERT_AUTHORITY_INVALID",),
            "name": ("net::ERR_CERT_COMMON_NAME_INVALID",),
        },
        "mediator": {
            "authority": (
                "self-signed certificate in certificate chain",
                "unable to verify the first certificate",
                "unable to get local issuer certificate",
            ),
            "name": ("Hostname/IP does not match certificate's altnames",),
        },
    }
    matches = [
        kind
        for kind, tokens in markers[engine].items()
        if any(token in message for token in tokens)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "Unexpected TLS/tool/connection result; prerequisite unverified"
        )
    return matches[0]
