#!/usr/bin/env python3
"""bsc-peek - read-only BNB Chain balance viewer.

Prints native BNB plus any ERC-20 balances for one or more addresses,
optionally priced in USD via the public DexScreener API.

No private keys, no signing, no transactions - every call is a plain
JSON-RPC eth_call against a public endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

RPC = "https://bsc-rpc.publicnode.com"
DEXSCREENER = "https://api.dexscreener.com/latest/dex/tokens/"
UA = "bsc-peek/1.0"

# A few well-known BEP-20s. Extend freely; the script accepts --token too.
DEFAULT_TOKENS = {
    "USDT": "0x55d398326f99059fF775485246999027B3197955",
    "USDC": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    "WBNB": "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    "BTCB": "0x7130d2A12B9BCbFAe4f2634d864A1Ee1Ce3Ead9c",
}

SELECTOR_BALANCE_OF = "0x70a08231"
SELECTOR_DECIMALS = "0x313ce567"
SELECTOR_SYMBOL = "0x95d89b41"


def rpc(method: str, params: list) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        RPC, data=payload, headers={"Content-Type": "application/json", "User-Agent": UA}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read())
    if "error" in body:
        raise RuntimeError(body["error"].get("message", "rpc error"))
    return body


def eth_call(to: str, data: str) -> str:
    return rpc("eth_call", [{"to": to, "data": data}, "latest"])["result"]


def native_balance(address: str) -> float:
    wei = int(rpc("eth_getBalance", [address, "latest"])["result"], 16)
    return wei / 1e18


def token_meta(token: str) -> tuple[str, int]:
    symbol = token
    decimals = 18
    try:
        raw = eth_call(token, SELECTOR_SYMBOL)
        if len(raw) >= 130:
            length = int(raw[66:130], 16)
            symbol = bytes.fromhex(raw[130:130 + length * 2]).decode("utf-8", "replace")
    except (RuntimeError, ValueError):
        pass
    try:
        decimals = int(eth_call(token, SELECTOR_DECIMALS), 16)
    except (RuntimeError, ValueError):
        pass
    return symbol, decimals


def token_balance(token: str, address: str, decimals: int) -> float:
    data = SELECTOR_BALANCE_OF + address[2:].lower().rjust(64, "0")
    return int(eth_call(token, data), 16) / (10 ** decimals)


def usd_price(token: str) -> float | None:
    try:
        req = urllib.request.Request(DEXSCREENER + token, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            pairs = json.loads(resp.read()).get("pairs") or []
        priced = [p for p in pairs if p.get("priceUsd")]
        if not priced:
            return None
        best = max(priced, key=lambda p: float(p.get("liquidity", {}).get("usd") or 0))
        return float(best["priceUsd"])
    except (urllib.error.URLError, ValueError, KeyError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only BNB Chain balance viewer")
    parser.add_argument("addresses", nargs="+", help="wallet address(es) to inspect")
    parser.add_argument("--token", action="append", default=[], metavar="ADDRESS",
                        help="extra BEP-20 contract to include (repeatable)")
    parser.add_argument("--no-defaults", action="store_true",
                        help="skip the built-in token list")
    parser.add_argument("--price", action="store_true",
                        help="also fetch USD prices from DexScreener")
    args = parser.parse_args()

    tokens = {} if args.no_defaults else dict(DEFAULT_TOKENS)
    for i, addr in enumerate(args.token):
        tokens[f"TOKEN{i + 1}"] = addr

    bnb_price = usd_price("0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c") if args.price else None

    with ThreadPoolExecutor(max_workers=8) as pool:
        metas = list(pool.map(token_meta, tokens.values()))

    for address in args.addresses:
        address = address.strip()
        if not address.startswith("0x") or len(address) != 42:
            print(f"{address}: invalid address", file=sys.stderr)
            continue

        print(f"\n{address}")
        bnb = native_balance(address)
        line = f"  {'BNB':<10} {bnb:>20.6f}"
        if bnb_price:
            line += f"  ${bnb * bnb_price:,.2f}"
        print(line)

        for (symbol, decimals), token in zip(metas, tokens.values()):
            try:
                amount = token_balance(token, address, decimals)
            except RuntimeError:
                continue
            if amount == 0:
                continue
            line = f"  {symbol[:10]:<10} {amount:>20.6f}"
            if args.price:
                price = usd_price(token)
                if price:
                    line += f"  ${amount * price:,.2f}"
            print(line)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
