#!/usr/bin/env python3
"""Offline analysis for AMR LKS session 4 (no hardware, no actuation).

Session 4 closes two questions left open by session 3 (``docs/sesi_3.md``):

1. ``C_eff`` -- the distance the robot actually travels per wheel revolution.
   Session 3 measured ``20.72 +/- 1.84 cm`` from three 3-revolution roll-outs,
   so the relative error (8,9 %) is as large as the effect being investigated.
2. Which model explains the floor data -- a constant efficiency ratio
   (``d = r * u * C * T``) or a fixed distance offset (``d = u * C * T - k``).

This script only computes statistics over numbers that were already measured
by hand on the robot. It never opens a serial port and never sends a motor
command; the actuating side of session 4 is ``scripts/wheel_test.py``.

INPUT
-----
A JSON file with the recorded measurements::

    {
      "rollout": {
        "rotations_per_trial": 10,
        "trials": [{"trial": 1, "distance_cm": 207.0}]
      },
      "duration": {
        "u_rps": 0.6,
        "trials": [{"trial": 1, "duration_s": 3, "distance_cm": 33.0}]
      },
      "freewheel": {
        "u_rps": 0.6,
        "trials": [{"trial": 1, "rotations": 20, "seconds": 33.9}]
      }
    }

A trial may carry its own ``u_rps`` (for example the older session-3 points at
0,3 and 1,0 rps), which overrides the section default.

Any section may be missing; the script then reports "data belum ada" for it
instead of failing, so a partial session can still be analysed.

USAGE
-----
    python scripts/analyze_sesi4.py data.json
    python scripts/analyze_sesi4.py data.json --c-eff 20.72 --c-eff-sd 0.58

Exit codes: 0 = analysis printed, 2 = input file unreadable or invalid JSON.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Working values carried over from session 3 (docs/sesi_3.md).
C_EFF_PRIOR_CM = 20.72
C_EFF_PRIOR_SD_CM = 1.84
RATIO_PRIOR = 0.885
OFFSET_PRIOR_CM = 4.89

# Decision thresholds for the 9 s trials (session 4 brief).
NINE_SECOND_RATIO_MAX_CM = 101.0
NINE_SECOND_OFFSET_MIN_CM = 105.0

# Session 3 ground rate at u = 0,6 rps: 33,0 cm in 3 s over C_eff = 20,72 cm.
GROUND_RPS_PRIOR = 33.0 / 3.0 / C_EFF_PRIOR_CM

# Measurement uncertainty of a single ruler reading on the floor.
RULER_SIGMA_CM = 1.0


def sample_sd(values: list[float]) -> float:
    """Sample standard deviation (n-1); 0,0 for a single sample."""
    return statistics.stdev(values) if len(values) > 1 else 0.0


def sem(values: list[float]) -> float:
    """Standard error of the mean; 0,0 for a single sample."""
    sd = sample_sd(values)
    return sd / len(values) ** 0.5 if values else 0.0


def fmt(value: float, digits: int = 2) -> str:
    """Format a number with a comma as the decimal separator (repo convention)."""
    return f"{value:.{digits}f}".replace(".", ",")


@dataclass
class RolloutResult:
    """Statistics of the roll-out trials, which measure ``C_eff`` directly."""

    c_eff_cm: list[float] = field(default_factory=list)
    mean_cm: float = 0.0
    sd_cm: float = 0.0
    median_cm: float = 0.0
    cv_percent: float = 0.0
    sigma_low_cm: float = 0.0
    sigma_high_cm: float = 0.0
    sem_cm: float = 0.0


def analyse_rollout(distances_cm: list[float], rotations: int) -> RolloutResult:
    """Turn roll-out distances into ``C_eff`` statistics."""
    if rotations <= 0:
        raise ValueError("rotations must be positive")
    c_eff = [d / rotations for d in distances_cm]
    if not c_eff:
        return RolloutResult()
    mean = statistics.fmean(c_eff)
    sd = sample_sd(c_eff)
    return RolloutResult(
        c_eff_cm=c_eff,
        mean_cm=mean,
        sd_cm=sd,
        median_cm=statistics.median(c_eff),
        cv_percent=100.0 * sd / mean if mean else 0.0,
        sigma_low_cm=mean - sd,
        sigma_high_cm=mean + sd,
        sem_cm=sem(c_eff),
    )


@dataclass
class Fit:
    """Result of fitting one distance model to the duration trials."""

    name: str
    params: dict[str, float]
    predictions: list[float]
    residuals: list[float]
    rms_cm: float
    chi2: float
    dof: int


def _rms(residuals: list[float], n_params: int) -> float:
    if len(residuals) <= n_params:
        return 0.0
    return (sum(r * r for r in residuals) / (len(residuals) - n_params)) ** 0.5


def _chi2(residuals: list[float], sigma: float) -> float:
    return sum((r / sigma) ** 2 for r in residuals)


def fit_ratio(x_cm: list[float], y_cm: list[float], sigma: float = RULER_SIGMA_CM) -> Fit:
    """Fit ``y = r * x`` (constant efficiency ratio)."""
    denom = sum(x * x for x in x_cm)
    r = (sum(x * y for x, y in zip(x_cm, y_cm, strict=True)) / denom) if denom else 0.0
    preds = [r * x for x in x_cm]
    residuals = [y - p for y, p in zip(y_cm, preds, strict=True)]
    return Fit(
        name="rasio konstan  d = r * u * C * T",
        params={"r": r},
        predictions=preds,
        residuals=residuals,
        rms_cm=_rms(residuals, 1),
        chi2=_chi2(residuals, sigma),
        dof=len(y_cm) - 1,
    )


def fit_offset(x_cm: list[float], y_cm: list[float], sigma: float = RULER_SIGMA_CM) -> Fit:
    """Fit ``y = x - k`` (fixed distance offset, full steady-state speed)."""
    k = statistics.fmean([x - y for x, y in zip(x_cm, y_cm, strict=True)]) if x_cm else 0.0
    preds = [x - k for x in x_cm]
    residuals = [y - p for y, p in zip(y_cm, preds, strict=True)]
    return Fit(
        name="offset tetap  d = u * C * T - k",
        params={"k_cm": k},
        predictions=preds,
        residuals=residuals,
        rms_cm=_rms(residuals, 1),
        chi2=_chi2(residuals, sigma),
        dof=len(y_cm) - 1,
    )


def fit_joint(x_cm: list[float], y_cm: list[float], sigma: float = RULER_SIGMA_CM) -> Fit:
    """Fit ``y = r * x + b`` (ratio *and* offset free), reported as ``k = -b``."""
    n = len(x_cm)
    if n < 2:
        raise ValueError("joint fit needs at least two points")
    sum_x = sum(x_cm)
    sum_y = sum(y_cm)
    sum_xx = sum(x * x for x in x_cm)
    sum_xy = sum(x * y for x, y in zip(x_cm, y_cm, strict=True))
    denom = n * sum_xx - sum_x * sum_x
    r = (n * sum_xy - sum_x * sum_y) / denom if denom else 0.0
    b = (sum_y - r * sum_x) / n
    preds = [r * x + b for x in x_cm]
    residuals = [y - p for y, p in zip(y_cm, preds, strict=True)]
    return Fit(
        name="rasio + offset  d = r * u * C * T - k",
        params={"r": r, "k_cm": -b},
        predictions=preds,
        residuals=residuals,
        rms_cm=_rms(residuals, 2),
        chi2=_chi2(residuals, sigma),
        dof=n - 2,
    )


def decide(nine_second_mean_cm: float) -> str:
    """Apply the session-4 decision rule to the 9 s mean distance."""
    if nine_second_mean_cm <= NINE_SECOND_RATIO_MAX_CM:
        return "RATIO"
    if nine_second_mean_cm >= NINE_SECOND_OFFSET_MIN_CM:
        return "OFFSET"
    return "INCONCLUSIVE"


def c_free_check(
    nine_mean_cm: float,
    three_mean_cm: float,
    nine_sem_cm: float,
    three_sem_cm: float,
) -> tuple[float, float]:
    """Return ``(D, sigma_D)`` for ``D = Y9 - 3 * Y3``.

    The ratio model predicts ``D = 0`` and the offset model ``D = 2k``, and
    neither prediction contains ``C_eff`` -- so this comparison is immune to
    the ``C_eff`` uncertainty that the duration predictions depend on.
    """
    difference = nine_mean_cm - 3.0 * three_mean_cm
    sigma = (nine_sem_cm**2 + 9.0 * three_sem_cm**2) ** 0.5
    return difference, sigma


def report_rollout(result: RolloutResult, rotations: int) -> None:
    print("=" * 72)
    print(f"EKSPERIMEN 1 - ROLL-OUT {rotations} PUTARAN x N (robot mati, didorong)")
    print("=" * 72)
    if not result.c_eff_cm:
        print("  data belum ada")
        return
    for index, value in enumerate(result.c_eff_cm, start=1):
        print(f"  trial {index}: C_eff = {fmt(value)} cm")
    print(f"  mean   = {fmt(result.mean_cm)} cm")
    print(f"  sd     = {fmt(result.sd_cm)} cm")
    print(f"  median = {fmt(result.median_cm)} cm")
    print(f"  1 sigma= {fmt(result.sigma_low_cm)} - {fmt(result.sigma_high_cm)} cm")
    print(f"  CV     = {fmt(result.cv_percent, 1)} %")
    print(f"  SEM    = {fmt(result.sem_cm)} cm")
    prior_cv = 100.0 * C_EFF_PRIOR_SD_CM / C_EFF_PRIOR_CM
    print(f"  acuan sesi 3: {fmt(C_EFF_PRIOR_CM)} +/- {fmt(C_EFF_PRIOR_SD_CM)} cm "
          f"(CV {fmt(prior_cv, 1)} %)")
    if result.cv_percent < 4.0:
        print("  -> galat DIDOMINASI hitung putaran; C_eff siap dipakai.")
    else:
        print("  -> galat TIDAK didominasi hitung putaran; galat berasal dari")
        print("     lintasan dorong / permukaan lantai. Perhatikan konsekuensinya")
        print("     di bawah: prediksi jarak ikut melebar.")


def trial_u(trial: dict[str, float], default_u: float) -> float:
    """Return the commanded speed of a trial (per-trial ``u_rps`` overrides the section default)."""
    return float(trial.get("u_rps", default_u))


def group_trials(
    trials: list[dict[str, float]], default_u: float
) -> dict[tuple[float, float], list[float]]:
    """Group trial distances by ``(u, duration)``."""
    groups: dict[tuple[float, float], list[float]] = {}
    for trial in trials:
        key = (trial_u(trial, default_u), float(trial["duration_s"]))
        groups.setdefault(key, []).append(float(trial["distance_cm"]))
    return groups


def report_duration(
    trials: list[dict[str, float]],
    u_rps: float,
    c_eff_cm: float,
    c_eff_sd_cm: float,
) -> None:
    print()
    print("=" * 72)
    print("EKSPERIMEN 2 - DURASI")
    print("=" * 72)
    if not trials:
        print("  data belum ada")
        return
    groups = group_trials(trials, u_rps)
    for (group_u, duration_s), distances in sorted(groups.items()):
        print(f"  u = {fmt(group_u, 3)} rps, T = {fmt(duration_s, 0)} s : "
              f"trial {', '.join(fmt(d) for d in distances)} cm")
        print(f"      mean = {fmt(statistics.fmean(distances))} cm   "
              f"sd = {fmt(sample_sd(distances))} cm   SEM = {fmt(sem(distances))} cm")

    print()
    print("  Prediksi model (C_eff = " + fmt(c_eff_cm) + " cm, r = "
          + fmt(RATIO_PRIOR, 3) + ", k = " + fmt(OFFSET_PRIOR_CM) + " cm):")
    print(f"  {'u':>6} | {'T':>4} | {'rasio':>9} | {'offset':>9} | {'selisih':>8}")
    for (group_u, duration_s) in sorted(groups):
        x_cm = group_u * c_eff_cm * duration_s
        ratio_pred = RATIO_PRIOR * x_cm
        offset_pred = x_cm - OFFSET_PRIOR_CM
        print(f"  {fmt(group_u, 3):>6} | {fmt(duration_s, 0):>4} | {fmt(ratio_pred):>9} | "
              f"{fmt(offset_pred):>9} | {fmt(offset_pred - ratio_pred):>8}")
    sigma_pred = c_eff_sd_cm / c_eff_cm if c_eff_cm else 0.0
    print(f"  (galat prediksi dari C_eff saja: +/- {fmt(sigma_pred * 100, 1)} % "
          "dari jarak prediksi)")

    for group_u in sorted({key[0] for key in groups}):
        nine = groups.get((group_u, 9.0))
        three = groups.get((group_u, 3.0))
        if not nine:
            continue
        nine_mean = statistics.fmean(nine)
        verdict = decide(nine_mean)
        print()
        print(f"  ATURAN KEPUTUSAN u = {fmt(group_u, 3)} rps "
              f"(mean 9 s = {fmt(nine_mean)} cm):")
        print(f"    <= {fmt(NINE_SECOND_RATIO_MAX_CM, 0)} cm -> model RASIO KONSTAN")
        print(f"    >= {fmt(NINE_SECOND_OFFSET_MIN_CM, 0)} cm -> model OFFSET TETAP")
        print("    di antaranya -> BELUM KONKLUSIF (ulangi / cek video)")
        print(f"    HASIL: {verdict}")
        if three:
            three_mean = statistics.fmean(three)
            difference, sigma_diff = c_free_check(
                nine_mean, three_mean, sem(nine), sem(three)
            )
            print()
            print("  UJI TAMBAHAN TANPA C_eff (selisih durasi):")
            print("    model rasio  -> D = Y9 - 3*Y3 = 0")
            print("    model offset -> D = Y9 - 3*Y3 = +2k = "
                  f"+{fmt(2 * OFFSET_PRIOR_CM)} cm")
            print(f"    terukur      -> D = {fmt(difference)} cm "
                  f"(+/- {fmt(sigma_diff)} cm dari SEM trial)")
            if sigma_diff > 0:
                print(f"    jarak ke rasio  = {fmt(abs(difference) / sigma_diff)} sigma")
                print(f"    jarak ke offset = "
                      f"{fmt(abs(difference - 2 * OFFSET_PRIOR_CM) / sigma_diff)} sigma")
            print("    (uji ini tidak bergantung pada C_eff sama sekali)")


def report_models(
    trials: list[dict[str, float]],
    u_rps: float,
    c_eff_cm: float,
) -> None:
    print()
    print("=" * 72)
    print("PASAL 4 - FIT MODEL PADA DATA DURASI")
    print("=" * 72)
    if len(trials) < 2:
        print("  data belum ada (butuh minimal 2 trial)")
        return
    x_cm = [
        trial_u(trial, u_rps) * c_eff_cm * float(trial["duration_s"]) for trial in trials
    ]
    y_cm = [float(trial["distance_cm"]) for trial in trials]
    for fit in (fit_ratio(x_cm, y_cm), fit_offset(x_cm, y_cm), fit_joint(x_cm, y_cm)):
        params = "  ".join(f"{key} = {fmt(value, 3)}" for key, value in fit.params.items())
        print(f"  {fit.name}")
        print(f"    {params}   rms = {fmt(fit.rms_cm)} cm   "
              f"chi2 = {fmt(fit.chi2)} (dof {fit.dof})")
        for trial, pred, residual in zip(trials, fit.predictions, fit.residuals, strict=True):
            trial_u_rps = trial_u(trial, u_rps)
            trial_duration_s = float(trial["duration_s"])
            print(f"      u={fmt(trial_u_rps, 3)} T={fmt(trial_duration_s, 0)} s  "
                  f"terukur {fmt(float(trial['distance_cm']))} cm  "
                  f"prediksi {fmt(pred)} cm  sisa {fmt(residual)} cm")


def report_freewheel(trials: list[dict[str, float]], u_rps: float, c_eff_cm: float) -> None:
    print()
    print("=" * 72)
    print("EKSPERIMEN 3 - FREE-WHEEL 20 PUTARAN (roda terangkat)")
    print("=" * 72)
    if not trials:
        print("  data belum ada")
        return
    rates = []
    for trial in trials:
        rotations = float(trial["rotations"])
        seconds = float(trial["seconds"])
        rate = rotations / seconds if seconds else 0.0
        rates.append(rate)
        print(f"  trial {int(trial.get('trial', len(rates)))}: {fmt(rotations, 0)} putaran / "
              f"{fmt(seconds)} s = {fmt(rate, 3)} rps")
    mean_rate = statistics.fmean(rates)
    ground_rate = (GROUND_RPS_PRIOR * C_EFF_PRIOR_CM) / c_eff_cm if c_eff_cm else 0.0
    print(f"  mean free-wheel = {fmt(mean_rate, 3)} rps")
    print(f"  perintah        = {fmt(u_rps, 3)} rps")
    print(f"  acuan lantai sesi 3 = {fmt(ground_rate, 3)} rps "
          "(0,531 rps untuk C_eff = 20,72 cm)")
    print()
    if mean_rate < ground_rate - 0.03:
        print("  -> free-wheel LEBIH LAMBAT dari lantai: secara fisis tidak mungkin.")
        print("     Ada yang salah di C_eff atau di pengukuran jarak; jangan")
        print("     menafsirkan sebagai efisiensi.")
    elif abs(mean_rate - ground_rate) <= 0.03:
        print("  -> free-wheel dan lantai praktis sama: selisihnya di dalam noise,")
        print("     jadi efek beban lantai tidak terbukti. Tidak boleh dipakai")
        print("     sebagai faktor kalibrasi.")
    else:
        print("  -> free-wheel lebih cepat dari lantai: efek beban lantai masuk akal.")
    if abs(mean_rate - u_rps) <= 0.05:
        print("  -> free-wheel mendekati perintah: motor mencapai kecepatan perintah")
        print("     tanpa beban; defisit lantai berasal dari beban/slip atau")
        print("     dari start-up (uji video).")
    else:
        print("  -> free-wheel TIDAK mendekati perintah: motor tidak mencapai")
        print("     kecepatan perintah bahkan tanpa beban. Periksa ulang.")


def load_data(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: {path} is not valid JSON: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    if not isinstance(data, dict):
        print("ERROR: top level of the JSON file must be an object", file=sys.stderr)
        raise SystemExit(2)
    return data


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline analysis for session 4.")
    parser.add_argument("data", type=Path, help="JSON file with the recorded measurements")
    parser.add_argument(
        "--c-eff",
        type=float,
        default=C_EFF_PRIOR_CM,
        help=f"C_eff to use for predictions in cm (default {C_EFF_PRIOR_CM})",
    )
    parser.add_argument(
        "--c-eff-sd",
        type=float,
        default=C_EFF_PRIOR_SD_CM,
        help=f"uncertainty of C_eff in cm (default {C_EFF_PRIOR_SD_CM})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = load_data(args.data)

    rollout = data.get("rollout") or {}
    distance = data.get("duration") or {}
    freewheel = data.get("freewheel") or {}

    rotations = int(rollout.get("rotations_per_trial", 10))
    distances_cm = [float(t["distance_cm"]) for t in rollout.get("trials", [])]
    report_rollout(analyse_rollout(distances_cm, rotations), rotations)

    duration_trials = list(distance.get("trials", []))
    u_rps = float(distance.get("u_rps", 0.6))
    report_duration(duration_trials, u_rps, args.c_eff, args.c_eff_sd)
    report_models(duration_trials, u_rps, args.c_eff)

    freewheel_trials = list(freewheel.get("trials", []))
    report_freewheel(freewheel_trials, float(freewheel.get("u_rps", 0.6)), args.c_eff)

    print()
    print("=" * 72)
    print("CATATAN")
    print("=" * 72)
    print("  Script ini hanya menghitung dari angka yang sudah diukur. Ia tidak")
    print("  membuka port serial dan tidak mengirim perintah motor.")
    print("  Data kosong berarti 'belum diukur' - jangan diisi dengan perkiraan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
