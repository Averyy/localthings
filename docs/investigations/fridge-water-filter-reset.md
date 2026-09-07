# Fridge water-filter reset: solved

`{"x.com.samsung.da.filterReset": "On"}` POSTed to
`/filter/waterfilter/vs/0` resets the water-filter counter.

Measured 2026-09-07 against a live `TP1X_REF_21K` (RF29DB9750QLAA, One UI
7.0, firmware `A-RFWW-TP1-24-T4-COM_20260617`), integration v0.25.0 / HA
2026.8.2. `filterUsage` `"100"` -> `"0"` and `filterStatus` `"replace"` ->
`"normal"`, confirmed held on a fresh DTLS session afterwards.

The value is **case-sensitive**: `"On"` works, `"on"` and `"ON"` both
fault with 5.00. The field is a *trigger*, never stored and never echoed
back in the resource's rep -- so, exactly as in `ac-filter-reset.md`, a
before/after diff of reported state can only ever show the effect, never
the cause.

## Why this was hard to find

`x.com.samsung.da.filterReset` appears **nowhere**: not in the device's
reported rep, not in `/oic/res`, not in the `/device/0` batch, not in any
fixture in this repo, and not in `smartthings-local`. The only thing that
reveals it is the 5.00 it throws on a *wrong* string.

The decisive control was a near-miss field name. An unrecognised field is
swallowed with 2.04; `filterResetZZZ: "zzz"` is swallowed, while
`filterReset: "zzz"` faults. That asymmetry is the entire signal that the
field exists at all.

## The inference that cracked it

The first reading of the 5.00 was that the board type-checks the field
and rejects strings -- because non-strings (`true`, `0`, `1`, `2`, `100`,
`["replaceable"]`) all returned 2.04. That reading is **backwards**, and
it is the trap worth remembering:

- **non-string** -> `oc_rep_get_string()` fails, the handler never enters
  the reset block -> 2.04, inert. The value was never looked at.
- **string** -> the getter succeeds, the handler enters the dispatch,
  fails to match the value, and errors out -> 5.00.

So 5.00 was not rejection, it was *reaching the right code path and
missing*. Under that reading, string is the correct type and the search
collapses from an unbounded value space to a small vocabulary of command
words -- which is how `"On"` was found on the eighth try.

Generalisable: on this firmware a 5.00 is closer to a hit than a 2.04.
The error means you are talking to real code.

## Traps on this board

1. **2.04 means nothing.** This firmware ACKs unknown field names rather
   than rejecting them. 2.04 does not indicate a recognised field, a
   parsed value, or a stored one. Only a live re-read is evidence. The
   PRAC_20K's informative 4.00-vs-5.00 type split does not exist here.
2. **The POST response body is a verbatim echo** -- the payload returned
   unchanged, on 2.04 and 5.00 alike, with no `"Control fail, <...>"`
   diagnostic like the laundry firmware. Worth stating because
   `_raw_write_blocking` discards that body (`code, _ = sess.post(...)`)
   and it is tempting to assume the answer is hiding there. It is not;
   capturing it was tried and showed only the echo.
3. **`changed` in `write_resource` output is not "something changed."**
   It is `all(after.get(k) == v for k, v in payload.items())` -- "are the
   payload's values present afterward." Writing a field its own existing
   value reports `changed: true` having done nothing.
4. **One CoAP/DTLS session per device.** A second session contends with
   the integration's. Disable the config entry before probing directly,
   or the two will disrupt each other and muddy every result.

## Not the answer (ruled out)

- Direct writes of `filterUsage` (`"0"` and `0`) and `filterStatus`
  (`"normal"`), separately and combined: 2.04, inert.
- `filterResetType: ["replaceable"]` is descriptive, not a command, as
  `ac-filter-reset.md` says. But note its sharp edge: the adjacent,
  unadvertised `filterReset` *is* real. "The reset-shaped field in the
  rep is a decoy" and "there is no reset field" are different claims, and
  only the first is true.
- The AC's `/mode/vs/0` single-token options merge. This board's mode
  resource has `x.com.samsung.da.modes` and no `options` blob, and a
  nonsense token there is discarded. Its `modes` carries
  `WATERFILTER_ENABLE`; the corpus knows only that and
  `WATERFILTER_DISABLE`, which are capability declarations, not commands.
- An unenumerated resource. `/oic/res` carries only 14 platform links
  here; the functional resources come from the `/device/0` batch, which
  has no reset href. No `/actions/vs/0` on this board.
- An explicit `?if=oic.if.a` interface query: no different from baseline.

## Reproducing

Probed with a direct DTLS/CoAP session outside HA (integration disabled
first, per trap 4), using `certs/ab0b0ac4_fullchain.pem` and
`smartthings_local.protocol.dtls_session.DtlsCoapSession`, POSTing to
`["filter","waterfilter","vs","0"]`. The integration's own write path
cannot show the POST response body; that is why the probe was built
outside it.

Note the counter only climbs in normal use, so once reset there is no
cheap way to re-test a candidate write for months. Verification of a
*wrong* value is still available at any time, though: junk strings return
5.00 and `"On"` returns 2.04.
