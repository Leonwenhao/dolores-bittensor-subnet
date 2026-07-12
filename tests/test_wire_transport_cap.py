from __future__ import annotations

import asyncio

import pytest

from dolores_subnet.wire import TransportResponseTooLarge, _bounded_response_json


class FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.iterated = False

    async def iter_chunked(self, size: int):  # noqa: ANN201
        assert size > 0
        self.iterated = True
        for chunk in self.chunks:
            yield chunk


class FakeResponse:
    def __init__(self, chunks: list[bytes], *, content_length: str | None = None) -> None:
        self.content = FakeContent(chunks)
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = content_length


def test_declared_oversize_response_is_rejected_before_body_read() -> None:
    response = FakeResponse([b'{}'], content_length="1048577")

    with pytest.raises(TransportResponseTooLarge, match="declared response"):
        asyncio.run(_bounded_response_json(response, max_bytes=1024 * 1024))
    assert response.content.iterated is False


def test_chunked_oversize_response_is_rejected_before_json_parse() -> None:
    response = FakeResponse([b'{"x":"', b"a" * 1024, b'"}'])

    with pytest.raises(TransportResponseTooLarge, match="streamed response"):
        asyncio.run(_bounded_response_json(response, max_bytes=128))
    assert response.content.iterated is True


def test_bounded_response_accepts_small_json_object() -> None:
    response = FakeResponse([b'{"ok":', b"true}"])

    assert asyncio.run(_bounded_response_json(response, max_bytes=128)) == {"ok": True}
