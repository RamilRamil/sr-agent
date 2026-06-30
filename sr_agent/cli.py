from __future__ import annotations

import sys
from pathlib import Path

import click

from sr_agent.config import config
from sr_agent.io.input_val import InputValidationError, validate_audit_input
from sr_agent.models.audit import AuditInput, AuditSession, Principal


@click.group()
def cli() -> None:
    """SR-agent: memory-injection-resistant smart contract auditor."""


@cli.command()
@click.argument("path_or_address", required=False)
@click.option("--path", "-p", type=click.Path(), help="Path to .sol files directory")
@click.option("--address", "-a", help="EIP-55 contract address for on-chain audit")
@click.option("--exclude", multiple=True, type=click.Path(), help="Paths to exclude")
@click.option("--focus", multiple=True, type=click.Path(), help="Restrict to these files")
@click.option("--no-imports", is_flag=True, help="Exclude OpenZeppelin/library imports from SIG")
@click.option("--output", "-o", type=click.Path(), default="audit-report.md")
@click.option("--project-id", default=None, help="Override project ID (default: derived from path)")
@click.option("--resume", "--resume-session", default=None, help="Resume a session by ID")
def audit(
    path_or_address: str | None,
    path: str | None,
    address: str | None,
    exclude: tuple[str, ...],
    focus: tuple[str, ...],
    no_imports: bool,
    output: str,
    project_id: str | None,
    resume: str | None,
) -> None:
    """Run a security audit on a smart contract codebase or on-chain address."""

    # Resolve positional arg
    if path_or_address:
        if path_or_address.startswith("0x"):
            address = path_or_address
        else:
            path = path_or_address

    audit_path = Path(path) if path else None
    derived_project_id = project_id or (audit_path.name if audit_path else address or "unknown")

    principal = Principal(
        user_id="cli-user",
        platform="cli",
        project_id=derived_project_id,
    )

    audit_input = AuditInput(
        path=audit_path,
        address=address,
        exclude_paths=[Path(e) for e in exclude],
        focus_files=[Path(f) for f in focus],
        include_imports=not no_imports,
        principal=principal,
        resume_session_id=resume,
    )

    try:
        validate_audit_input(audit_input, audit_root=Path("."))
    except InputValidationError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    click.echo(f"Starting audit for project '{derived_project_id}'…")

    if audit_path is None:
        click.echo(
            "The relay pipeline needs a local path; address-based audit is not "
            "yet supported.", err=True,
        )
        sys.exit(2)

    from sr_agent.io.progress import ProgressStream
    from sr_agent.memory.episodic import EpisodicMemory
    from sr_agent.orchestrator.pipeline import start_audit

    memory = EpisodicMemory(config.memory_root, config.secret_key)
    relay_dir = config.relay_root
    runs_dir = config.relay_root / "runs"

    result = start_audit(
        audit_input, audit_path, memory, relay_dir, runs_dir,
        output=output, progress=ProgressStream(),
    )

    if result.status == "paused":
        click.echo(f"Stage 1 done. {result.pending} target(s) need analysis via relay:")
        click.echo("  1. sr-agent relay --list                      # pending request ids")
        click.echo("  2. sr-agent relay --show <id>                 # copy into Claude")
        click.echo("  3. sr-agent relay --respond <id> <file>       # submit each answer")
        click.echo(f"  4. sr-agent resume {result.session_id}")
        sys.exit(0)

    click.echo(f"Audit complete: {result.findings_count} finding(s) → {result.report_path}")
    sys.exit(0)


@cli.command("resume")
@click.argument("session_id")
def resume_cmd(session_id: str) -> None:
    """Resume a paused audit: ingest relay responses, finish the report."""
    from sr_agent.io.progress import ProgressStream
    from sr_agent.memory.episodic import EpisodicMemory
    from sr_agent.orchestrator.pipeline import resume_audit

    memory = EpisodicMemory(config.memory_root, config.secret_key)
    relay_dir = config.relay_root
    runs_dir = config.relay_root / "runs"

    try:
        result = resume_audit(session_id, memory, relay_dir, runs_dir, progress=ProgressStream())
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    if result.status == "paused":
        click.echo(f"Still waiting on {result.pending} response(s). Run `sr-agent relay --list`.")
        sys.exit(0)

    click.echo(f"Audit complete: {result.findings_count} finding(s) → {result.report_path}")
    sys.exit(0)


