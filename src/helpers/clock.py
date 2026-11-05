# generated from brief/09 · part 09 owns this file
"""Verified gait clock (part 09).

The gait signal and the step-rate clock. This is the signal that
worked — head-bob is not implemented anywhere in the library (R-C2).
"""

from __future__ import annotations

import math

__all__ = [
    "clock_evidence",
    "gait_signal",
    "step_rate",
]

try:  # Single source of limits (part 04); fall back to spec values.
    from src.config import CLOCK_BAND_HZ as _CONFIG_BAND
    from src.config import GAIT_MEDIAN_WINDOW_S as _CONFIG_WINDOW_S
except (ImportError, AttributeError):  # pragma: no cover
    _CONFIG_BAND = None
    _CONFIG_WINDOW_S = None

#: Fallbacks when :mod:`src.config` is unreachable (the sandbox ships
#: only ``src/helpers``): a ~1 s running-median window and the default
#: 1–4 Hz step-rate band.
GAIT_MEDIAN_WINDOW_S_FALLBACK = 1.0
CLOCK_BAND_HZ_FALLBACK = (1.0, 4.0)


def _median_window_s():
    if isinstance(_CONFIG_WINDOW_S, (int, float)):
        return float(_CONFIG_WINDOW_S)
    return GAIT_MEDIAN_WINDOW_S_FALLBACK


def _default_band():
    if isinstance(_CONFIG_BAND, (list, tuple)) and len(_CONFIG_BAND) == 2:
        try:
            return (float(_CONFIG_BAND[0]), float(_CONFIG_BAND[1]))
        except (TypeError, ValueError):
            pass
    return CLOCK_BAND_HZ_FALLBACK


def gait_signal(masks):
    """Per-frame gait signal from a mask series.

    ``masks`` maps ``frame_index`` to a mask. For each frame the
    signal is the width of the **lowest 30% of the mask rows** (from
    the bottom of the mask's span upward) divided by the mask height:
    ``(max occupied column - min occupied column + 1) / height`` over
    that row band. Legs spreading and closing modulate this width
    once per stride cycle.

    Returns ``{"frame", "gait"}`` rows sorted by frame. Raises
    ``ValueError`` (``"empty_mask"``) when a frame's mask is empty —
    a missing body is not a zero-width measurement.
    """
    import numpy as np

    try:
        items = sorted(masks.items())
    except AttributeError as exc:
        raise ValueError(
            f"bad_masks: masks must map frame_index to a mask: "
            f"{exc}") from exc
    rows = []
    for frame, mask in items:
        try:
            frame_index = int(frame)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_frame: frame key {frame!r} must be an int: "
                f"{exc}") from exc
        arr = np.asarray(mask)
        if arr.ndim != 2:
            raise ValueError(
                f"bad_mask: frame {frame_index} mask is {arr.ndim}-D, "
                "need 2-D")
        hit = arr.astype(bool)
        if not hit.any():
            raise ValueError("empty_mask")
        ys, xs = np.nonzero(hit)
        top, bottom = int(ys.min()), int(ys.max())
        height = bottom - top + 1
        band_rows = max(1, int(round(0.3 * height)))
        low = bottom - band_rows + 1
        sub = hit[low:bottom + 1, :]
        sub_ys, sub_xs = np.nonzero(sub)
        if len(sub_xs) == 0:
            raise ValueError("empty_mask")
        width = int(sub_xs.max() - sub_xs.min() + 1)
        rows.append({"frame": frame_index,
                     "gait": float(width) / float(height)})
    if not rows:
        raise ValueError("empty_mask")
    return rows


def _detrend_median(signal, window):
    """Subtract a running-median trend (odd ``window`` samples)."""
    from scipy.ndimage import median_filter

    size = int(window)
    if size % 2 == 0:
        size -= 1
    size = max(1, min(size, len(signal) if len(signal) % 2 else
                      len(signal) - 1))
    import numpy as np

    trend = median_filter(np.asarray(signal, dtype=float), size=size,
                          mode="reflect")
    return np.asarray(signal, dtype=float) - trend


