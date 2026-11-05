# bsc-peek

Read-only BNB Chain balance viewer. No keys, no signing, no transactions —
every request is a plain `eth_call` against a public RPC.

## Usage

```bash
python bsc_peek.py 0x0000000000000000000000000000000000000000
```

Output:

```
0x0000000000000000000000000000000000000000
  BNB                 1.234567
  USDT              120.000000
```

Add USD prices (DexScreener, best-liquidity pair):

```bash
python bsc_peek.py --price 0x... 0x...
```

Add your own token:

```bash
python bsc_peek.py --token 0xYourTokenContract 0x...
```

Skip the built-in list:

```bash
python bsc_peek.py --no-defaults --token 0x... 0x...
```

## Notes

- Requires Python 3.10+ and only the standard library.
- Default RPC is `https://bsc-rpc.publicnode.com`. Change `RPC` at the top of the
  script if you prefer another endpoint.
- Tokens with a zero balance are skipped; symbol/decimals failures fall back to
  the placeholder name and 18 decimals.
- Prices come from the public DexScreener API and can be missing or stale for
  low-liquidity tokens.

## License

MIT