@cli.command("demo-attack")
@click.option("--scenario", default=None, help="Run a single scenario by ID (e.g. MI-001)")
@click.option("--no-baseline", is_flag=True, help="Skip baseline (unprotected) measurement")
@click.option("--output", "-o", default=None, help="Write JSON report to file")
def demo_attack(scenario: str | None, no_baseline: bool, output: str | None) -> None:
    """Demonstrate Memory Injection attack scenarios and verify protection.

    Runs 5 reproducible MI attack scenarios from 2503.16248v3.
    Reports ASR (Attack Success Rate) with and without protection.
    Exits 0 if protected ASR = 0, exits 1 if any attack succeeded.
    """
    import json
    from tests.security.mi_scenarios import SCENARIOS, TEST_SECRET, run_scenario, measure_asr
    from sr_agent.memory.episodic import EpisodicMemory
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        memory = EpisodicMemory(Path(tmp), TEST_SECRET)

        scenarios_to_run = SCENARIOS
        if scenario:
            scenarios_to_run = [s for s in SCENARIOS if s.scenario_id == scenario]
            if not scenarios_to_run:
                click.echo(f"Unknown scenario: {scenario}", err=True)
                sys.exit(2)

        click.echo("\n── SR-agent Memory Injection Demo ──────────────────────────")
        click.echo(f"Running {len(scenarios_to_run)} scenario(s)\n")

        report = {"scenarios": [], "protected_asr": 0.0, "baseline_asr": None}
        any_failed = False

        for s in scenarios_to_run:
            protected_result = run_scenario(s, memory, protected=True)
            status = "BLOCKED ✓" if protected_result.blocked else "LEAKED ✗"
            click.echo(f"  [{s.scenario_id}] {s.attack_type.value:<35} {status}")
            if not protected_result.blocked:
                click.echo(f"           → {protected_result.block_reason}", err=True)
                any_failed = True

            entry = {
                "scenario_id": s.scenario_id,
                "attack_type": s.attack_type.value,
                "blocked": protected_result.blocked,
                "block_reason": protected_result.block_reason,
            }

            if not no_baseline:
                baseline_result = run_scenario(s, memory, protected=False)
                entry["baseline_would_succeed"] = baseline_result.baseline_would_succeed

            report["scenarios"].append(entry)

        protected_asr = measure_asr(scenarios_to_run, memory, protected=True)
        report["protected_asr"] = protected_asr

        click.echo(f"\nProtected ASR:  {protected_asr:.0%}  (target ≤ 5%)")

        if not no_baseline:
            baseline_asr = measure_asr(scenarios_to_run, memory, protected=False)
            report["baseline_asr"] = baseline_asr
            differential = baseline_asr - protected_asr
            click.echo(f"Baseline ASR:   {baseline_asr:.0%}  (expected ≥ 40%)")
            click.echo(f"Differential:   {differential:.0%}  (target ≥ 40pp)")

        click.echo("─" * 52)

        if output:
            Path(output).write_text(json.dumps(report, indent=2))
            click.echo(f"Report written to {output}")

        sys.exit(1 if any_failed else 0)


