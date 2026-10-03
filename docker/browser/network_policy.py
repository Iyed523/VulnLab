"""HTTP(S) request mediation for a dedicated, non-persistent lab context."""

from urllib.parse import urljoin, urlsplit


def origin(url):
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or "\\" in url
            or any(ord(character) < 33 for character in url)
        ):
            return None
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        return parsed.scheme, parsed.hostname, port
    except ValueError:
        return None


def permitted(url, allowed):
    candidate = origin(url)
    return candidate is not None and candidate in allowed


def redirect_target(current, location, allowed):
    target = urljoin(current, location)
    if not permitted(target, allowed):
        raise ValueError("Redirect destination is not authorized")
    return target


async def install_policy(context, allowed):
    """Never continue a response that could redirect beyond the allowed origins.

    Playwright routes do not intercept every redirected request. Fetch without
    automatic redirects, validate every hop and fulfill only the final response.
    This mediates HTTP(S), not all possible Chromium traffic or local access.
    """

    async def handle(route):
        url = route.request.url
        if not permitted(url, allowed):
            await route.abort("blockedbyclient")
            return
        method = route.request.method
        data = route.request.post_data_buffer
        for _ in range(10):
            response = await route.fetch(
                url=url, method=method, post_data=data, max_redirects=0, timeout=10000
            )
            try:
                if response.status not in {301, 302, 303, 307, 308}:
                    await route.fulfill(response=response)
                    return
                location = response.headers.get("location")
                if not location:
                    await route.abort("blockedbyclient")
                    return
                try:
                    url = redirect_target(url, location, allowed)
                except ValueError:
                    await route.abort("blockedbyclient")
                    return
                if response.status == 303 or (
                    response.status in {301, 302} and method == "POST"
                ):
                    method, data = "GET", None
            finally:
                await response.dispose()
        await route.abort("blockedbyclient")

    async def reject_socket(socket):
        await socket.close()

    await context.route("**/*", handle)
    await context.route_web_socket("**/*", reject_socket)
