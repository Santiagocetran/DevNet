
import typer
from dincli.cli.utils import build_and_send_tx

slash_app = typer.Typer(help="Slash commands")

@slash_app.command("auditors")
def slash_auditors(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)

    task_coordinator_Contract = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    
    curr_GI, curr_GIstate = ctx.obj.get_current_gi_and_state(task_coordinator_Contract)

    ref_gi = ctx.obj.validate_gi_ET_curr_GI(gi, curr_GI)
    ctx.obj.validate_GIstate_ET_given_GIstate(curr_GIstate, "T2AggregationDone","Can not slash auditors at this time.")

    console.print(f"[bold green]Slashing Auditors ...[/bold green]")
    try:
        tx_receipt = build_and_send_tx(
            ctx,
            task_coordinator_Contract.functions.slashAuditors(ref_gi),
            "Slashing Auditors",
            "Auditors slashed",
            "Slash Auditors Transaction failed",
            exit_on_failure=False
        )
        console.print(f"[dim]Tx hash: {tx_receipt.transactionHash.hex()}[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)
    


@slash_app.command("aggregators")
def slash_aggregators(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)

    task_coordinator_Contract = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    
    curr_GI, curr_GIstate = ctx.obj.get_current_gi_and_state(task_coordinator_Contract)

    ref_gi = ctx.obj.validate_gi_ET_curr_GI(gi, curr_GI)
    ctx.obj.validate_GIstate_ET_given_GIstate(curr_GIstate, "AuditorsSlashed","Can not slash aggregators at this time.")
    
    console.print(f"[bold green]Slashing Aggregators ...[/bold green]")

    try:
        tx_receipt = build_and_send_tx(
            ctx,
            task_coordinator_Contract.functions.slashAggregators(ref_gi),
            "Slashing Aggregators",
            "Aggregators slashed",
            "Slash Aggregators Transaction failed",
            exit_on_failure=False
        )
        console.print(f"[dim]Tx hash: {tx_receipt.transactionHash.hex()}[/dim]")
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1)
