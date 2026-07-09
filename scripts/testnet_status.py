"""Read-only public-testnet status for the Dolores subnet.

Shows per-uid state (stake, permit, active, axon, updated, incentive,
emission), the raw weights row for the validator, and the current block.
Saves JSON + Markdown evidence under work/testnet_status/.

Read-only by construction: btcli subprocesses for bulk state (process-
isolated, cannot hang this process) plus one bounded-timeout SDK query for
the raw weights row (reported as "unavailable" on timeout). The network is
forced through the repo allowlist — mainnet is refused before any call.

Usage:
    python scripts/testnet_status.py                # netuid 523, network test
    python scripts/testnet_status.py --watch 20     # snapshot every 20 min
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from dolores_subnet.config import assert_safe_network  # noqa: E402

BTCLI = str(REPO_ROOT / ".venv" / "bin" / "btcli")
SUBPROCESS_TIMEOUT = 120


def _btcli_json(args: list[str], *, no_prompt: bool = False) -> Any:
    extra = ["--no-prompt"] if no_prompt else []
    result = subprocess.run(
        [BTCLI, *args, *extra, "--json-output"],
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT,
    )
    if result.returncode != 0:
        raise RuntimeError(f"btcli {' '.join(args)} failed: {result.stderr.strip()[:300]}")
    # strict=False: the on-chain subnet identity embeds a control character
    # that btcli passes through verbatim.
    return json.loads(result.stdout, strict=False)


def _metagraph_extras(network: str, netuid: int) -> dict[int, dict[str, Any]] | None:
    """axon/active/last_update/permit per uid via one bounded SDK read.

    btcli `subnets show` does not carry these fields; the SDK metagraph does.
    Returns None when the read times out — columns render 'unavailable'.
    """

    from dolores_subnet.chain import bounded_call

    def read() -> tuple[Any, int]:
        import bittensor as bt

        subtensor = bt.Subtensor(network=network)
        return subtensor.metagraph(netuid=netuid, lite=True), int(subtensor.get_current_block())

    try:
        metagraph, block = bounded_call(read, timeout=90)
    except Exception:  # noqa: BLE001 - timeout/RPC failure degrades gracefully
        return None
    extras: dict[int, dict[str, Any]] = {"_block": {"block": block}}  # type: ignore[dict-item]
    axons = list(getattr(metagraph, "axons", []))
    for index, uid in enumerate(int(value) for value in getattr(metagraph, "uids", [])):
        axon = axons[index] if index < len(axons) else None
        ip = str(getattr(axon, "ip", "") or "")
        port = int(getattr(axon, "port", 0) or 0)
        extras[uid] = {
            "axon": f"{ip}:{port}" if port > 0 and ip not in {"", "0.0.0.0"} else "none",
            "active": bool(metagraph.active[index]) if hasattr(metagraph, "active") else None,
            "updated": int(metagraph.last_update[index])
            if hasattr(metagraph, "last_update")
            else None,
            "permit": bool(metagraph.validator_permit[index])
            if hasattr(metagraph, "validator_permit")
            else None,
        }
    return extras


def _weights_row(network: str, netuid: int, uid: int) -> Any:
    """Raw Weights[netuid, uid] via a bounded SDK read; 'unavailable' on hang."""

    from dolores_subnet.chain import bounded_call

    def read() -> Any:
        import bittensor as bt

        subtensor = bt.Subtensor(network=network)
        rows = subtensor.weights(netuid=netuid)
        for row_uid, row in rows:
            if int(row_uid) == uid:
                return [[int(target), int(weight)] for target, weight in row]
        return []

    try:
        return bounded_call(read, timeout=90)
    except Exception as exc:  # noqa: BLE001
        return f"unavailable ({type(exc).__name__})"


def _neuron_rows(show: Any, extras: dict[int, dict[str, Any]] | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for neuron in show.get("uids", []) or []:
        uid = neuron.get("uid")
        extra = (extras or {}).get(uid, {})
        rows.append(
            {
                "uid": uid,
                "hotkey": str(neuron.get("hotkey", ""))[:16],
                "stake": neuron.get("alpha_stake", neuron.get("stake")),
                "permit": extra.get("permit", "unavailable"),
                "active": extra.get("active", "unavailable"),
                "axon": extra.get("axon", "unavailable"),
                "updated": extra.get("updated", "unavailable"),
                "incentive": neuron.get("incentive"),
                "dividends": neuron.get("dividends"),
                "emission": neuron.get("emissions", neuron.get("emission")),
            }
        )
    return rows


def snapshot(network: str, netuid: int, validator_uid: int) -> dict[str, Any]:
    show = _btcli_json(
        ["subnets", "show", "--netuid", str(netuid), "--network", network], no_prompt=True
    )
    hyper = _btcli_json(
        ["subnets", "hyperparameters", "--netuid", str(netuid), "--network", network]
    )
    if isinstance(hyper, list):
        hyper_map = {h.get("hyperparameter"): h.get("value") for h in hyper}
    else:
        hyper_map = hyper
    extras = _metagraph_extras(network, netuid)
    block = (extras or {}).get("_block", {}).get("block", "unavailable")
    return {
        "read_at_utc": datetime.now(UTC).isoformat(),
        "network": network,
        "netuid": netuid,
        "block": block,
        "subnet": {
            "name": str(show.get("name", "")).strip(),
            "tao_emission": show.get("emission"),
            "rate": show.get("rate"),
            "tao_pool": show.get("tao_pool"),
            "alpha_pool": show.get("alpha_pool"),
        },
        "neurons": _neuron_rows(show, extras),
        "hyperparameters": {
            key: hyper_map.get(key)
            for key in ("tempo", "weights_rate_limit", "serving_rate_limit",
                        "commit_reveal_weights_enabled")
        },
        "weights_row": {
            f"Weights[{netuid},{validator_uid}]": _weights_row(network, netuid, validator_uid)
        },
        "raw_show": show,
    }


def render_markdown(snap: dict[str, Any]) -> str:
    subnet = snap.get("subnet", {})
    lines = [
        f"# Testnet status — netuid {snap['netuid']} @ block {snap['block']}",
        f"Read {snap['read_at_utc']} on network `{snap['network']}` (read-only).",
        f"Subnet TAO emission: {subnet.get('tao_emission')} · alpha rate: "
        f"{subnet.get('rate')} τ · pools: {subnet.get('tao_pool')} τ / "
        f"{subnet.get('alpha_pool')} α",
        "",
        "| uid | hotkey | stake α | permit | active | axon | updated "
        "| incentive | dividends | emission |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for row in snap["neurons"]:
        lines.append(
            f"| {row['uid']} | {row['hotkey']}… | {row['stake']} | {row['permit']} "
            f"| {row['active']} | {row['axon']} | {row['updated']} "
            f"| {row['incentive']} | {row['dividends']} | {row['emission']} |"
        )
    lines.append("")
    for key, value in snap["weights_row"].items():
        lines.append(f"Raw `{key}` = `{value}`")
    lines.append("")
    lines.append(f"Hyperparameters: `{snap['hyperparameters']}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netuid", type=int, default=523)
    parser.add_argument("--network", default="test")
    parser.add_argument("--validator-uid", type=int, default=0)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "work" / "testnet_status")
    parser.add_argument("--watch", type=int, default=None, help="poll every N minutes")
    args = parser.parse_args()

    network = assert_safe_network(args.network)
    args.out.mkdir(parents=True, exist_ok=True)

    while True:
        snap = snapshot(network, args.netuid, args.validator_uid)
        block = snap.get("block") or "unknown"
        (args.out / f"status_{block}.json").write_text(
            json.dumps(snap, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
        )
        markdown = render_markdown(snap)
        (args.out / f"status_{block}.md").write_text(markdown, encoding="utf-8")
        print(markdown)
        if args.watch is None:
            return 0
        summary = {
            "read_at_utc": snap["read_at_utc"],
            "block": snap.get("block"),
            "axons": [row["axon"] for row in snap["neurons"]],
            "active": [row["active"] for row in snap["neurons"]],
            "incentive": [row["incentive"] for row in snap["neurons"]],
            "emission": [row["emission"] for row in snap["neurons"]],
        }
        with (args.out / "watch.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(summary, default=str) + "\n")
        time.sleep(args.watch * 60)


if __name__ == "__main__":
    raise SystemExit(main())
