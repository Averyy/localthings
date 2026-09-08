"""Air-quality readings are gated on the board listing that sensor type.

Issue #414: an AVT-WW-TP1-22-TOUCHOTN purifier reports a single CleanLevel
item in /sensors/vs/0 and grew four permanently-unknown particulate sensors
next to it. `common.has_sensor_type` was already doing this job for the AC
family and for CO2; these tests pin it across the three families that read
the same items[] shape.
"""

import pytest

from custom_components.localthings.registry.adapter import flatten
from custom_components.localthings.registry.by_type import resolve
from custom_components.localthings.registry.capabilities import (
    air_monitor,
    air_purifier,
    range_hood,
)
from custom_components.localthings.registry.discovery import discover
from tests.conftest import _load_device

_PARTICULATE = ("dust", "fine_dust", "super_fine_dust", "odor")


def _state(fixture, device_types=()):
    resources = _load_device(fixture)
    reg = resolve(resources, device_types=device_types)
    assert reg is not None, fixture
    bound = discover(resources, reg.capabilities, reg.pattern_capabilities)
    return flatten(bound, resources)


def test_touchotn_fixture_has_no_unbound_hrefs():
    resources = _load_device("air_purifier_avt_ww_touchotn")
    reg = resolve(resources, device_types=("oic.wk.d", "oic.d.airpurifier"))
    assert reg is not None and reg.name == "air_purifier"
    unbound = []
    discover(resources, reg.capabilities, reg.pattern_capabilities, log=unbound.append)
    assert unbound == []


def test_board_listing_only_clean_level_gets_only_clean_level():
    """The reported board (issue #414). It's powered on and running in this
    capture, so the short items[] is what it reports, not an idle artifact."""
    state = _state("air_purifier_avt_ww_touchotn", ("oic.wk.d", "oic.d.airpurifier"))
    assert state["clean_level"] == 1
    for key in _PARTICULATE:
        assert key not in state, key


@pytest.mark.parametrize(
    "fixture",
    ["air_purifier", "air_purifier_vtww", "air_purifier_avt_ww", "air_purifier_tp1x_da_ac_air"],
)
def test_boards_listing_every_type_keep_every_reading(fixture):
    """The other side of the gate: it must not cost a reading on any board
    that does report one."""
    state = _state(fixture)
    for key in (*_PARTICULATE, "clean_level"):
        assert key in state, key


def test_air_monitor_keeps_its_full_set():
    state = _state("air_monitor")
    for key in (*_PARTICULATE, "clean_level", "co2"):
        assert key in state, key


def _air_quality_descs():
    """Every descriptor across the three families that reads items[]."""
    for capability in (air_purifier.AIR_QUALITY, air_monitor.SENSORS, range_hood.AIR_QUALITY):
        for desc in capability.entities:
            yield capability, desc


def test_every_items_reader_is_gated():
    """A new reading added to any of these without a gate is the bug again."""
    for capability, desc in _air_quality_descs():
        assert desc.exists_fn is not None, f"{capability.href}:{desc.key}"


def test_gate_keeps_the_not_yet_fetched_stub_carve_out():
    """A /device/0 stub means "no data yet", not "no sensor" -- dropping the
    entity there would leave a board with no air-quality sensors at all
    whenever discovery raced the first sub-poll (issue #127)."""
    stub = {"href": "/sensors/vs/0"}
    for _capability, desc in _air_quality_descs():
        assert desc.exists_fn(stub, {"/sensors/vs/0": stub}) is True
