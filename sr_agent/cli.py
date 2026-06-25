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

    from sr_agent.memory.episodic import EpisodicMemory
    from sr_agent.orchestrator.loop import OrchestratorLoop

    memory = EpisodicMemory(config.memory_root, config.secret_key)
    session = AuditSession(principal=principal, audit_input=audit_input)

    loop = OrchestratorLoop(session, memory, audit_root=audit_path or Path("."))
    result = loop.run(system_prompt="Perform Stage 1 discovery audit.")

    click.echo(f"Audit complete. Findings: {len(result.findings)}, Stop: {result.stop_reason}")
    sys.exit(0 if result.completed else 1)


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

    elif subcommand in ("show", "verify") and target:
        records = mem.load(project_id, target)
        for r in records:
            click.echo(r.model_dump_json(indent=2))
