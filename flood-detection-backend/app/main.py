import gradio as gr
import os
import tempfile
import requests
# import shutil
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Optional, Union
import subprocess
from pathlib import Path
import torch
import sys
import boto3
from botocore.exceptions import ClientError
import numpy as np
import rasterio
from rasterio.transform import from_bounds
import io
from sentinelhub import SHConfig, BBox, CRS, DataCollection, SentinelHubRequest, MimeType
from datetime import datetime, timedelta
import uvicorn

try:
    import yaml
except ImportError:  # pragma: no cover - runtime fallback
    yaml = None  # type: ignore[assignment]

from model_paths import (
    CONFIG_PATH,
    CHECKPOINT_PATH,
    MODEL_CONFIG_FILENAME,
    MODEL_CHECKPOINT_FILENAME,
    PROJECT_CODE_DIR,
)

# --- MinIO Configuration ---
DEFAULT_MINIO_ENDPOINT = 'https://minio-s3-ppe-multi-modal.apps.cluster-r8fxn.r8fxn.sandbox753.opentlc.com'
MINIO_ENDPOINT = os.environ.get('MINIO_ENDPOINT', DEFAULT_MINIO_ENDPOINT)
MINIO_ACCESS_KEY = os.environ.get('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.environ.get('MINIO_SECRET_KEY')
MINIO_BUCKET = os.environ.get('MINIO_PREDICTIONS_BUCKET', 'flood-predictions')
MINIO_MODELS_BUCKET = os.environ.get('MINIO_MODELS_BUCKET', 'flood-models')
MINIO_REGION = os.environ.get('MINIO_REGION', 'us-east-1')
MINIO_VERIFY_SSL = os.environ.get('MINIO_VERIFY_SSL', 'false').lower() in {
    '1', 'true', 'yes'}

MODEL_CHECKPOINT_FALLBACK_URL = os.environ.get(
    "MODEL_CHECKPOINT_FALLBACK_URL",
    "https://huggingface.co/ibm-granite/granite-geospatial-uki-flooddetection/resolve/main/granite_geospatial_uki_flood_detection_v1.ckpt?download=1",
)
MODEL_CONFIG_FALLBACK_URL = os.environ.get(
    "MODEL_CONFIG_FALLBACK_URL",
    "https://huggingface.co/ibm-granite/granite-geospatial-uki-flooddetection/resolve/main/config.yaml?download=1",
)
HF_AUTH_TOKEN = os.environ.get("HF_AUTH_TOKEN")
MODEL_DOWNLOAD_CHUNK_SIZE = int(
    os.environ.get("MODEL_DOWNLOAD_CHUNK_SIZE", 8 * 1024 * 1024)
)

# --- Sentinel Hub Configuration ---
# Secrets must be set as environment variables
SH_CLIENT_ID = os.environ.get("SH_CLIENT_ID")
SH_CLIENT_SECRET = os.environ.get("SH_CLIENT_SECRET")

DEFAULT_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

_MONITOR_MIN_KEYWORDS = ("loss", "error", "mae", "rmse", "mse")
_MONITOR_MAX_KEYWORDS = ("acc", "accuracy", "precision",
                         "recall", "f1", "iou", "dice")


def _strip_checkpoint_hparams(checkpoint_path: Path) -> None:
    """
    Remove stale Lightning hyper-parameter metadata from a checkpoint file.
    This prevents Terratorch CLI from re-injecting incompatible config keys.
    """
    if not checkpoint_path.exists():
        return

    try:
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
    except Exception as exc:  # pragma: no cover - defensive logging
        print(
            f"⚠️ Unable to load checkpoint for sanitising ({checkpoint_path}): {exc}",
            file=sys.stderr,
        )
        return

    patched = False
    for key in ("hyper_parameters", "hparams", "hyperparameters"):
        if key in checkpoint:
            checkpoint.pop(key, None)  # Use .pop() to guarantee removal
            patched = True

    if not patched:
        # --- NEW: Print message even if no change needed ---
        print(f"✅ Checkpoint hyperparameters already clean: {checkpoint_path}")
        return

    tmp_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
    try:
        torch.save(checkpoint, tmp_path)
        tmp_path.replace(checkpoint_path)
        print(f"ℹ️ Stripped Lightning hyperparameters from {checkpoint_path}")
    except Exception as exc:  # pragma: no cover - defensive logging
        print(
            f"⚠️ Failed to write patched checkpoint {checkpoint_path}: {exc}",
            file=sys.stderr,
        )
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass


def _select_mode_value(raw_mode: Any, monitor: Any) -> Any:
    """
    Translate legacy boolean/string mode flags into the allowed 'min'/'max' values.
    """
    if isinstance(raw_mode, str):
        lowered = raw_mode.strip().lower()
        if lowered in {"min", "max"}:
            return lowered
        if lowered in {"true", "false"}:
            raw_mode = lowered == "true"
        else:
            return raw_mode

    if isinstance(raw_mode, bool):
        bool_value = raw_mode
    else:
        bool_value = True

    if isinstance(monitor, str):
        monitor_lower = monitor.lower()
        if any(token in monitor_lower for token in _MONITOR_MIN_KEYWORDS):
            return "min"
        if any(token in monitor_lower for token in _MONITOR_MAX_KEYWORDS):
            return "max"

    return "max" if bool_value else "min"


def _normalise_mode_nodes(node: Any) -> bool:
    """
    Recursively walk the parsed YAML and normalise any boolean mode fields.
    """
    changed = False
    if isinstance(node, dict):
        monitor = node.get("monitor")
        if "mode" in node:
            new_mode = _select_mode_value(node["mode"], monitor)
            if new_mode != node["mode"]:
                node["mode"] = new_mode
                changed = True
        for value in node.values():
            if _normalise_mode_nodes(value):
                changed = True
    elif isinstance(node, list):
        for item in node:
            if _normalise_mode_nodes(item):
                changed = True
    return changed


def _fallback_mode_text_replace(raw_text: str, config_path: Path) -> None:
    replacements = {
        "mode: True": "mode: max",
        "mode: true": "mode: max",
        "mode: False": "mode: min",
        "mode: false": "mode: min",
    }
    updated = raw_text
    for src, dst in replacements.items():
        updated = updated.replace(src, dst)
    if updated != raw_text:
        config_path.write_text(updated)
        print(
            f"ℹ️ Normalised boolean mode fields in {config_path} (text replace)")


def normalise_boolean_mode_fields(config_path: Path) -> None:
    """
    Ensure Lightning callback/scheduler `mode` parameters are valid strings.
    ** ALSO: Injects a valid ModelCheckpoint to override a terratorch bug. **
    """
    if config_path.suffix.lower() not in {".yaml", ".yml"}:
        return

    try:
        raw_text = config_path.read_text()
    except FileNotFoundError:
        print(
            f"⚠️ Config file not found, cannot patch: {config_path}", file=sys.stderr)
        return

    if not raw_text.strip():
        return

    if yaml is None:
        _fallback_mode_text_replace(raw_text, config_path)
        return

    try:
        parsed = yaml.safe_load(raw_text)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(
            f"⚠️ Failed to parse YAML config at {config_path}: {exc}. Falling back to text replacement.",
            file=sys.stderr,
        )
        _fallback_mode_text_replace(raw_text, config_path)
        return

    if parsed is None:
        return

    # --- BEGIN NEW LOGIC ---
    # This is the override for the terratorch `mode: True` bug.
    # We inject a valid ModelCheckpoint config to prevent terratorch
    # from injecting its own buggy, hard-coded one.

    callbacks_changed = False
    if "trainer" in parsed and "callbacks" in parsed["trainer"]:
        callbacks = parsed["trainer"].get("callbacks")
        if isinstance(callbacks, list):
            found_checkpoint = False
            for cb in callbacks:
                if isinstance(cb, dict) and "ModelCheckpoint" in cb.get("class_path", ""):
                    found_checkpoint = True
                    break

            if not found_checkpoint:
                print(
                    "ℹ️ Injecting valid ModelCheckpoint config to override terratorch bug.")
                callbacks.append({
                    "class_path": "lightning.pytorch.callbacks.ModelCheckpoint",
                    "init_args": {
                        "monitor": "val/loss",  # This value doesn't matter, but must be valid
                        "mode": "min",         # This is the critical fix
                        "save_top_k": 0        # Don't save anything
                    }
                })
                callbacks_changed = True
        else:  # Handle case where callbacks might not be a list initially
            print("ℹ️ Initializing trainer callbacks list and injecting ModelCheckpoint.")
            parsed["trainer"]["callbacks"] = [{
                "class_path": "lightning.pytorch.callbacks.ModelCheckpoint",
                "init_args": {
                    "monitor": "val/loss",
                    "mode": "min",
                    "save_top_k": 0
                }
            }]
            callbacks_changed = True
    elif "trainer" in parsed:  # Handle case where trainer exists but callbacks doesn't
        print("ℹ️ Adding trainer callbacks list and injecting ModelCheckpoint.")
        parsed["trainer"]["callbacks"] = [{
            "class_path": "lightning.pytorch.callbacks.ModelCheckpoint",
            "init_args": {
                "monitor": "val/loss",
                "mode": "min",
                "save_top_k": 0
            }
        }]
        callbacks_changed = True
    else:  # Handle case where trainer section doesn't exist
        print("ℹ️ Adding trainer section and injecting ModelCheckpoint.")
        parsed["trainer"] = {
            "callbacks": [{
                "class_path": "lightning.pytorch.callbacks.ModelCheckpoint",
                "init_args": {
                    "monitor": "val/loss",
                    "mode": "min",
                    "save_top_k": 0
                }
            }]
        }
        callbacks_changed = True
    # --- END NEW LOGIC ---

    # Now, run the original logic to fix any other 'mode: True' issues
    nodes_changed = _normalise_mode_nodes(parsed)

    if nodes_changed or callbacks_changed:  # Check if *either* change happened
        try:
            config_path.write_text(yaml.safe_dump(parsed, sort_keys=False))
            print(f"✅ Patched and saved config file: {config_path}")
        except Exception as write_exc:
            print(
                f"⚠️ Failed to write patched config file {config_path}: {write_exc}", file=sys.stderr)
    else:
        # --- NEW: Print message even if no change needed ---
        print(f"✅ Config file already patched/correct: {config_path}")


def upload_to_minio(file_path: str, object_name: str) -> str:
    """
    Upload a file to MinIO storage.
    """
    if not MINIO_ACCESS_KEY or not MINIO_SECRET_KEY:
        raise gr.Error(
            "MinIO credentials are not configured. Cannot upload result.")

    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            region_name=MINIO_REGION,
            use_ssl=MINIO_ENDPOINT.startswith('https://'),
            verify=MINIO_VERIFY_SSL,
        )
        print(
            f"Uploading {file_path} to MinIO bucket '{MINIO_BUCKET}' as '{object_name}'")
        s3_client.upload_file(file_path, MINIO_BUCKET, object_name)

        # Generate a presigned URL that expires in 1 hour (3600 seconds)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': MINIO_BUCKET, 'Key': object_name},
            ExpiresIn=3600
        )
        print(f"File uploaded. Shareable URL: {presigned_url}")
        return presigned_url
    except Exception as e:
        print(f"Error uploading to MinIO: {e}", file=sys.stderr)
        raise gr.Error(f"Failed to upload result to MinIO: {e}")


