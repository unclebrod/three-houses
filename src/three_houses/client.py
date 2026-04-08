"""Client class for fetching data."""

import httpx

from three_houses.log import logger


def log_request(request: httpx.Request) -> None:
    """Log when requests are made by the client.

    Args:
        request: httpx Request object.
    """
    logger.info(f"Request: {request.method} {request.url}")


def log_response(response: httpx.Response) -> None:
    """Log when responses are received by the client.

    Args:
        response: httpx Response object.
    """
    request = response.request
    logger.info(
        f"Response: {request.method} {request.url} - "
        f"Status Code: {response.status_code}"
    )
    response.raise_for_status()  # Raise an exception for HTTP errors


class Client(httpx.Client):
    """HTTP client wrapper around httpx.Client with custom base settings."""

    def __init__(self, **kwargs) -> None:
        """Initialize the Client."""
        super().__init__(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0),
            transport=httpx.HTTPTransport(retries=3),
            event_hooks={
                "request": [log_request],
                "response": [log_response],
            },
            **kwargs,
        )
