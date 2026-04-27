# OEM Profile Format

This workspace now has a profile layout you can use to move from a generic
UDS trace generator to an OEM-specific flashing generator without rewriting
the core logic each time.

## Folder layout

```text
CAN/
  firmware/
  profiles/
    mahindra_template.json
  profile_plugins/
    mahindra_seed_key_v1.py
  hex_parser.py
  hex_parsing.py
```

## Purpose of each part

- `profiles/`
  Store OEM/ECU-specific settings as data.

- `profile_plugins/`
  Store OEM-specific Python logic that cannot be expressed cleanly in JSON,
  such as seed-key algorithms or custom payload builders.

- `hex_parsing.py`
  Stays the generic engine: parse HEX, build ISO-TP traffic, write ASC.

## What should live in JSON

Use JSON for values that are declarative and stable:

- CAN IDs
- addressing mode
- padding byte
- session subfunctions
- session timing bytes (P2 / P2*)
- service IDs
- routine IDs
- address/size field widths
- timing values
- transfer block size
- workflow sequence

## What should live in Python plugins

Use Python plugins for behavior that needs logic:

- seed-to-key algorithms
- checksum algorithms
- custom erase payload builders
- custom RequestDownload field packing
- OEM-specific segment filtering rules
- OEM-specific checksum/dependency routine payloads

## Recommended next step in code

Refactor `hex_parsing.py` in this order:

1. Add a `load_profile(profile_path)` helper.
2. Replace hardcoded constants with values from the loaded profile.
3. Replace the placeholder seed-key call with dynamic import from
   `profile_plugins/`.
4. Replace the fixed flashing sequence with a step runner driven by the
   `sequence` array in the profile.
5. Keep generic ISO-TP and ASC writer code separate from OEM-specific logic.

## Suggested naming pattern

Use one profile per ECU/programming family:

- `mahindra_ccm_v1.json`
- `mahindra_bcm_v1.json`
- `mahindra_adas_v1.json`

If one ECU changes across vehicle platforms or software generations, create a
new profile version instead of mutating the old one heavily.

## Minimum data you must confirm from Mahindra

- request CAN ID
- response CAN ID
- programming session subfunction
- security seed request/send key subfunctions
- actual seed-key algorithm
- erase routine ID
- RequestDownload address and size format
- max transfer block length
- TransferExit behavior
- ECU reset type
- timing and response-pending behavior

## Template status

`mahindra_template.json` is intentionally a starting point only. It is not
OEM-accurate yet and should be copied into a concrete profile such as
`mahindra_ccm_v1.json` before use.