def download_file(url: str, dest: Path) -> None:
    """
    Download a file from the given URL to the destination path.
    Supports optional Hugging Face bearer token authentication.
    """
    headers = {}
    if HF_AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {HF_AUTH_TOKEN}"

    with requests.get(url, stream=True, timeout=300, headers=headers) as response:
        response.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in response.iter_content(MODEL_DOWNLOAD_CHUNK_SIZE):
                if chunk:
                    fh.write(chunk)


def coerce_to_timestamp(value: Union[float, int, str, datetime]) -> float:
    """
    Convert different time representations into a POSIX timestamp.
    """
    if isinstance(value, (float, int)):
        return float(value)

    if isinstance(value, datetime):
        return value.timestamp()

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            try:
                return datetime.strptime(value, DEFAULT_DATETIME_FORMAT).timestamp()
            except ValueError as exc:
                raise ValueError(f"Invalid datetime string: {value}") from exc

    raise ValueError(f"Unsupported datetime value: {value!r}")


def fetch_sentinel2_data(bbox: tuple, time_interval: tuple, config: SHConfig):
    """Fetch Sentinel-2 data separately"""
    print("🛰️  Fetching Sentinel-2 data...")

    evalscript = """
    //VERSION=3
    function setup() {
      return {
        input: ["B02","B03","B04","B8A","B11","B12","SCL"],
        output: { bands: 7, sampleType: "FLOAT32" }
      };
    }
    function evaluatePixel(s) {
      // cloud = 1 when SCL = 8,9,10, otherwise 0
      const cloud = (s.SCL == 8 || s.SCL == 9 || s.SCL == 10) ? 1 : 0;
      return [s.B02, s.B03, s.B04, s.B8A, s.B11, s.B12, cloud];
    }
    """

    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=time_interval,
                other_args={
                    "dataFilter": {           # <-- only that granule
                        "tileId": {"$eq": "30UXE"}
                    },
                    "processing": {
                        "mosaickingOrder": "mostRecent"  # guarantees one scene
                    }
                }
            )
        ],
        responses=[SentinelHubRequest.output_response(
            "default", MimeType.TIFF)],
        bbox=BBox(bbox=bbox, crs=CRS.WGS84),
        size=[512, 512],
        config=config,
    )

    url_list = request.get_url_list()
    if url_list:
        print(
            f"✅ Requesting from actual URL endpoint: {url_list[0].split('?')[0]}...")

    return request.get_data()[0]


