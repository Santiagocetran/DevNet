from pathlib import Path
from typing import Optional

import typer
from web3 import Web3

from dincli.cli.utils import CACHE_DIR, build_and_send_tx, require_custom_manifest_service
from dincli.services.cid_utils import get_bytes32_from_cid, get_cid_from_bytes32

app = typer.Typer(help="Commands for DIN clients in DIN.")
lms_app = typer.Typer(help="LMS related commands")
app.add_typer(lms_app, name="lms")

@app.command()
def train_lms(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model index"),
    submit: Optional[bool] = typer.Option(False, "--submit", help="Submit the model to DIN"),
    gi: Optional[int] = typer.Option(None, "--gi", help="Global iteration to use"),
):
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)

    taskCoordinator_contract, taskAuditor_contract = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id), ctx.obj.get_deployed_din_task_auditor_contract(True, model_id)
    runtime = ctx.obj.build_service_runtime(role="client", model_id=model_id)
    current_GI, current_GIstate = ctx.obj.get_current_gi_and_state(taskCoordinator_contract)

    ctx.obj.validate_gi_ET_curr_GI(gi, current_GI)

    console.print("Training local model")

    genesis_model_ipfs_hash_raw = taskCoordinator_contract.functions.genesisModelIpfsHash().call()
    genesis_model_ipfs_hash = get_cid_from_bytes32(genesis_model_ipfs_hash_raw.hex())
    console.print("Using Genesis Model IPFS Hash: ", genesis_model_ipfs_hash)

    initial_model_ipfs_hash = None
    t2_list = []
    if current_GI > 1:
        t2_batches_count = 1
        for i in range(t2_batches_count):
            (bid, val, fin, cid_raw) = taskCoordinator_contract.functions.getTier2Batch(current_GI-1, i).call()
            cid = get_cid_from_bytes32(cid_raw.hex()) if cid_raw and cid_raw != bytes(32) else None
            t2_list.append(Tier2Batch(batch_id=bid, validators=val, finalized=fin, final_cid=cid))
            t2_batch_gi_minus_1 = t2_list[0]
            initial_model_ipfs_hash = t2_batch_gi_minus_1.final_cid

    console.print("Using Latest Global Model IPFS Hash: ", initial_model_ipfs_hash)

    model_base_dir = Path(CACHE_DIR) / effective_network / f"model_{model_id}"
    manifest = runtime.require_manifest_key("train_client_model_and_upload_to_ipfs")
    model_manifest = runtime.require_manifest_key("ModelArchitecture")
    client_service_path = model_base_dir / Path(manifest["path"])
    model_service_path = model_base_dir / Path(model_manifest["path"])

    require_custom_manifest_service(manifest, "train_client_model_and_upload_to_ipfs")
    ctx.obj.ensure_file_exists(client_service_path, manifest["ipfs"], "client service") 
    ctx.obj.ensure_file_exists(model_service_path, model_manifest["ipfs"], "model architecture service")

    fn = ctx.obj.load_custom_fn(
        client_service_path,
        "train_client_model_and_upload_to_ipfs",
        runtime=runtime,
    )

    client_model_ipfs_hash = fn(
        genesis_model_ipfs_hash,
        account.address,
        effective_network,
        initial_model_ipfs_hash=initial_model_ipfs_hash,
        model_base_dir=model_base_dir,
        gi=current_GI,
    )

    if submit:
        try:
            client_model_ipfs_hash_bytes32 = Web3.to_bytes(hexstr=get_bytes32_from_cid(client_model_ipfs_hash))

            build_and_send_tx(
                ctx,
                taskAuditor_contract.functions.submitLocalModel(client_model_ipfs_hash_bytes32, current_GI),
                f"Submitting local model with IPFS hash: {client_model_ipfs_hash} to task auditor",
                f"Local model submitted to task auditor with IPFS hash: {client_model_ipfs_hash}",
                f"Local model submission failed to task auditor with IPFS hash: {client_model_ipfs_hash}",
                exit_on_failure=False
            )
        except Exception as e:
            console.print(f"[bold red] Error submitting local model to task auditor: {e}[/bold red]")

@lms_app.command()
def show_models(
    ctx: typer.Context,
    model_id: int = typer.Argument(..., help="Model index"),
    gi: int = typer.Option(None, "--gi", help="Global iteration to use"),
):
    
    effective_network, w3, account, console = ctx.obj.get_en_w3_account_console(model_id)
    
    taskCoordinator_contract, taskAuditor_contract = ctx.obj.get_deployed_din_task_coordinator_contract(True, model_id), ctx.obj.get_deployed_din_task_auditor_contract(True, model_id)
    
    curr_GI, curr_GIstate = ctx.obj.get_current_gi_and_state(taskCoordinator_contract)
    
    ref_gi = ctx.obj.validate_gi_LTE_curr_GI(gi, curr_GI)

    console.print(f"[bold green]Showing local model submissions for global iteration {ref_gi}![/bold green]")

    ctx.obj.validate_GIstate_LTE_given_GIstate(ref_gi, curr_GI, curr_GIstate, "LMSstarted", "Its not time for model submissions yet.")
    
    has_submitted = taskAuditor_contract.functions.clientHasSubmitted(ref_gi, account.address).call()
    if has_submitted:
        console.print(f"[green]✓ Client {account.address} has submitted ![/green]")
    else:
        console.print(f"[red]Error:[/red] No local model submission found")
        raise typer.Exit(1)

    has_index = taskAuditor_contract.functions.clientSubmissionIndex(ref_gi, account.address).call()

    lm_submission = taskAuditor_contract.functions.lmSubmissions(ref_gi, has_index).call()
    
    console.print(f"[green]✓ Client {lm_submission[0]} submitted model {get_cid_from_bytes32(lm_submission[1].hex())}![/green]")

    console.print(f"[bold green]✓ Local model submissions shown![/bold green]")
