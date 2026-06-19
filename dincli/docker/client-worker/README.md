# DIN Client Worker Container

This is the first containerization target for client local training.

The host keeps normal `dincli` configuration outside Docker:

- `/home/azureuser/.config/dincli/config.json`
- `/home/azureuser/.config/dincli/wallet.json`

The worker receives only a mounted model cache, a mounted job file, and an output directory. It does not need the wallet.

## Build

```bash
cd /home/azureuser/projects/devnet
docker build -f dincli/docker/client-worker/Dockerfile -t din-client-worker:dev .
```

## Host Preflight

Before running the container, the host `dincli` should prepare the model cache:

1. `cache_manifest(model_id, network, update=True)` downloads/refreshes `manifest.json`.
2. `ensure_file_exists(...)` downloads the client service and model architecture files from the manifest.
3. The client dataset should be available under the model cache, for example:

```text
/home/azureuser/.cache/dincli/local/model_0/dataset/clients/<wallet-address>/data.pt
```

For v1, mount the model cache into the container instead of copying it into the image. Copying would make every model/job create a large image or temporary directory and would make cache invalidation harder.

## Example Job File

Create a host-side job file such as `/tmp/din-client-job.json`:

```json
{
  "network": "local",
  "account_address": "0xCLIENT_ADDRESS",
  "genesis_model_ipfs_hash": "bafy...",
  "initial_model_ipfs_hash": null,
  "gi": 1,
  "model_base_dir": "/din/model",
  "manifest_path": "/din/model/manifest.json",
  "output_path": "/din/output/result.json"
}
```

## Run

```bash
docker run --rm \
  --name din-client-worker-model-0-gi-1 \
  --cpus 2 \
  --memory 4g \
  -e IPFS_API_URL_ADD \
  -e IPFS_API_URL_RETRIEVE \
  -v /home/azureuser/.cache/dincli/local/model_0:/din/model:rw \
  -v /tmp/din-client-job.json:/din/job/job.json:ro \
  -v /tmp/din-client-output:/din/output:rw \
  din-client-worker:dev
```

The result is written to:

```text
/tmp/din-client-output/result.json
```

## Current Limitation

The current custom client service still calls `retrieve_from_ipfs` and `upload_to_ipfs` from inside the worker. If the selected IPFS provider needs network access or credentials, v1 must pass only the minimal IPFS configuration into the worker, never the wallet or `/home/azureuser/.config/dincli`.

After the service contract is refactored so the worker trains to an output artifact path and the trusted host process performs IPFS upload and contract submission, run the worker with `--network none` by default.