def fetch_sentinel1_data(bbox: tuple, time_interval: tuple, config: SHConfig):
    """Fetch Sentinel-1 data separately"""
    print("🛰️  Fetching Sentinel-1 data...")

    evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: ["VV", "VH"],
                output: { bands: 2, sampleType: "FLOAT32" }
            };
        }
        function toDb(linear) {
            if (!isFinite(linear) || linear <= 0) return -35.0;
            let db = 10 * Math.log10(linear);
            return Math.max(-35.0, Math.min(10.0, db));
        }
        function evaluatePixel(sample) {
            return [toDb(sample.VV), toDb(sample.VH)];
        }
    """

    request = SentinelHubRequest(
        evalscript=evalscript,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL1_IW,
                time_interval=time_interval,
                other_args={
                    "dataFilter": {
                        # "orbitDirection": "ASCENDING",
                        "relativeOrbit": 137           # relative orbit of the EMSR scene
                    },
                    "processing": {"mosaickingOrder": "mostRecent"}
                },
            )
        ],
        responses=[SentinelHubRequest.output_response(
            "default", MimeType.TIFF)],
        bbox=BBox(bbox=bbox, crs=CRS.WGS84),
        size=[512, 512],
        config=config,
    )

    return request.get_data()[0]


def combine_sentinel_data(s2_data: np.ndarray, s1_data: np.ndarray, bbox: tuple) -> bytes:
    """Combine Sentinel-1 (float32) and Sentinel-2 (uint16) data into a single 9-band float32 TIFF."""
    print("🔧 Combining Sentinel-1 and Sentinel-2 data...")

    # Transpose to (bands, height, width)
    if s2_data.shape == (512, 512, 7):
        s2_data = s2_data.transpose(2, 0, 1)
    if s1_data.shape == (512, 512, 2):
        s1_data = s1_data.transpose(2, 0, 1)

    s1_float = s1_data
    s2_scaled = (s2_data[:6] * 10000).astype(np.float64)  # bands 1‑6
    cloud_band = s2_data[6].astype(
        np.float64)             # band 7, keep 0/1
    s2_float = np.concatenate([s2_scaled, cloud_band[None, ...]])

    combined_array = np.concatenate(
        [s1_float, s2_float], axis=0)
    print(
        f"🔍 Combined array shape: {combined_array.shape}, dtype: {combined_array.dtype}")

    profile = {
        'driver': 'GTiff',
        'dtype': 'float64',
        'width': 512,
        'height': 512,
        'count': 9,
        'crs': 'EPSG:4326'
    }

    west, south, east, north = bbox
    transform = from_bounds(west, south, east, north, 512, 512)
    profile['transform'] = transform

    with io.BytesIO() as buffer:
        with rasterio.open(buffer, 'w', **profile) as dst:
            dst.write(combined_array)
        buffer.seek(0)
        return buffer.read()


def fetch_sentinel_image(bbox: tuple, target_date: datetime) -> bytes:
    """
    Fetches a 9-band TIFF image combining Sentinel-2 L2A, a cloud mask,
    and Sentinel-1 GRD data, as expected by the flood detection model.

    Updated to use separate requests approach that works with Copernicus Data Space Ecosystem.
    """
    if not SH_CLIENT_ID or not SH_CLIENT_SECRET:
        raise gr.Error(
            "Sentinel Hub credentials (SH_CLIENT_ID, SH_CLIENT_SECRET) are not set.")

    # Create explicit Copernicus configuration
    config = SHConfig()
    config.sh_client_id = SH_CLIENT_ID
    config.sh_client_secret = SH_CLIENT_SECRET
    config.sh_base_url = "https://sh.dataspace.copernicus.eu"

    print(f"✅ Using Copernicus Data Space Ecosystem: {config.sh_base_url}")

    optical_interval = (f"{(target_date - timedelta(days=5)).strftime('%Y-%m-%d')}T00:00:00Z",
                        f"{target_date.strftime('%Y-%m-%d')}T23:59:59Z")
    radar_interval = (f"{target_date.strftime('%Y-%m-%d')}T06:00:00Z",
                      f"{target_date.strftime('%Y-%m-%d')}T06:30:00Z")

    try:
        # Fetch data separately using the working approach
        s2_data = fetch_sentinel2_data(bbox, optical_interval, config)
        s1_data = fetch_sentinel1_data(bbox, radar_interval, config)

        if s2_data is None:
            raise gr.Error("No Sentinel-2 data returned from Copernicus")

        if s1_data is None:
            raise gr.Error("No Sentinel-1 data returned from Copernicus")

        print(f"✅ Got S2 data: {s2_data.size} elements")
        print(f"✅ Got S1 data: {s1_data.size} elements")

        # Combine and return as bytes
        combined_tiff_bytes = combine_sentinel_data(s2_data, s1_data, bbox)
        print(f"✅ Combined TIFF created: {len(combined_tiff_bytes)} bytes")

        return combined_tiff_bytes

    except Exception as e:
        print(f"Error fetching sentinel data: {e}", file=sys.stderr)
        raise gr.Error(f"Failed to fetch satellite data: {e}")


# --- THIS FUNCTION IS MODIFIED ---
def ensure_files_exist():
    """
    On startup, check if the config and model files exist locally.
    If not, download them. **Always applies patches.**
    """
    files_to_check = {
        Path(CONFIG_PATH): {
            "minio": MODEL_CONFIG_FILENAME,
            "fallback": MODEL_CONFIG_FALLBACK_URL,
            "patch_func": normalise_boolean_mode_fields,  # Reference to the patch function
        },
        Path(CHECKPOINT_PATH): {
            "minio": MODEL_CHECKPOINT_FILENAME,
            "fallback": MODEL_CHECKPOINT_FALLBACK_URL,
            "patch_func": _strip_checkpoint_hparams,  # Reference to the patch function
        },
    }

    s3_client = None
    if MINIO_ACCESS_KEY and MINIO_SECRET_KEY:
        try:
            s3_client = boto3.client(
                "s3",
                endpoint_url=MINIO_ENDPOINT,
                aws_access_key_id=MINIO_ACCESS_KEY,
                aws_secret_access_key=MINIO_SECRET_KEY,
                region_name=MINIO_REGION,
                use_ssl=MINIO_ENDPOINT.startswith('https://'),
                verify=MINIO_VERIFY_SSL,
            )
        except Exception as e:
            print(
                f"⚠️ WARNING: Failed to create MinIO client: {e}", file=sys.stderr)
    else:
        print("WARNING: MinIO credentials not found. Falling back to external downloads where available.")

    for local_path, meta in files_to_check.items():
        minio_key = meta["minio"]
        fallback_url = meta["fallback"]
        patch_func = meta["patch_func"]  # Get the patch function

        if not local_path.exists():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            downloaded = False
            if s3_client:
                try:
                    print(f"⬇️ Downloading '{minio_key}' from MinIO...")
                    s3_client.download_file(
                        MINIO_MODELS_BUCKET, minio_key, str(local_path))
                    print(f"✅ Successfully downloaded {local_path} from MinIO")
                    downloaded = True
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code")
                    print(
                        f"⚠️ MinIO download failed for '{minio_key}' (code={error_code}): {e}")
                except Exception as e:
                    print(
                        f"⚠️ Unexpected error downloading '{minio_key}' from MinIO: {e}", file=sys.stderr)

            if not downloaded and fallback_url:
                try:
                    print(
                        f"⬇️ Downloading '{minio_key}' from fallback URL: {fallback_url}")
                    download_file(fallback_url, local_path)
                    downloaded = True
                    if s3_client:
                        try:
                            s3_client.upload_file(
                                str(local_path), MINIO_MODELS_BUCKET, minio_key)
                            print(
                                f"✅ Seeded MinIO bucket '{MINIO_MODELS_BUCKET}' with '{minio_key}'")
                        except Exception as e:
                            print(
                                f"⚠️ Warning: failed to upload '{minio_key}' to MinIO: {e}", file=sys.stderr)
                except Exception as e:
                    print(
                        f"❌ ERROR: Failed to download '{minio_key}' from fallback: {e}", file=sys.stderr)

            if not downloaded:
                print(
                    f"❌ ERROR: Required model asset '{minio_key}' is unavailable.", file=sys.stderr)
                sys.exit(1)
            else:
                # Apply patch immediately after download
                print(f"Applying patch to newly downloaded file: {local_path}")
                patch_func(local_path)
                print(f"✅ File ready: {local_path}")

        else:
            # --- ALWAYS APPLY PATCH ---
            print(f"File already exists locally, applying patch: {local_path}")
            patch_func(local_path)
            # --- END CHANGE ---

# --- END MODIFIED FUNCTION ---


def run_terratorch_inference(input_dir: str, output_dir: str, input_filename: str) -> str:
    """
    Runs terratorch inference on a TIFF file.
    """
    predict_script = "terratorch"
    accelerator = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"✅ Using accelerator='{accelerator}'.")

    command = [
        predict_script, "predict",
        "-c", CONFIG_PATH,
        "--ckpt_path", CHECKPOINT_PATH,
        "--predict_output_dir", output_dir,
        "--data.init_args.predict_data_root", input_dir,
        "--data.init_args.img_grep", input_filename,
        f"--trainer.accelerator={accelerator}",
        "--trainer.devices=1",
        "--data.init_args.batch_size=1",
        "--trainer.default_root_dir=/app/data",
        # --- REMOVED: "--trainer.enable_checkpointing=false" ---
        # This is handled by the injected config patch now
    ]

    print(f"\nExecuting command: {' '.join(command)}")
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_CODE_DIR,
            capture_output=True,
            text=True,
            check=True,
            env=os.environ.copy()
        )
        print("STDOUT:", result.stdout)
        print("STDERR:", result.stderr)
        print("\n✅ Terratorch predict command finished successfully.")

        base_name = Path(input_filename).stem
        expected_output_filename = f"{base_name}_pred.tif"
        output_filepath = Path(output_dir) / expected_output_filename

        if not output_filepath.exists():
            # --- Check common output variation ---
            # Sometimes _pred is omitted
            variation_filename = f"{base_name}.tif"
            variation_filepath = Path(output_dir) / variation_filename
            if variation_filepath.exists():
                print(
                    f"ℹ️ Found output file without '_pred' suffix: {variation_filepath}")
                return str(variation_filepath)
            # --- End check ---
            raise FileNotFoundError(
                f"Inference finished, but expected output file '{output_filepath}' (or variation) was not found.")

        return str(output_filepath)

    except subprocess.CalledProcessError as e:
        print(
            f"❌ Terratorch predict command failed with exit code {e.returncode}.", file=sys.stderr)
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        # Attempt to extract a more specific error from stderr if possible
        stderr_lines = e.stderr.strip().split('\n')
        last_line = stderr_lines[-1] if stderr_lines else "Unknown error"
        raise gr.Error(
            f"Model inference failed. Check logs. Last error line: {last_line}")
    except Exception as e:
        print(f"❌ An error occurred during inference: {e}", file=sys.stderr)
        raise gr.Error(f"An unexpected error occurred during inference: {e}")


def detect_flood_from_url(image_url: str) -> str:
    """
    Performs flood detection on a GeoTIFF image provided via a URL.
    """
    if not image_url:
        raise gr.Error("Input is empty. Please provide a URL to a TIFF image.")

    temp_dir = tempfile.mkdtemp(prefix="flood_detect_url_")

    try:
        temp_dir_path = Path(temp_dir)
        input_dir = temp_dir_path / "input"
        output_dir = temp_dir_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        print(f"Downloading image from: {image_url}")
        response = requests.get(image_url, stream=True)
        response.raise_for_status()

        url_path = image_url.split('?')[0]
        original_filename = url_path.split('/')[-1]
        input_filename = original_filename if original_filename else "input.tif"
        input_filepath = input_dir / input_filename

        with open(input_filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"Input file saved to: {input_filepath}")

        output_filepath = run_terratorch_inference(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            input_filename=input_filename
        )

        minio_url = upload_to_minio(
            output_filepath, Path(output_filepath).name)
        return minio_url

    except requests.exceptions.RequestException as e:
        print(f"Failed to download image from URL: {e}")
        raise gr.Error(f"Could not fetch image from URL: {image_url}")
    except Exception as e:
        print(f"An error occurred: {e}")
        raise gr.Error(str(e))
    # --- Ensure temporary directory cleanup ---
    # finally:
    #     if 'temp_dir_path' in locals() and temp_dir_path.exists():
    #          shutil.rmtree(temp_dir_path)
    #          print(f"Cleaned up temporary directory: {temp_dir_path}")


def detect_flood_from_file(temp_file) -> str:
    """
    Performs flood detection on a directly uploaded GeoTIFF file.
    """
    if temp_file is None:
        raise gr.Error("No file uploaded. Please upload a TIFF image.")

    input_filepath = Path(temp_file.name)
    print(f"Processing uploaded file: {input_filepath}")

    temp_dir = tempfile.mkdtemp(prefix="flood_detect_file_")

    try:
        temp_dir_path = Path(temp_dir)
        input_dir = str(input_filepath.parent)
        output_dir = str(temp_dir_path / "output")
        Path(output_dir).mkdir()
        input_filename = input_filepath.name

        output_filepath = run_terratorch_inference(
            input_dir=input_dir,
            output_dir=output_dir,
            input_filename=input_filename
        )

        minio_url = upload_to_minio(
            output_filepath, Path(output_filepath).name)
        return minio_url

    except Exception as e:
        print(f"An error occurred: {e}")
        raise gr.Error(str(e))
    # --- Ensure temporary directory cleanup ---
    # finally:
    #     if 'temp_dir_path' in locals() and temp_dir_path.exists():
    #          shutil.rmtree(temp_dir_path)
    #          print(f"Cleaned up temporary directory: {temp_dir_path}")


def fetch_and_run_flood_detection(bbox_str: str, analysis_date_timestamp: Union[float, int, str, datetime]) -> str:
    """
    Orchestrates the entire process: fetch from Sentinel Hub, run inference,
    and upload the result.
    """
    if not bbox_str or not analysis_date_timestamp:
        raise gr.Error("Bounding Box and Analysis Date must be provided.")

    temp_dir = None  # Initialize outside try block for finally clause
    try:
        # 1. Parse Inputs from Gradio UI
        try:
            timestamp = coerce_to_timestamp(analysis_date_timestamp)
        except ValueError as exc:
            raise gr.Error(str(exc))
        analysis_date = datetime.fromtimestamp(timestamp).date()

        bbox_parts = [float(p.strip()) for p in bbox_str.split(',')]
        if len(bbox_parts) != 4:
            raise ValueError(
                "Bounding Box must have 4 comma-separated values: min_lon, min_lat, max_lon, max_lat")
        bbox = tuple(bbox_parts)

        # 2. Fetch the satellite image
        print(
            f"Fetching Sentinel Hub image for BBox: {bbox} on {analysis_date.isoformat()}")
        tiff_data_bytes = fetch_sentinel_image(bbox, analysis_date)
        if len(tiff_data_bytes) == 0:
            raise gr.Error(
                "Failed to fetch data from Sentinel Hub. The area might be cloudy or no data is available.")

        # 3. Save the fetched TIFF
        temp_dir = tempfile.mkdtemp(prefix="sentinel_flood_")
        temp_dir_path = Path(temp_dir)
        input_dir = temp_dir_path / "input"
        output_dir = temp_dir_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        input_filename = f"sentinel_image_{analysis_date.isoformat()}.tif"
        input_filepath = input_dir / input_filename
        with open(input_filepath, "wb") as f:
            f.write(tiff_data_bytes)
        print(f"Sentinel TIFF saved to temporary file: {input_filepath}")

        # 4. Run Terratorch inference
        output_filepath = run_terratorch_inference(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            input_filename=input_filename
        )

        # 5. Upload the prediction result to MinIO
        minio_url = upload_to_minio(
            output_filepath, Path(output_filepath).name)

        return minio_url

    except Exception as e:
        print(f"An error occurred during the process: {e}", file=sys.stderr)
        # --- Make error more specific if possible ---
        if isinstance(e, gr.Error):
            raise e  # Re-raise Gradio errors directly
        else:
            raise gr.Error(
                f"An unexpected error occurred: {type(e).__name__} - {e}")
    # --- Ensure temporary directory cleanup ---
    # finally:
    #     if temp_dir and Path(temp_dir).exists():
    #          shutil.rmtree(temp_dir)
    #          print(f"Cleaned up temporary directory: {temp_dir}")


class FloodDetectionRequest(BaseModel):
    bbox_str: str
    analysis_date_timestamp: Union[float, int, str] = Field(
        ..., description="Unix timestamp (seconds) or ISO datetime string")
    backend_url: Optional[str] = None

    def resolved_timestamp(self) -> float:
        try:
            return coerce_to_timestamp(self.analysis_date_timestamp)
        except ValueError as exc:
            raise ValueError(
                f"Invalid analysis_date_timestamp: {self.analysis_date_timestamp}"
            ) from exc

# --- Create the Gradio Interface ---


interface_url = gr.Interface(
    fn=detect_flood_from_url,
    inputs=gr.Textbox(
        lines=1, placeholder="https://path/to/your/satellite_image.tif", label="Image URL"),
    outputs=gr.Textbox(label="MinIO Result URL"),
    title="💧 Flood Detection from URL 🌊",
    description="Provide a public URL to a GeoTIFF image to run flood detection."
)

interface_file = gr.Interface(
    fn=detect_flood_from_file,
    inputs=gr.File(label="Upload GeoTIFF Image",
                   file_types=[".tif", ".tiff"]),
    outputs=gr.Textbox(label="MinIO Result URL"),
    title="💧 Flood Detection from File Upload 🌊",
    description="Upload a GeoTIFF image directly to run flood detection."
)

inferface_coordinates_datetime = gr.Interface(
    fn=fetch_and_run_flood_detection,
    inputs=[
        gr.Textbox(
            label="Bounding Box (min_lon, min_lat, max_lon, max_lat)",
            placeholder="e.g., 28.94, 41.01, 28.99, 41.04"
        ),
        gr.DateTime(
            label="Analysis DateTime",
            value=datetime.now().strftime(DEFAULT_DATETIME_FORMAT),
        )
    ],
    outputs=gr.Textbox(label="🔗 MinIO URL for Flood Prediction Map"),
    title="🛰️ Automated Flood Detection from Satellite Imagery 🌊",
    description="Provide a bounding box and datetime. The service will fetch the corresponding Sentinel-2 satellite image, run it through the flood detection model, and return a link to the prediction map.",
    examples=[
        ["-1.57, 53.80, -1.50, 53.83",
            datetime(2025, 1, 10).strftime(DEFAULT_DATETIME_FORMAT)],
        ["28.85, 40.97, 28.90, 41.00", datetime(
            2025, 7, 17, 15, 30).strftime(DEFAULT_DATETIME_FORMAT)]
    ],
    flagging_mode="never"
)

demo = gr.TabbedInterface(
    [interface_url, interface_file, inferface_coordinates_datetime],
    ["From URL", "From File Upload", "From Coordinates and Date"]
)

api_app = FastAPI(title="Flood Detection Backend", version="1.0.0")


@api_app.get("/health")
async def healthcheck():
    return {"status": "ok"}


@api_app.post("/detect_flood_from_coordinates")
async def detect_flood_from_coordinates(request: FloodDetectionRequest):
    try:
        result_url = fetch_and_run_flood_detection(
            bbox_str=request.bbox_str,
            analysis_date_timestamp=request.resolved_timestamp(),
        )
        return {"status": "success", "result_url": result_url}
    except gr.Error as ge:
        raise HTTPException(status_code=400, detail=str(ge)) from ge
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

app = gr.mount_gradio_app(api_app, demo, path="/")

if __name__ == "__main__":
    ensure_files_exist()

    root_path = os.environ.get("GRADIO_ROOT_PATH", "/")
    print(f"🚀 Launching Uvicorn with root_path: {root_path}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        root_path=root_path
    )
