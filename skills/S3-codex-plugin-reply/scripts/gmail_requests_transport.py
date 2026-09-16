"""Gmail discovery client backed by the proxy-aware requests transport."""

from __future__ import annotations

import httplib2
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class RequestsHttp:
    def __init__(self, credentials: Credentials) -> None:
        self.session = AuthorizedSession(credentials)

    def request(self, uri: str, method: str = "GET", body=None, headers=None, **kwargs):
        response = self.session.request(method, uri, data=body, headers=headers, timeout=60)
        wrapped = httplib2.Response(dict(response.headers))
        wrapped.status = response.status_code
        wrapped.reason = response.reason
        return wrapped, response.content


def build_gmail_service(credentials: Credentials):
    return build("gmail", "v1", http=RequestsHttp(credentials), cache_discovery=False)
