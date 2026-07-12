from __future__ import annotations

import pytest

from dolores_subnet.endpoints import EndpointPolicyError
from scripts import testnet_status


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--network", "test"],
        ["--netuid", "523"],
    ],
)
def test_status_requires_explicit_network_and_netuid(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        testnet_status.main(argv)
    assert exc_info.value.code == 2


@pytest.mark.parametrize(
    "argv",
    [
        ["--network", "test", "--netuid", "1"],
        ["--network", "ws://127.0.0.1:9944", "--netuid", "523"],
    ],
)
def test_status_rejects_any_non_cohort_target_before_snapshot(
    argv: list[str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        testnet_status,
        "snapshot",
        lambda *args, **kwargs: pytest.fail("snapshot must not run for an invalid target"),
    )

    with pytest.raises(EndpointPolicyError, match="network=test netuid=523"):
        testnet_status.main(argv)


def test_status_accepts_explicit_cohort_target_without_defaults(
    tmp_path,
    monkeypatch,
) -> None:
    calls: list[tuple[str, int, int]] = []

    def fake_snapshot(network: str, netuid: int, validator_uid: int):  # noqa: ANN202
        calls.append((network, netuid, validator_uid))
        return {"block": 123, "read_at_utc": "now", "neurons": []}

    monkeypatch.setattr(testnet_status, "snapshot", fake_snapshot)
    monkeypatch.setattr(testnet_status, "render_markdown", lambda snap: "status\n")

    result = testnet_status.main(
        [
            "--network",
            "test",
            "--netuid",
            "523",
            "--validator-uid",
            "0",
            "--out",
            str(tmp_path),
        ]
    )

    assert result == 0
    assert calls == [("test", 523, 0)]
    assert (tmp_path / "status_123.json").is_file()
    assert (tmp_path / "status_123.md").read_text(encoding="utf-8") == "status\n"
