from __future__ import annotations

from pathlib import Path

import torch
from rich import console

from dincli.cli.utils import CONFIG_DIR
from dincli.services.ipfs import retrieve_from_ipfs
from dincli.services.scoring import (
    evaluate_classification_model,
    load_scoring_policy,
    normalize_holdout_delta_score,
    run_eligibility_anomaly_gate,
    write_metric_bundle,
)


console = console.Console()


def Score_model_by_auditor(
    gi,
    genesis_model_cid,
    batch_id,
    model_index,
    auditor_address,
    testDataCID,
    lm_cid,
    model_base_dir=None,
):
    """Built-in fallback auditor scorer.

    Most real tasks use the custom service path from the manifest, but `dincli`
    still has a built-in fallback. Keeping this implementation aligned with the
    reference task prevents the fallback from silently reverting to old
    accuracy-only scoring.

    The return value remains `(score, eligible)` because the current Solidity
    method is `setAuditScorenEligibility(...)`. Rich audit details are written
    to a local metric bundle and best-effort uploaded to IPFS for the future V2
    audit-result flow.
    """

    try:
        if model_base_dir is None:
            model_base_dir = Path(CONFIG_DIR) / "auditor" / str(auditor_address)
        model_base_dir = Path(model_base_dir)

        policy = load_scoring_policy(model_base_dir)

        dataset_dir = model_base_dir / "datasets"
        model_dir = model_base_dir / "models"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        model_dir.mkdir(parents=True, exist_ok=True)

        test_data_path = dataset_dir / f"auditorDataset_{gi}_{batch_id}.pt"
        genesis_model_path = model_dir / "genesis_model.pt"
        local_model_path = model_dir / f"lm_{gi}_{model_index}.pt"

        retrieve_from_ipfs(testDataCID, test_data_path)
        retrieve_from_ipfs(genesis_model_cid, genesis_model_path)
        retrieve_from_ipfs(lm_cid, local_model_path)

        testdata = torch.load(test_data_path, weights_only=False)
        baseline_model = torch.load(genesis_model_path, weights_only=False)
        candidate_model = torch.load(genesis_model_path, weights_only=False)
        candidate_state = torch.load(local_model_path, weights_only=True)

        min_eval_examples = int(policy.get("eligibility_checks", {}).get("min_eval_examples", 1))
        if hasattr(testdata, "__len__") and len(testdata) < min_eval_examples:
            console.print(
                f"[bold red]Evaluation dataset too small: {len(testdata)} < {min_eval_examples}[/bold red]"
            )
            return 0, False

        eligibility = run_eligibility_anomaly_gate(
            base_state=baseline_model.state_dict(),
            candidate_state=candidate_state,
            policy=policy,
        )
        if not eligibility.eligible:
            console.print(f"[bold red]Local model failed eligibility: {eligibility.tags}[/bold red]")
            return 0, False

        candidate_model.load_state_dict(candidate_state)

        batch_size = int(policy.get("evaluation", {}).get("batch_size", 32))
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        baseline_metrics = evaluate_classification_model(
            baseline_model,
            testdata,
            batch_size=batch_size,
            device=device,
        )
        candidate_metrics = evaluate_classification_model(
            candidate_model,
            testdata,
            batch_size=batch_size,
            device=device,
        )

        result = normalize_holdout_delta_score(
            candidate_metrics=candidate_metrics,
            baseline_metrics=baseline_metrics,
            eligibility=eligibility,
            policy=policy,
        )
        result = write_metric_bundle(
            result=result,
            policy=policy,
            output_dir=model_base_dir / "audits" / "metric_bundles" / str(auditor_address),
            gi=gi,
            batch_id=batch_id,
            model_index=model_index,
            auditor_address=auditor_address,
            test_data_cid=testDataCID,
            local_model_cid=lm_cid,
        )

        console.print(f"Audit contract score: {result.contract_score}")
        console.print(f"Audit accepted by policy: {result.accepted}")
        console.print(f"Audit metric bundle path: {result.metric_bundle_path}")
        if result.metric_bundle_cid:
            console.print(f"Audit metric bundle CID: {result.metric_bundle_cid}")

        return result.contract_score, result.accepted
    except Exception as e:
        print("can not score model", e)
        return 0, False
