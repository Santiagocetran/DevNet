from pathlib import Path
from typing import Optional

import typer

from dincli.cli.utils import (CACHE_DIR, GIstateToStr, build_and_send_tx,
                               get_manifest_key)
from dincli.services.modelowner import getscoreforGM
from dincli.services.cid_utils import get_cid_from_bytes32

gi_app = typer.Typer(help="Global iteration commands")
reg_app = typer.Typer(help="Registration commands for a Global Iteration")

gi_app.add_typer(reg_app, name="reg")

@gi_app.command(help="Start a global iteration")
def start(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: Optional[int] = typer.Option(None, "--gi", help="Global iteration (optional)"),
    threshold: Optional[int] = typer.Option(None, "--threshold", help="Accuracy threshold deduction (default: 5)"),

):

    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)

    # === 1. Contract & State Validation ===
    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    curr_gi, GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)

    # Validate requested GI
    target_gi = gi if gi is not None else curr_gi + 1
    if target_gi != curr_gi + 1:
        console.print(f"[red]❌ Invalid GI request:[/red] Expected {curr_gi + 1}, got {target_gi}")
        raise typer.Exit(1)

    console.print(f"[bold green]🚀 Starting global iteration {target_gi}[/bold green]")

    # === 2. Latest GM CID Resolution ===
    if curr_gi == 0:
        gmcid_raw = task_coordinator.functions.genesisModelIpfsHash().call()
        gmcid = get_cid_from_bytes32(gmcid_raw.hex())
        console.print(f"[dim]Using genesis model CID:[/dim] {gmcid}")
    else:
        _, _, _, gmcid_raw = task_coordinator.functions.getTier2Batch(curr_gi, 0).call()
        gmcid = get_cid_from_bytes32(gmcid_raw.hex())
        console.print(f"[dim]Using T2-aggregated model CID for GI {curr_gi}:[/dim] {gmcid}")

    # === 3. Path Setup (Consistent Path Handling) ===
    model_base_path = Path(CACHE_DIR) / effective_network / f"model_{model_id}"
    models_dir = model_base_path / "models"
    test_data_path = model_base_path / "dataset" / "test" / "test_dataset.pt"
    genesis_model_path = models_dir / "genesis_model.pth"

     # === 4. Accuracy Calculation ===
    manifest = get_manifest_key(effective_network, "getscoreforGM", model_id)

    if manifest["type"] == "custom":

        # Retrieve required service files
        service_path = model_base_path / manifest["path"]
        model_arch_path = model_base_path / get_manifest_key(effective_network, "ModelArchitecture", model_id)["path"]


        ctx.obj.ensure_file_exists(service_path, manifest["ipfs"], "model owner service")
        ctx.obj.ensure_file_exists(model_arch_path, get_manifest_key(effective_network, "ModelArchitecture", model_id)["ipfs"], "model architecture service")
        ctx.obj.ensure_file_exists(genesis_model_path, get_manifest_key(effective_network, "Genesis_Model_CID", model_id), "genesis model")

        # Validate test dataset
        if not test_data_path.exists():
            console.print(f"[red]❌ Test dataset missing:[/red] {test_data_path}")
            raise typer.Exit(1)


        fn = ctx.obj.load_custom_fn(service_path, "getscoreforGM")

        accuracy = fn(curr_gi, gmcid, model_base_path)
    else:
         # Built-in scoring fallback
        accuracy = getscoreforGM(curr_gi, gmcid, base_path=model_base_path)

    console.print(f"[bold]GM Accuracy (GI {curr_gi}):[/bold] {accuracy:.2f}%")


    # === 5. Threshold Application ===
    threshold = threshold if threshold is not None else 5
    pass_score = int(accuracy - threshold)
    console.print(f"[bold]Pass Score (threshold -{threshold}%):[/bold] {pass_score}")

     # === 6. Transaction Execution ===
    try:
        tx_receipt = build_and_send_tx(
            ctx,
            task_coordinator.functions.startGI(target_gi, pass_score),
            f"Starting global iteration {target_gi}",
            f"Global iteration {target_gi} started successfully!",
            f"Transaction failed or reverted starting global iteration {target_gi}",
            exit_on_failure=False
        )
        console.print(f"[dim]Transaction hash:[/dim] {tx_receipt.transactionHash.hex()}")
        console.print(f"[bold]Pass Score set to:[/bold] {pass_score}")
    except Exception as e:
        console.print(f"[red]❌ Transaction failed:[/red] {str(e)}")
        raise typer.Exit(1)
    
    
@reg_app.command()  
def aggregators_open(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)

    # === 1. Contract & State Validation ===
    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    curr_gi, GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)
    
    ctx.obj.validate_gi_ET_curr_GI(gi, curr_gi)
    
    console.print(f"[bold green]Opening aggregators registration [/bold green]")
    
    try:
        tx_receipt = build_and_send_tx(
            ctx,
            task_coordinator.functions.startDINaggregatorsRegistration(curr_gi),
            "Opening aggregators registration",
            "Aggregators registration opened!",
            "Transaction failed or reverted opening aggregators registration",
            exit_on_failure=False
        )
        console.print(f"[dim]Transaction hash:[/dim] {tx_receipt.transactionHash.hex()}")
    except Exception as e:
        console.print(f"[red]❌ Transaction failed:[/red] {str(e)}")
        raise typer.Exit(1)

