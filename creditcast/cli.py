"""CreditCast CLI — the reproducible lifecycle as one command surface.

python -m creditcast.cli generate     # synthetic GSE panels -> Bronze
python -m creditcast.cli pipeline      # Bronze -> Silver -> Gold
python -m creditcast.cli split         # show the out-of-time split
python -m creditcast.cli train         # fit + calibrate PD/LGD, score OOT
python -m creditcast.cli validate      # Gini/KS/calibration/PSI -> report
python -m creditcast.cli governance    # SHAP, reason codes, fairness, card
python -m creditcast.cli monitor       # PSI drift vs training baseline
python -m creditcast.cli gates         # CI performance gates (exit code)
python -m creditcast.cli all           # the whole thing; registers a version if gates pass
python -m creditcast.cli register      # snapshot the current models as a new version
python -m creditcast.cli models list   # registered versions + metrics (* = active)
python -m creditcast.cli models use v0002   # roll back / forward to a version
"""

from __future__ import annotations

import json

import typer

app = typer.Typer(add_completion=False, help="CreditCast lifecycle CLI")
models_app = typer.Typer(add_completion=False, help="Registered model versions")
app.add_typer(models_app, name="models")


@app.command()
def generate():
    """Generate synthetic GSE-schema panels into Bronze."""
    from creditcast.pipeline.generate import generate as gen

    gen()


@app.command()
def pipeline():
    """Build Silver (point-in-time target) then Gold (feature matrix)."""
    from creditcast.pipeline.gold import build_gold
    from creditcast.pipeline.silver import build_silver

    build_silver()
    build_gold()


@app.command()
def split():
    """Print the out-of-time split summary."""
    from creditcast.pipeline.split import make_split

    typer.echo(json.dumps(make_split().summary(), indent=2))


@app.command()
def train():
    """Fit + calibrate scorecard, challenger, LGD; score the OOT test set."""
    from creditcast.train import train_all

    train_all()


@app.command()
def validate():
    """Run the validation suite and write the report."""
    from creditcast.validation.report import build_report

    r = build_report()
    typer.echo(json.dumps(r["benchmark"], indent=2, default=float))


@app.command()
def governance():
    """SHAP global, fairness, decision policy, adverse-action card."""
    from creditcast.governance.report import build_governance

    build_governance()


@app.command()
def monitor():
    """PSI/CSI drift of the OOT batch vs the training baseline."""
    from creditcast.monitoring.drift import run_monitoring

    r = run_monitoring()
    typer.echo(
        f"score PSI={r['score_psi']} ({r['score_status']}) | "
        f"alerts={len(r['alerts'])} | healthy={r['healthy']}"
    )


@app.command()
def lifetime():
    """Lifetime PD (survival model) and IFRS 9 staging of the out-of-time book."""
    from creditcast.lifetime import build_lifetime

    r = json.loads(build_lifetime().read_text())
    st = {s["stage"]: s for s in r["staging"]["stages"]}
    typer.echo(
        f"[lifetime] mean PD 12m {r['lifetime_pd']['mean_12m']:.2%} -> lifetime "
        f"{r['lifetime_pd']['mean_lifetime']:.2%} | stages 1/2/3: "
        f"{st[1]['loans']}/{st[2]['loans']}/{st[3]['loans']} | ECL {r['staging']['total_ecl']:,.0f}"
    )


@app.command()
def stress():
    """Macro stress test: EL, PD by band and approval rate per scenario."""
    from creditcast.stress import stress_report

    report = json.loads(stress_report().read_text())
    for name, sc in report["scenarios"].items():
        typer.echo(
            f"[stress] {name:<17} PD {sc['mean_pd']:.2%}  EL {sc['el_bps']:.0f} bps "
            f"({sc['el_vs_baseline_pct']:+.0f}% vs baseline)  approve {sc['approval_rate']:.0%}"
        )


@app.command()
def gates():
    """Run CI performance gates; non-zero exit on failure."""
    from creditcast.eval.gates import main as gate_main

    raise typer.Exit(code=gate_main())


@app.command(name="all")
def run_all():
    """End-to-end: generate -> pipeline -> train -> validate -> governance -> monitor
    -> lifetime -> stress -> gates."""
    generate()
    pipeline()
    train()
    validate()
    governance()
    monitor()
    lifetime()
    stress()
    from creditcast.eval.gates import main as gate_main

    code = gate_main()
    if code == 0:  # only models that pass the gates become a version
        register(note="cli all")
    else:
        typer.echo("[registry] gates failed - not registering this run")
    raise typer.Exit(code=code)


@app.command()
def register(note: str = typer.Option("", help="Free-text note stored with the version")):
    """Snapshot the current working models as a new registered version."""
    from creditcast.eval.gates import run_gates
    from creditcast.registry import register as do_register

    try:
        passed, _ = run_gates()
    except FileNotFoundError:
        passed = None  # no validation report yet
    m = do_register(gates_passed=passed, note=note)
    verb = "already registered as" if m.get("reused") else "registered"
    typer.echo(
        f"[registry] {verb} {m['version']} (fingerprint {m['fingerprint']}, "
        f"gini {m['metrics'].get('gini') or float('nan'):.4f})"
    )


def _fmt(x, spec: str) -> str:
    return format(x, spec) if isinstance(x, (int, float)) else "-"


@models_app.command("list")
def models_list():
    """List registered versions with their headline metrics."""
    from creditcast.registry import active_version, list_versions

    versions, active = list_versions(), active_version()
    if not versions:
        typer.echo("no registered versions yet - run `python -m creditcast.cli all`")
        return
    typer.echo(
        f"  {'version':8} {'created (UTC)':20} {'git':12} {'gini':>7} "
        f"{'approval':>9} {'EL bps':>7}  gates"
    )
    for v in versions:
        m = v["metrics"]
        mark = "*" if v["version"] == active else " "
        typer.echo(
            f"{mark} {v['version']:8} {v['created_at'][:19]:20} {v['git_sha'][:12]:12} "
            f"{_fmt(m.get('gini'), '7.4f')} {_fmt(m.get('approval_rate'), '9.1%')} "
            f"{_fmt(m.get('el_rate_bps'), '7.1f')}  {v.get('gates_passed')}"
        )


@models_app.command("use")
def models_use(version: str):
    """Serve a registered version (restores its files; restart the API after)."""
    from creditcast.registry import RegistryError, activate

    try:
        m = activate(version)
    except RegistryError as e:
        typer.echo(f"[registry] {e}", err=True)
        raise typer.Exit(code=1) from e
    typer.echo(
        f"[registry] now serving {m['version']} (fingerprint {m['fingerprint']}). "
        "Restart the API to load it."
    )


if __name__ == "__main__":
    app()