def _band_of(band_hz):
    """The ``(lo, hi)`` search band, or ``ValueError`` (``"bad_band"``)."""
    band = _default_band() if band_hz is None else band_hz
    try:
        low, high = float(band[0]), float(band[1])
    except (TypeError, ValueError, IndexError) as exc:
        raise ValueError(
            f"bad_band: band_hz must be (lo_hz, hi_hz): {exc}") from exc
    if not (math.isfinite(low) and math.isfinite(high)
            and 0 < low < high):
        raise ValueError(
            f"bad_band: band_hz needs 0 < lo < hi, got {band!r}")
    return low, high


def step_rate(signal, t, band_hz=None):
    """Step-rate clock from a gait signal.

    Detrends ``signal`` with a **running median** (window from config,
    odd, ~1 s — this removes the slow perspective trend without
    touching the stepping oscillation), then takes a simple
    periodogram/FFT peak search **strictly inside** ``band_hz``
    (default 1–4 Hz). ``t`` holds the sample times in seconds.

    Returns ``(result, flag)``:

    - on success, ``result`` is ``{"peak_hz", "as_step_hz",
      "as_stride_hz", "alt_step_hz", "harmonic_evidence", "band_hz"}``
      and ``flag`` is None. The peak is read two ways, because R-C3's
      ambiguity is data, not a silent choice: reading A takes the
      peak as the step rate (``as_step_hz = peak``,
      ``as_stride_hz = peak / 2``); reading B takes the peak as the
      stride rate (``alt_step_hz = 2 × peak``). ``harmonic_evidence``
      reports the spectrum power at the peak, at double and at half
      the peak (nearest bins, evidence only — never returned as a
      rate) with their ratios, so the choice between readings stays
      checkable.
    - when the peak sits at a band edge (the lowest or highest
      in-band bin, or within 1.5 bins of the band boundary — the
      peak is then unresolved from the boundary), the peak is not
      clamped into a number: returns ``(None, "no_reliable_clock")``.
      A frequency outside the band is never returned, and an edge
      peak is never promoted.

    Raises ``ValueError`` (``"short_signal"``) on fewer than 8
    samples, (``"bad_timebase"``) on unusable times, (``"bad_band"``)
    on an unusable band, and (``"peak_at_band_edge"``) when the
    sampling cannot place a single bin strictly inside the band (the
    peak would be pinned at the edge by construction).
    """
    import numpy as np

    try:
        values = [float(v) for v in signal]
        moments = [float(v) for v in t]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_signal: signal and t must hold numbers: "
            f"{exc}") from exc
    if len(values) != len(moments) or not values:
        raise ValueError("bad_signal: signal and t need the same "
                         "non-empty length")
    if len(values) < 8:
        raise ValueError(
            f"short_signal: need at least 8 samples, got {len(values)}")
    if not all(math.isfinite(v) for v in values + moments):
        raise ValueError("bad_signal: signal and t must be finite")
    gaps = np.diff(np.asarray(moments))
    if len(gaps) == 0 or not bool(np.all(gaps > 0)):
        raise ValueError("bad_timebase: t must be strictly increasing")
    low, high = _band_of(band_hz)

    dt = float(np.median(gaps))
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("bad_timebase: t has no positive median step")
    window = int(round(_median_window_s() / dt))
    window = max(3, window)
    if window % 2 == 0:
        window += 1
    detrended = _detrend_median(values, min(
        window, len(values) if len(values) % 2 else len(values) - 1))
    spectrum = np.fft.rfft(detrended)
    freqs = np.fft.rfftfreq(len(values), d=dt)
    power = (spectrum.real ** 2 + spectrum.imag ** 2) / len(values)
    inside = [k for k, f in enumerate(freqs) if low < f < high]
    if not inside:
        raise ValueError(
            "peak_at_band_edge: no spectrum bin lies strictly inside "
            f"({low}, {high}) Hz at this sampling")
    best = max(inside, key=lambda k: power[k])
    step = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 0.0
    peak_guess = float(freqs[best])
    if (best == inside[0] or best == inside[-1]
            or peak_guess - low <= 1.5 * step
            or high - peak_guess <= 1.5 * step):
        return None, "no_reliable_clock"

    def _nearest_power(freq):
        if freq <= 0:
            return 0.0
        near = min(range(len(freqs)),
                   key=lambda k: abs(freqs[k] - freq))
        return float(power[near])

    peak = float(freqs[best])
    power_peak = float(power[best])
    power_double = _nearest_power(2.0 * peak)
    power_half = _nearest_power(0.5 * peak)
    result = {"peak_hz": peak, "as_step_hz": peak,
              "as_stride_hz": peak / 2.0, "alt_step_hz": 2.0 * peak,
              "harmonic_evidence": {
                  "power_at_peak": power_peak,
                  "power_at_double": power_double,
                  "power_at_half": power_half,
                  "ratio_double": (power_double / power_peak
                                   if power_peak > 0 else 0.0),
                  "ratio_half": (power_half / power_peak
                                 if power_peak > 0 else 0.0)},
              "band_hz": [low, high]}
    return result, None


