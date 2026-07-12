from __future__ import annotations

from types import SimpleNamespace

import pytest

from dolores_subnet.config import LOCALNET_ALT_NETWORK, LOCALNET_NETWORK, Mode
from dolores_subnet.endpoints import EndpointPolicyError
from scripts import preflight


@pytest.mark.parametrize(
    "argv",
    [
        ["--mode", "testnet"],
        ["--mode", "testnet", "--network", "test"],
        ["--mode", "testnet", "--netuid", "523"],
    ],
)
def test_testnet_preflight_rejects_implicit_target_before_config(
    argv: list[str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        preflight.SubnetConfig,
        "from_env",
        lambda **kwargs: pytest.fail("config must not be constructed"),
    )

    with pytest.raises(ValueError, match="explicit --network test --netuid 523"):
        preflight.main(argv)


@pytest.mark.parametrize(
    "argv",
    [
        ["--mode", "testnet", "--network", "test", "--netuid", "1"],
        [
            "--mode",
            "testnet",
            "--network",
            LOCALNET_NETWORK,
            "--netuid",
            "523",
        ],
    ],
)
def test_testnet_preflight_requires_exact_cohort_target_before_config(
    argv: list[str],
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        preflight.SubnetConfig,
        "from_env",
        lambda **kwargs: pytest.fail("config must not be constructed"),
    )

    with pytest.raises(EndpointPolicyError, match="network=test netuid=523"):
        preflight.main(argv)


def test_localnet_preflight_rejects_public_test_before_config(monkeypatch) -> None:
    monkeypatch.setattr(
        preflight.SubnetConfig,
        "from_env",
        lambda **kwargs: pytest.fail("config must not be constructed"),
    )

    with pytest.raises(ValueError, match="public network test is forbidden"):
        preflight.main(
            [
                "--mode",
                "localnet",
                "--network",
                "test",
                "--netuid",
                "2",
            ]
        )


@pytest.mark.parametrize("network", [LOCALNET_NETWORK, LOCALNET_ALT_NETWORK])
def test_legitimate_explicit_localnet_preflight_reaches_config(
    network: str,
    monkeypatch,
) -> None:
    calls: list[dict[str, object]] = []
    sentinel = SimpleNamespace(mode=Mode.LOCALNET)

    def fake_from_env(**kwargs):  # noqa: ANN202
        calls.append(kwargs)
        return sentinel

    monkeypatch.setattr(preflight.SubnetConfig, "from_env", fake_from_env)
    monkeypatch.setattr(preflight, "run_preflight", lambda cfg: int(cfg is not sentinel))

    assert (
        preflight.main(
            [
                "--mode",
                "localnet",
                "--network",
                network,
                "--netuid",
                "2",
            ]
        )
        == 0
    )
    assert calls == [
        {
            "mode": Mode.LOCALNET,
            "work_dir": None,
            "wallet_name": None,
            "wallet_hotkey": None,
            "network": network,
            "netuid": 2,
        }
    ]


def test_explicit_testnet_preflight_reaches_config(monkeypatch) -> None:
    sentinel = SimpleNamespace(mode=Mode.TESTNET)
    monkeypatch.setattr(
        preflight.SubnetConfig,
        "from_env",
        lambda **kwargs: sentinel,
    )
    monkeypatch.setattr(preflight, "run_preflight", lambda cfg: int(cfg is not sentinel))

    assert (
        preflight.main(
            [
                "--mode",
                "testnet",
                "--network",
                "test",
                "--netuid",
                "523",
            ]
        )
        == 0
    )
