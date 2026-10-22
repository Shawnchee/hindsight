# m0/gaps: DeFiHackLabs coverage-gap measurement

These files measure how many Ethereum incidents in DeFiLlama's hacks list are missing from DeFiHackLabs. Results are in [summary.md](summary.md).

- `gaps.json` holds the machine-readable output. It contains counts, the per-month table, incident names and dates, and the nearest DHL candidate for each incident.
- The DeFiLlama data is for **internal measurement only**: its licence is personal and non-commercial (PRD §7.1). Don't commit or redistribute the raw download.
- The outputs keep only counts and incident names and dates. Downloads go in `m0/data/gaps/`, which is gitignored.

## Regenerate (from repo root)

```sh
mkdir -p m0/data/gaps m0/gaps
# 1. DeFiLlama hacks snapshot (one request)
curl -sS --max-time 120 -o m0/data/gaps/llama_hacks.json https://api.llama.fi/hacks
# 2. DeFiHackLabs shallow clone. Untrusted: read only, never run anything in it.
rm -rf m0/data/gaps/dhl
git clone --depth 1 https://github.com/SunWeb3Sec/DeFiHackLabs m0/data/gaps/dhl
git -C m0/data/gaps/dhl rev-parse HEAD   # record this; measured run used 23c7bd83ccb4524972a9493617fcc8764ab6269b
# 3. Measure (isolated interpreter, script lives outside the clone)
python3 -I m0/scripts/gaps/measure_gaps.py --data m0/data/gaps --out m0/gaps
```

The script uses only the standard library. It prints the headline counts and writes `m0/gaps/gaps.json`. The window, gap months, ±7-day tolerance and fuzzy threshold are constants at the top of `m0/scripts/gaps/measure_gaps.py`. Use `--seed` to change the spot-check sample. `summary.md` is written by hand from `gaps.json`, so update it whenever the numbers change.

Pinning to the measured DHL commit needs a full clone: `git clone https://github.com/SunWeb3Sec/DeFiHackLabs m0/data/gaps/dhl && git -C m0/data/gaps/dhl checkout 23c7bd8`. DeFiLlama has no versioning, so a new fetch will drift.
