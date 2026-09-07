# Filter reset: solved, and it is a property of the resource type

`{"x.com.samsung.da.filterReset": "On"}` POSTed to an
`x.com.samsung.da.filter.*` resource resets that filter's usage counter.
The value is **case-sensitive**: `"On"` works, `"on"` and `"ON"` both
fault 5.00.

Confirmed on two unrelated families:

| Appliance | Resource | Result |
|---|---|---|
| `TP1X_REF_21K` fridge (RF29DB9750QLAA, `A-RFWW-TP1-24-T4-COM_20260617`) | `/filter/waterfilter/vs/0` | `filterUsage` `"100"` -> `"0"`, `filterStatus` `replace` -> `normal`, held on a fresh DTLS session |
| `TP1X_DA_AC_RAC_01001` air conditioner | `/filter/airdustfilter/vs/0` | reset confirmed by the reporter in #449 |

Two boards that share no registry code and no capability module is what
makes this a property of the resource type rather than of one firmware.
The field is a *trigger*: never stored, never echoed back in the rep, so
a before/after diff of reported state shows only the effect and never the
cause (same shape as `ac-filter-reset.md`'s token).

## Why it is hard to find

`x.com.samsung.da.filterReset` appears in almost no reported
representation -- not in the fridge's rep, `/oic/res`, its `/device/0`
batch, or `smartthings-local`. The only thing that reveals it is the 5.00
a *wrong string* produces.

The decisive control is a near-miss field name. An unrecognised field is
swallowed with 2.04; `filterResetZZZ: "zzz"` is swallowed, while
`filterReset: "zzz"` faults. That asymmetry is the entire signal that the
field exists.

(It is not absent from every family: `tests/fixtures/dishwasher_device.json`
reports a stored `"x.com.samsung.da.filterReset": "00"` on its own
`/filter/waterfilter/vs/0`. Evidence the value grammar can differ, and a
reason the button is gated rather than offered everywhere.)

## The inference that cracked it

The first reading of the 5.00 was that the board type-checks the field and
rejects strings, because non-strings (`true`, `0`, `1`, `["replaceable"]`)
all returned 2.04. That reading is **backwards**, and it is the trap worth
remembering:

- **non-string** -> `oc_rep_get_string()` fails, the handler never enters
  the reset block -> 2.04, inert. The value was never looked at.
- **string** -> the getter succeeds, the handler enters the dispatch,
  fails to match the value, and errors out -> 5.00.

So 5.00 was not rejection, it was *reaching the right code path and
missing*. Under that reading, string is the correct type and the search
collapses from an unbounded value space to a small vocabulary of command
words -- which is how `"On"` was found on the eighth try.

Generalisable: on this firmware a 5.00 is closer to a hit than a 2.04. The
error means you are talking to real code.

## Traps

1. **2.04 means nothing.** This firmware ACKs unknown field names rather
   than rejecting them. 2.04 does not indicate a recognised field, a
   parsed value, or a stored one. Only a live re-read is evidence.
2. **The POST response body is a verbatim echo** -- the payload returned
   unchanged, on 2.04 and 5.00 alike, with no `"Control fail, <...>"`
   diagnostic like the laundry firmware. Worth stating because
   `_raw_write_blocking` discards that body (`code, _ = sess.post(...)`)
   and it is tempting to assume the answer hides there. It does not;
   capturing it was tried and showed only the echo.
3. **`changed` in `write_resource` output is not "something changed."**
   It is `all(after.get(k) == v for k, v in payload.items())` -- "are the
   payload's values present afterward." Writing a field its own existing
   value reports `changed: true` having done nothing.
4. **The board can lag its own reset.** The fridge reflected the new
   values within ~2 s; the AC in #449 took roughly a minute, with an
   immediate readback still showing the pre-reset usage and
   `changed: false`. A single post-write GET is not enough to call a
   candidate value dead on an unfamiliar board.
5. **One CoAP/DTLS session per device.** A second session contends with
   the integration's. Disable the config entry before probing directly.

## Not the answer (ruled out)

- Direct writes of `filterUsage` (`"0"` and `0`) and `filterStatus`
  (`"normal"`), separately and combined: 2.04, inert. This reproduces the
  independent negative result from PR #429, which measured the same
  `filterUsage: "0"` write returning 2.04 with the prior value intact on a
  one-second readback. That conclusion -- that `filterResetType` alone does
  not establish a reset command -- was correct; the reset simply lives in a
  different, unadvertised field.
- `filterResetType` is descriptive, not a command. Its sharp edge is that
  the adjacent, unadvertised `filterReset` is real: "the reset-shaped field
  in the rep is a decoy" and "there is no reset field" are different
  claims, and only the first is true.
- The AC's `/mode/vs/0` single-token options merge (see
  `ac-filter-reset.md`) is a *different, also-real* mechanism for the
  legacy `FilterTime_` counter. It does not apply to boards that keep
  usage in a `/filter/...` resource, and a nonsense token there is
  discarded.
- An unenumerated resource. `/oic/res` carries only 14 platform links on
  the fridge; the functional resources come from the `/device/0` batch,
  which has no reset-specific href.

## What ships, and what is extrapolation

`common.filter_reset_button` is bound to all six filter resources, gated on
`filterResetType` naming a reset the device claims to support
(`replaceable`/`washable`; the corpus also carries `notresetable`, which a
bare presence check would read as a yes).

| Resource | Button key | Evidence |
|---|---|---|
| `/filter/waterfilter/vs/0` | `filter_reset` | **measured** |
| `/filter/airdustfilter/vs/0` | `air_filter_reset` | **measured** (#449) |
| `/filter/airdustPM1filter/vs/0` | `air_filter_pm1_reset` | extrapolated |
| `/filter/hepafilter/vs/0` | `hepa_filter_reset` | extrapolated |
| `/filter/deodorfilter/vs/0` | `deodor_filter_reset` | extrapolated |
| `/filter/hoodfilter/vs/0` | `hood_filter_reset` | extrapolated |

The extrapolated four rest on the resource-type argument above, not on
measurement. A wrong token on those faults 5.00, and the entity write path
logs the code without surfacing anything to the user -- so a report of "the
button does nothing" on one of them is the expected shape of that failure,
and worth a `write_resource` probe before assuming the resource is
read-only.

## Known limitation of the button

The write body carries only the trigger, so the optimistic cache entry sets
`filterReset` and nothing else. The board's actual response lands on
`filterUsage` and `filterStatus`, which the body does not set, and
`mark_write_pending` suppresses non-optimistic updates for
`_POST_TIMEOUT_S + _POLL_TIMEOUT_S` (43 s) -- so after a successful press
the sensors keep reading pre-reset values for up to that long, *plus* any
board-side lag (trap 4).

Putting the expected post-reset values in the body would close the HA half
of that window, but the body is also what goes on the wire, and only
`{"filterReset": "On"}` exactly is verified. Adding fields to a payload
that cannot be cheaply re-tested -- the counter only climbs, so there is no
second reset to measure for months -- trades a cosmetic delay for an
unverified write. Left as-is deliberately.

Related wart: because the cache merges and the board never echoes the
trigger back, `"filterReset": "On"` stays in the cached rep for that
resource and appears in diagnostics dumps as though the device reported it.
Do not read that as a device-reported field.