@reg_app.command("aggregators-close")
def aggregators_close(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)

    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    curr_GI, GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)
    
    ctx.obj.validate_gi_ET_curr_GI(gi, curr_GI)
    
    console.print(f"[bold green]Closing aggregators registration[/bold green]")

    try:
        tx_receipt = build_and_send_tx(
            ctx,
            task_coordinator.functions.closeDINaggregatorsRegistration(curr_GI),
            "Closing aggregators registration",
            "Aggregators registration closed!",
            "Aggregators registration closing failed",
            exit_on_failure=False
        )
        console.print(f"[dim]Aggregators registration closed tx:[/dim] {tx_receipt.transactionHash.hex()}")
    except Exception as e:
        console.print(f"[red]❌ Transaction failed:[/red] {str(e)}")
        raise typer.Exit(1)
        
@reg_app.command()
def auditors_open(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):      
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)
    
    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    curr_GI, GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)
    
    ctx.obj.validate_gi_ET_curr_GI(gi, curr_GI)
    
    console.print(f"[bold green]Opening auditors registration[/bold green]")

    try:
        tx_receipt = build_and_send_tx(
            ctx,
            task_coordinator.functions.startDINauditorsRegistration(curr_GI),
            "Opening auditors registration",
            "Auditors registration opened!",
            "Auditors registration opening failed",
            exit_on_failure=False
        )
        console.print(f"[dim]Auditors registration opened tx:[/dim] {tx_receipt.transactionHash.hex()}")
    except Exception as e:
        console.print(f"[red]❌ Transaction failed:[/red] {str(e)}")
        raise typer.Exit(1)

@gi_app.command("show-registered-auditors", help="Show registered auditors")
def show_registered_auditors(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):    
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)
    
    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    
    DINTaskAuditor_contract = ctx.obj.get_deployed_din_task_auditor_contract(True, model_id)
    
    curr_GI, curr_GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)

    target_gi = ctx.obj.validate_gi_LTE_curr_GI(gi, curr_GI)

    ctx.obj.validate_GIstate_LTE_given_GIstate(target_gi, curr_GI, curr_GIstate, "DINauditorsRegistrationStarted", "No auditors registered yet as DINauditorsRegistrationStarted has not been reached")

    console.print(f"[bold green]Showing registered auditors for global iteration {target_gi} [/bold green]")

    registered_auditors = DINTaskAuditor_contract.functions.getDINtaskAuditors(target_gi).call()
    console.print(str(len(registered_auditors)) + " Registered Auditors:", registered_auditors)    
    console.print("[green]✓ Registered auditors shown![/green]")


@gi_app.command("show-registered-aggregators", help="Show registered aggregators")
def show_registered_aggregators(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)
    
    # === 1. Contract & State Validation ===
    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    curr_gi, curr_GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)

    target_gi = ctx.obj.validate_gi_LTE_curr_GI(gi, curr_gi)

    ctx.obj.validate_GIstate_LTE_given_GIstate(target_gi, curr_gi, curr_GIstate, "DINaggregatorsRegistrationStarted", "No aggregators registered yet as DINaggregatorsRegistrationStarted has not been reached")

    console.print(f"[bold green]Showing registered aggregators for global iteration {target_gi}![/bold green]")
    
    registered_aggregators = task_coordinator.functions.getDINtaskAggregators(target_gi).call()
    console.print(str(len(registered_aggregators)) + " Registered Aggregators:", registered_aggregators)    
    console.print("[green]✓ Registered aggregators shown![/green]")



@reg_app.command("auditors-close", help="Close auditors registration")
def auditors_close(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)
    
    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    curr_GI, curr_GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)
    
    ctx.obj.validate_gi_ET_curr_GI(gi, curr_GI)
    
    console.print(f"[bold green]Closing auditors registration[/bold green]")

    try:    
        build_and_send_tx(
            ctx,
            task_coordinator.functions.closeDINauditorsRegistration(curr_GI),
            "Closing auditors registration",
            "Auditors registration closed!",
            "Auditors registration closing failed",
            exit_on_failure=False
        )
    except Exception as e:
        console.print(f"[red]❌ Transaction failed:[/red] {str(e)}")
        raise typer.Exit(1)


@gi_app.command()
def end(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model ID"),
    gi: int = typer.Option(None, "--gi", help="Global iteration number"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)

    task_coordinator = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id)
    
    curr_GI, GIstate = ctx.obj.get_current_gi_and_state(task_coordinator)

    ref_gi = ctx.obj.validate_gi_ET_curr_GI(gi, curr_GI)
    ctx.obj.validate_GIstate_ET_given_GIstate( GIstate, "AggregatorsSlashed", "AggregatorsSlashed not passed yet")
    
    console.print(f"[bold green]Ending GI {curr_GI}...[/bold green]")   
    try:
        build_and_send_tx(
            ctx,
            task_coordinator.functions.endGI(curr_GI),
            f"Ending GI {curr_GI}",
            "GI ended!",
            "GI ending failed",
            exit_on_failure=False
        )
    except Exception as e:
        console.print(f"[red]❌ Transaction failed:[/red] {str(e)}")
        raise typer.Exit(1)
