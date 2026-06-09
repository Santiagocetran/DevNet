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


@task_app.command("cache-default-artifacts")
def cache_default_artifacts(
    ctx: typer.Context,
    task_coordinator_address: str = typer.Option(None, "--taskCoordinator", help="Task coordinator address"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console()
    task_coordinator_address = resolve_task_coordinator_address(
        effective_network, task_coordinator_address, console
    )

    task_dir = Path(os.getcwd()) / 'tasks' / effective_network.lower() / task_coordinator_address
    if not task_dir.exists():
        console.print(f"[bold red]Task directory not found at {task_dir}[/bold red]")
        console.print(f"[bold yellow]Please create the task directory first using: dincli model-owner task create-task-dir[/bold yellow]")
        raise typer.Exit(1)

    


    # TODO: implement caching of default manifest services
    console.print("[yellow]cache-default-manifest-services not yet implemented.[/yellow]")
