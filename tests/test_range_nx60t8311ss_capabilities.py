"""Gas range NX60T8311SS/AA (TP2X_DA-KS-RANGE-0101X, issue #444): the first
TP2X range in the corpus, captured with all five burners lit so the
/cooktopmonitoring/vs/0 bitmask is non-zero (31)."""

import pytest

from custom_components.localthings.registry.adapter import flatten
from custom_components.localthings.registry.by_type import resolve
from custom_components.localthings.registry.capabilities import range as range_caps
from custom_components.localthings.registry.discovery import discover
from tests.conftest import _load_device

DEVICE_TYPES = ("oic.wk.d", "oic.d.range")


def _range():
    resources = _load_device("range_nx60t8311ss")
    reg = resolve(resources, device_types=DEVICE_TYPES)
    return reg, resources


def _state(resources=None):
    reg, res = _range()
    res = resources if resources is not None else res
    bound = discover(res, reg.capabilities, reg.pattern_capabilities)
    return flatten(bound, res)


def test_resolves_to_range_registry():
    reg, _ = _range()
    assert reg is not None and reg.name == "range"


def test_no_unbound_hrefs():
    reg, resources = _range()
    unbound = []
    discover(resources, reg.capabilities, reg.pattern_capabilities, log=unbound.append)
    assert unbound == []


def test_all_five_burners_lit_in_capture():
    state = _state()
    assert state["cooktop_running_state"] == "Run"
    assert state["active_burners"] == 5
    for n in range(1, 6):
        assert state[f"cooktop_burner_{n}"] is True


def test_mask_entities_gated_when_field_absent():
    """Issue #404's NX6512A reports the same resource without the field
    (only warmingCenterState/cooktopRunningState); no phantom burners."""
    _, resources = _range()
    resources = dict(resources)
    rep = dict(resources["/cooktopmonitoring/vs/0"])
    del rep["x.com.samsung.da.cooktopMonitoring"]
    resources["/cooktopmonitoring/vs/0"] = rep
    state = _state(resources)
    assert "active_burners" not in state
    assert not any(k.startswith("cooktop_burner_") for k in state)


def _mask_desc(key):
    return next(e for e in range_caps.COOKTOP_MONITORING.entities if e.key == key)


@pytest.mark.parametrize(
    ("mask", "lit", "count"),
    [
        ("0", (), 0),
        ("1", (1,), 1),  # front-left alone
        ("8", (4,), 1),  # back-right alone; unchanged when turned down to simmer
        ("3", (1, 2), 2),
        ("7", (1, 2, 3), 3),
        ("23", (1, 2, 3, 5), 4),
        ("31", (1, 2, 3, 4, 5), 5),
        ("24", (4, 5), 2),
    ],
)
def test_mask_decodes_to_burners_and_count(mask, lit, count):
    """Values read live while lighting and extinguishing burners one at a
    time on the NX60T8311SS."""
    rep = {"x.com.samsung.da.cooktopMonitoring": mask}
    assert _mask_desc("active_burners").rep_fn(rep) == count
    for n in range(1, 6):
        assert _mask_desc(f"cooktop_burner_{n}").rep_fn(rep) is (n in lit)


def test_mask_unparseable_reads_unknown():
    rep = {"x.com.samsung.da.cooktopMonitoring": "n/a"}
    assert _mask_desc("active_burners").rep_fn(rep) is None
    assert _mask_desc("cooktop_burner_1").rep_fn(rep) is None