def _as_pair(raw, field):
    """A ``[lo, hi]`` pair from a list/tuple or a ``{min, max}``
    mapping, or ``ValueError`` naming ``field``."""
    if isinstance(raw, dict):
        keys = ("min", "max") if "min" in raw or "max" in raw else (
            ("lo", "hi") if "lo" in raw or "hi" in raw else (None,
                                                             None))
        if keys[0] is None:
            raise ValueError(
                f"bad_{field}: {field} must be [lo, hi] or "
                f"{{min, max}}, got {raw!r}")
        try:
            pair = [float(raw[keys[0]]), float(raw[keys[1]])]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"bad_{field}: {field} carries no usable pair: "
                f"{exc}") from exc
    else:
        try:
            pair = [float(raw[0]), float(raw[1])]
        except (KeyError, IndexError, TypeError,
                ValueError) as exc:
            raise ValueError(
                f"bad_{field}: {field} must be [lo, hi] or "
                f"{{min, max}}, got {raw!r}: {exc}") from exc
        if len(list(raw)) != 2:
            raise ValueError(
                f"bad_{field}: {field} must hold two numbers, got "
                f"{raw!r}")
    low, high = pair
    if not (math.isfinite(low) and math.isfinite(high)):
        raise ValueError(
            f"bad_{field}: {field} must be finite, got {raw!r}")
    if not 0 <= low < high:
        raise ValueError(
            f"bad_{field}: {field} needs 0 <= lo < hi, got {raw!r}")
    return [low, high]


