"""Connection failures only; unrelated OS/tool errors fail the gate."""

import errno


def connection_refusal(error):
    if isinstance(error, TimeoutError):
        return "connection-timeout"
    reasons = {
        errno.ECONNREFUSED: "connection-refused",
        errno.ENETUNREACH: "network-unreachable",
        errno.EHOSTUNREACH: "host-unreachable",
    }
    if isinstance(error, OSError) and error.errno in reasons:
        return reasons[error.errno]
    raise RuntimeError("Unexpected socket/tool error; network isolation unverified")


def download_refusal(navigation_error, failure):
    # ERR_FAILED alone is never proof. Require a real Download event and the
    # exact Playwright failure identifying the accept_downloads=False setting.
    expected = (
        "Pass 'accept_downloads=True' when you are creating your browser context."
    )
    if failure != expected or not any(
        marker in navigation_error
        for marker in (
            "Download is starting",
            "net::ERR_ABORTED",
            "net::ERR_FAILED",
        )
    ):
        raise RuntimeError("Unexpected download result; prerequisite unverified")
    return "accept-downloads-disabled"
