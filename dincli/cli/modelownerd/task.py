import os
import typer
from pathlib import Path

from dincli.cli.utils import resolve_task_coordinator_address

task_app = typer.Typer(help="task-level commands")


@task_app.command("create-task-dir")
def create_task_dir(ctx: typer.Context, task_coordinator_address: str = typer.Option(None, "--taskCoordinator", help="Task coordinator address")):

    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console()
    task_coordinator_address = resolve_task_coordinator_address(
        effective_network, task_coordinator_address, console
    )

    task_dir = Path(os.getcwd()) / 'tasks' / effective_network.lower() / task_coordinator_address
    os.makedirs(task_dir, exist_ok=True)

    console.print(f"[bold green]Task directory created successfully![/bold green]")
    console.print(f"[cyan]Task directory:[/cyan] {task_dir}")


@task_app.command("cache-default-manifest-services")
def cache_default_manifest_services(
    ctx: typer.Context,
    task_coordinator_address: str = typer.Option(None, "--taskCoordinator", help="Task coordinator address"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console()
    task_coordinator_address = resolve_task_coordinator_address(
        effective_network, task_coordinator_address, console
    )
    # TODO: implement caching of default manifest services
    console.print("[yellow]cache-default-manifest-services not yet implemented.[/yellow]")