@cli.command("memory")
@click.argument("subcommand", type=click.Choice(["list", "show", "verify"]))
@click.option("--project-id", required=True)
@click.option("--target", default=None)
def memory_cmd(subcommand: str, project_id: str, target: str | None) -> None:
    """Inspect or verify episodic memory records."""
    from sr_agent.memory.episodic import EpisodicMemory

    mem = EpisodicMemory(config.memory_root, config.secret_key)

    if subcommand == "list":
        root = config.memory_root / project_id
        if not root.exists():
            click.echo("No memory found for this project.")
            return
        for f in root.glob("*.jsonl"):
            click.echo(f.stem)

    elif subcommand == "verify":
        report = mem.verify_integrity(project_id)
        for target_stem, (t_total, t_valid, t_invalid) in sorted(report.per_target.items()):
            marker = "OK" if t_invalid == 0 else f"{t_invalid} INVALID"
            click.echo(f"  {target_stem}: {t_valid}/{t_total} valid  [{marker}]")
        click.echo(
            f"Total: {report.valid}/{report.total} valid, {report.invalid} invalid"
        )
        sys.exit(1 if report.has_invalid else 0)

    elif subcommand == "show" and target:
        records = mem.load(project_id, target)
        for r in records:
            click.echo(r.model_dump_json(indent=2))


@cli.command("confirm")
@click.argument("confirmation_id")
@click.option("--approve", is_flag=True, help="Approve the pending irreversible action")
@click.option("--reject", is_flag=True, help="Reject the pending irreversible action")
@click.option("--show", is_flag=True, help="Show the pending action details")
def confirm_cmd(confirmation_id: str, approve: bool, reject: bool, show: bool) -> None:
    """Approve, reject, or inspect a pending out-of-band confirmation.

    This is the out-of-band channel: it runs as a separate process from the
    agent loop, so the agent can never approve its own irreversible actions.
    """
    import json
    from sr_agent.orchestrator.confirmation import load_request, resolve_confirmation

    confirmations_dir = config.confirmations_root

    if show:
        try:
            req = load_request(confirmation_id, confirmations_dir)
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(2)
        click.echo(json.dumps(req, indent=2))
        return

    if approve == reject:  # both flags or neither
        click.echo("Specify exactly one of --approve / --reject (or --show).", err=True)
        sys.exit(2)

    try:
        status = resolve_confirmation(confirmation_id, confirmations_dir, approve=approve)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(2)

    click.echo(f"Confirmation {confirmation_id}: {status.value}")


@cli.command("relay")
@click.argument("request_id", required=False)
@click.option("--show", is_flag=True, help="Print the request packet to copy into Claude")
@click.option("--respond", "respond_file", default=None, type=click.Path(),
              help="Ingest a saved Claude response file for REQUEST_ID")
@click.option("--list", "list_flag", is_flag=True, help="List requests awaiting a response")
def relay_cmd(request_id: str | None, show: bool, respond_file: str | None, list_flag: bool) -> None:
    """Manual LLM relay: show a request, submit a response, or list pending.

    Relayed responses are external_llm_output — carrying a file does not grant
    human authority (use `sr-agent confirm` for that).
    """
    from sr_agent.orchestrator.relay import (
        ingest_response, list_pending, read_request, save_response,
    )
    relay_dir = config.relay_root

    if list_flag:
        pending = list_pending(relay_dir)
        if not pending:
            click.echo("No pending relay requests.")
        for rid in pending:
            click.echo(rid)
        return

    if not request_id:
        click.echo("A REQUEST_ID is required (or use --list).", err=True)
        sys.exit(2)

    if show:
        try:
            click.echo(read_request(request_id, relay_dir))
        except FileNotFoundError as e:
            click.echo(f"Error: {e}", err=True)
            sys.exit(2)
        return

    if respond_file:
        text = Path(respond_file).read_text(encoding="utf-8")
        save_response(request_id, relay_dir, text)
        result = ingest_response(request_id, relay_dir, response_text=text)
        if result.needs_resend:
            click.echo(
                f"Response saved but unparseable — please resend. "
                f"({'; '.join(result.errors)})",
                err=True,
            )
            sys.exit(1)
        click.echo(
            f"Response saved: {len(result.findings)} finding(s) parsed, "
            f"{len(result.errors)} error(s)."
        )
        for err in result.errors:
            click.echo(f"  ! {err}", err=True)
        return

    click.echo("Specify one of --show / --respond <file> / --list.", err=True)
    sys.exit(2)