def clock_evidence(rate, signal_description, interpretation,
                   natural_range_hz, natural_range_source, band_hz,
                   window_frames, method):
    """The evidence ``clock`` object, built by the library (part 09 §7).

    ``rate`` is :func:`step_rate`'s result — either its result dict
    or its ``(result, flag)`` pair. A ``None`` result, or a pair
    whose flag is not None (the band-edge ``"no_reliable_clock"``),
    raises ``ValueError`` (``"no_reliable_clock"``): an edge peak is
    never promoted into a clock. ``interpretation`` picks the
    reading: ``"step"`` reports ``as_step_hz``, ``"stride"`` reports
    ``as_stride_hz`` — R-C3's ambiguity stays an explicit choice.

    ``natural_range_hz`` is stored as ``[lo, hi]``; a ``{min, max}``
    mapping (the shape wall runs 9 and 10 wrote) is accepted and
    converted. ``natural_range_source`` is ``{"url", "quote"}``.
    ``band_hz`` is the search band, stored as ``[lo, hi]``.
    ``window_frames`` is the analysed window's frame count (a
    positive int) and ``method`` names the estimation procedure (a
    nonempty string); both are validated here and feed the quoted
    σ, not stored — the contract's ``clock`` shape carries no other
    fields.

    The quoted ``measured_rate_sigma_hz`` is half the search-band
    width spread over ``√window_frames`` independent bins: a
    resolution term from the window the peak was picked in, so longer
    windows quote tighter clocks.

    ``signal_description`` says what was timed (for example the
    lowest-thirty-percent width signal). Every parameter is
    required: a missing one raises ``ValueError`` naming that field
    (``"rate"``, ``"signal_description"``, ``"interpretation"``,
    ``"natural_range_hz"``, ``"natural_range_source"``,
    ``"band_hz"``, ``"window_frames"``, ``"method"``).

    Returns exactly the evidence ``clock`` shape (part 12):
    ``signal_description``, ``measured_rate_hz``,
    ``measured_rate_sigma_hz``, ``interpretation``, ``band_hz``,
    ``natural_range_hz``, ``natural_range_source`` — nothing more,
    so it validates against the contract's ``clock`` schema.
    """
    flag = None
    if isinstance(rate, (list, tuple)) and len(rate) == 2 and (
            rate[1] is None or isinstance(rate[1], str)):
        result, flag = rate
    else:
        result = rate
    if flag is not None or result is None:
        raise ValueError(
            "no_reliable_clock: the clock has no reliable rate; "
            "submit a null clock with a clock_absent_reason, not "
            "this")
    if not isinstance(result, dict):
        raise ValueError(
            f"bad_rate: rate must be step_rate's result dict, got "
            f"{type(result).__name__}")
    if not isinstance(signal_description, str) or not (
            signal_description.strip()):
        raise ValueError(
            "bad_signal_description: signal_description is missing: "
            "say what was timed")
    if interpretation not in ("step", "stride"):
        raise ValueError(
            "bad_interpretation: interpretation must be 'step' or "
            f"'stride', got {interpretation!r}")
    natural = _as_pair(natural_range_hz, "natural_range_hz")
    if natural_range_source is None or not isinstance(
            natural_range_source, dict):
        raise ValueError(
            "bad_natural_range_source: natural_range_source is "
            "missing: it needs {url, quote}")
    url = natural_range_source.get("url")
    quote = natural_range_source.get("quote")
    if not isinstance(url, str) or not url.strip():
        raise ValueError(
            "bad_natural_range_source: natural_range_source.url is "
            "missing: the range needs its source page")
    if not isinstance(quote, str) or not quote.strip():
        raise ValueError(
            "bad_natural_range_source: natural_range_source.quote "
            "is missing: the range needs its verbatim quote")
    band = _as_pair(band_hz, "band_hz")
    try:
        frames = int(window_frames)
        whole = float(window_frames) == float(frames)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "bad_window_frames: window_frames is missing: the "
            f"analysed window's frame count: {exc}") from exc
    if isinstance(window_frames, bool) or not whole or frames <= 0:
        raise ValueError(
            "bad_window_frames: window_frames must be a positive "
            f"frame count, got {window_frames!r}")
    if not isinstance(method, str) or not method.strip():
        raise ValueError(
            "bad_method: method is missing: name the estimation "
            "procedure")
    key = "as_step_hz" if interpretation == "step" else "as_stride_hz"
    try:
        measured = float(result[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"bad_rate: rate carries no {key!r}: pass step_rate's "
            f"result: {exc}") from exc
    if not math.isfinite(measured) or measured <= 0:
        raise ValueError(
            f"bad_rate: rate[{key!r}] must be a positive rate, got "
            f"{result.get(key)!r}")
    if not band[0] < measured < band[1]:
        raise ValueError(
            f"bad_rate: rate {measured!r} Hz lies outside its band "
            f"{band}: a frequency outside the band is never "
            "returned (R-C2)")
    sigma = (band[1] - band[0]) / (2.0 * math.sqrt(float(frames)))
    return {"signal_description": signal_description.strip(),
            "measured_rate_hz": float(measured),
            "measured_rate_sigma_hz": float(sigma),
            "interpretation": interpretation,
            "band_hz": band,
            "natural_range_hz": natural,
            "natural_range_source": {"url": url.strip(),
                                     "quote": quote.strip()}}
