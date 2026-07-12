from __future__ import annotations

import asyncio
from types import SimpleNamespace

from dolores_subnet.miner_cli import (
    RequestAdmissionMiddleware,
    TokenBucketLimiter,
    attach_miner_axon,
    validator_blacklist,
)


def test_miner_attach_layers_cohort_verifier_over_sdk_default() -> None:
    captured = {}

    class FakeAxon:
        def attach(self, **kwargs):
            captured.update(kwargs)
            return self

    forward = object()
    blacklist = object()
    assert attach_miner_axon(FakeAxon(), forward=forward, blacklist=blacklist)

    assert captured["forward_fn"] is forward
    assert captured["blacklist_fn"] is blacklist
    assert callable(captured["verify_fn"])


def test_controlled_cohort_blacklist_allows_only_configured_validator() -> None:
    policy = validator_blacklist(
        allowed_hotkeys=frozenset({"validator-a"}),
        allow_any_signed=False,
    )

    assert policy(
        SimpleNamespace(
            dendrite=SimpleNamespace(hotkey="validator-a"),
            request_id="a" * 32,
        )
    ) == (
        False,
        "",
    )
    rejected, reason = policy(
        SimpleNamespace(
            dendrite=SimpleNamespace(hotkey="validator-b"),
            request_id="b" * 32,
        )
    )
    assert rejected is True
    assert "not allowlisted" in reason


def test_local_rehearsal_can_explicitly_allow_any_signed_validator() -> None:
    policy = validator_blacklist(allowed_hotkeys=frozenset(), allow_any_signed=True)

    assert policy(
        SimpleNamespace(
            dendrite=SimpleNamespace(hotkey="validator-b"),
            request_id="b" * 32,
        )
    ) == (
        False,
        "",
    )
    assert policy(
        SimpleNamespace(dendrite=SimpleNamespace(hotkey=""), request_id="c" * 32)
    )[0] is True


def test_token_bucket_enforces_burst_and_refills() -> None:
    limiter = TokenBucketLimiter(burst=2, rate_per_second=1.0)

    assert limiter.allow("validator", now=10.0)
    assert limiter.allow("validator", now=10.0)
    assert not limiter.allow("validator", now=10.0)
    assert limiter.allow("validator", now=11.0)


def test_request_admission_rejects_chunked_body_before_downstream_parse() -> None:
    downstream_called = False

    async def downstream(scope, receive, send):  # noqa: ANN001
        nonlocal downstream_called
        del scope, receive, send
        downstream_called = True

    middleware = RequestAdmissionMiddleware(
        downstream,
        max_bytes=8,
        burst=10,
        rate_per_second=1.0,
    )
    messages = iter(
        [
            {"type": "http.request", "body": b"12345", "more_body": True},
            {"type": "http.request", "body": b"67890", "more_body": False},
        ]
    )
    sent = []

    async def receive():
        return next(messages)

    async def send(message):  # noqa: ANN001
        sent.append(message)

    asyncio.run(
        middleware(
            {"type": "http", "client": ("203.0.113.1", 1234), "headers": []},
            receive,
            send,
        )
    )

    assert downstream_called is False
    assert sent[0]["status"] == 413
