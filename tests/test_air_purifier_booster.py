"""Tower air purifier AX100DB900EDD (TP1X_DA-AC-AIR-01031_0000, issue #441).

Same board as the compact air_purifier_tp1x_da_ac_air fixture plus the three
/booster/ hrefs -- the second fan, the mood light and the oscillating head on
top of the tower -- which used to land in unbound_hrefs and fire the
coverage-gap repair.
"""

import pytest

from custom_components.localthings.registry.adapter import flatten
from custom_components.localthings.registry.by_type import resolve
from custom_components.localthings.registry.capabilities import air_purifier
from custom_components.localthings.registry.discovery import discover
from tests.conftest import _load_device

DEVICE_TYPES = ("oic.wk.d", "oic.d.airpurifier")


def _booster(fixture="air_purifier_ax100db900edd"):
    resources = _load_device(fixture)
    reg = resolve(resources, device_types=DEVICE_TYPES)
    return reg, resources


def _state(fixture="air_purifier_ax100db900edd"):
    reg, resources = _booster(fixture)
    bound = discover(resources, reg.capabilities, reg.pattern_capabilities)
    return flatten(bound, resources)


def _desc(capability, key):
    return next(e for e in capability.entities if e.key == key)


def test_resolves_to_air_purifier_registry():
    reg, _ = _booster()
    assert reg is not None and reg.name == "air_purifier"


def test_no_unbound_hrefs():
    """The three /booster/ hrefs were the whole gap on this dump."""
    reg, resources = _booster()
    unbound = []
    discover(resources, reg.capabilities, reg.pattern_capabilities, log=unbound.append)
    assert unbound == []


def test_booster_state_matches_the_capture():
    state = _state()
    assert state["booster_fan_mode"] == "Auto"
    assert state["booster_light"] is True
    assert state["booster_light_color_temperature"] == "3000K"
    assert state["booster_light_brightness"] == "Smart"
    assert state["booster_light_manual_brightness"] is True
    assert state["booster_oscillation"] is True
    assert state["booster_oscillation_angle"] == "Circulation"
    assert state["booster_angle_location"] == "2"


@pytest.mark.parametrize(
    ("capability", "key", "field"),
    [
        (air_purifier.BOOSTER_FAN_MODE, "booster_fan_mode", "supportedFanModes"),
        (
            air_purifier.BOOSTER_LIGHT,
            "booster_light_color_temperature",
            "supportedColorTemperatures",
        ),
        (air_purifier.BOOSTER_LIGHT, "booster_light_brightness", "supportedBrightnessLevels"),
        (
            air_purifier.BOOSTER_OSCILLATION,
            "booster_oscillation_angle",
            "supportedOscillationAngles",
        ),
    ],
)
def test_select_options_come_from_the_device(capability, key, field):
    """Every booster select names its own supported values, so none of them
    carries a hardcoded tuple that a different tower could outgrow."""
    desc = _desc(capability, key)
    assert desc.options_field == field
    assert not desc.options
    _, resources = _booster()
    assert resources[capability.href][field]


@pytest.mark.parametrize(
    ("capability", "key", "payload", "expected"),
    [
        (
            air_purifier.BOOSTER_FAN_MODE,
            "booster_fan_mode",
            "High",
            (["booster", "fanmode", "vs", "0"], {"fanMode": "High"}),
        ),
        (
            air_purifier.BOOSTER_LIGHT,
            "booster_light",
            "Off",
            (["booster", "light", "vs", "0"], {"light": "Off"}),
        ),
        (
            air_purifier.BOOSTER_LIGHT,
            "booster_light_color_temperature",
            "6500K",
            (["booster", "light", "vs", "0"], {"colorTemperature": "6500K"}),
        ),
        (
            air_purifier.BOOSTER_LIGHT,
            "booster_light_brightness",
            "Low",
            (["booster", "light", "vs", "0"], {"brightnessLevel": "Low"}),
        ),
        (
            air_purifier.BOOSTER_LIGHT,
            "booster_light_manual_brightness",
            "On",
            (["booster", "light", "vs", "0"], {"manualBrightness": "On"}),
        ),
        (
            air_purifier.BOOSTER_OSCILLATION,
            "booster_oscillation",
            "Off",
            (["booster", "oscillation", "vs", "0"], {"oscillation": "Off"}),
        ),
        (
            air_purifier.BOOSTER_OSCILLATION,
            "booster_oscillation_angle",
            "LeftWide",
            (["booster", "oscillation", "vs", "0"], {"oscillationAngle": "LeftWide"}),
        ),
    ],
)
def test_writes_target_their_own_href_and_field(capability, key, payload, expected):
    """Inferred from the resource shape, not a confirmed round trip (issue
    #441) -- pinned so a later confirmation changes a value here rather than
    silently drifting."""
    assert _desc(capability, key).write_fn(payload, {}) == expected


def test_angle_location_stays_a_raw_diagnostic():
    """It reads '2' next to oscillationAngle 'Circulation', the second
    supported angle -- an index and a head position are indistinguishable on
    one sample, so no unit, device_class or state_class is asserted."""
    desc = _desc(air_purifier.BOOSTER_OSCILLATION, "booster_angle_location")
    assert desc.entity_category == "diagnostic"
    assert (desc.unit, desc.device_class, desc.state_class) == (None, None, None)


def test_compact_sibling_gets_no_booster_entities():
    """The same registry, the same board family, no /booster/ hrefs -- the
    capabilities simply don't bind."""
    state = _state("air_purifier_tp1x_da_ac_air")
    assert not [k for k in state if k.startswith("booster")]
