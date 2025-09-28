import subprocess
import sys
import os
import tempfile
import shutil
import requests  # For downloading the file from URL
import torch  # For GPU detection
from pathlib import Path

from model_paths import CONFIG_PATH, CHECKPOINT_PATH, PROJECT_CODE_DIR


async def run_terratorch_inference_url(
    input_file_url: str,
    original_filename: str  # Keep original name for context/logging
) -> bytes | None:
    """
    Downloads a TIFF file from a URL, runs Terratorch inference,
    and returns the output file content. Detects GPU automatically.

    Args:
        input_file_url: The URL to download the input TIFF file from.
        original_filename: The original filename (used for logging).

    Returns:
        The byte content of the generated prediction TIFF, or None if failed.
    """
    predict_script = "terratorch"
    temp_dir = None  # Initialize to None

    # --- Accelerator Detection ---
    accelerator = 'cpu'
    devices = 1
    try:
        if torch.cuda.is_available():
            accelerator = 'gpu'
            # devices = torch.cuda.device_count() # Or keep it 1 if preferred
            print("✅ GPU detected. Using accelerator='gpu'.")
        else:
            print(
                "ℹ️ No GPU detected or PyTorch CUDA not available. Using accelerator='cpu'.")
    except Exception as e:
        print(
            f"⚠️ Error during GPU detection: {e}. Defaulting to CPU.", file=sys.stderr)
    # --- End Accelerator Detection ---

    try:
        # Create a temporary directory for this request
        temp_dir = tempfile.mkdtemp(prefix="flood_mcp_")
        temp_dir_path = Path(temp_dir)
        input_dir = temp_dir_path / "input"
        output_dir = temp_dir_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Use a fixed temporary input filename
        temp_input_filename = "input.tif"
        input_filepath = input_dir / temp_input_filename

        # --- Download the file ---
        print(f"Downloading file from: {input_file_url}")
        try:
            response = requests.get(
                input_file_url, stream=True, timeout=60)  # Added timeout
            response.raise_for_status()  # Raise an exception for bad status codes
            with open(input_filepath, "wb") as buffer:
                for chunk in response.iter_content(chunk_size=8192):
                    buffer.write(chunk)
            print(f"Temporary input file saved to: {input_filepath}")
        except requests.exceptions.RequestException as e:
            print(
                f"Error downloading file from {input_file_url}: {e}", file=sys.stderr)
            return None
        # --- End Download ---

        # Construct the command with detected accelerator
        command = [
            predict_script,
            "predict",
            "-c", CONFIG_PATH,
            "--ckpt_path", CHECKPOINT_PATH,
            "--predict_output_dir", str(output_dir),
            "--data.init_args.predict_data_root", str(input_dir),
            # Target the specific temp file
            "--data.init_args.img_grep", f"{temp_input_filename}",
            f"--trainer.accelerator={accelerator}",
            f"--trainer.devices={devices}",
            "--data.init_args.batch_size=1",
            "--trainer.default_root_dir=/app/data"
        ]

        print(
            f"\nExecuting command: {' '.join(command)}\nWorking directory: {PROJECT_CODE_DIR}\n")

        process = subprocess.Popen(
            command,
            cwd=PROJECT_CODE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy()
        )

        # Stream output for logging/debugging
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip(), flush=True)

        rc = process.poll()

        if rc == 0:
            print("\nTerratorch predict command finished successfully.")
            # Determine the output filename
            base_name = Path(temp_input_filename).stem
            expected_output_filename = f"{base_name}_pred.tif"
            output_filepath = output_dir / expected_output_filename

            if not output_filepath.exists():
                output_files = list(output_dir.glob('*.tif*'))
                if output_files:
                    print(
                        f"Warning: Expected output '{expected_output_filename}' not found. "
                        f"Using first found TIF: {output_files[0].name}")
                    output_filepath = output_files[0]
                else:
                    print(
                        f"Error: No output TIF file found in {output_dir}", file=sys.stderr)
                    return None

            # Read the output file content
            if output_filepath.exists():
                print(f"Reading output file: {output_filepath}")
                with open(output_filepath, "rb") as f:
                    output_content = f.read()
                return output_content
            else:
                print(
                    f"Error: Determined output file path does not exist: {output_filepath}", file=sys.stderr)
                return None
        else:
            print(
                f"\nTerratorch predict command failed with exit code {rc}.",
                file=sys.stderr
            )
            return None

    except FileNotFoundError:
        print(
            f"Error: Command '{predict_script}' not found. Is terratorch installed and in PATH?",
            file=sys.stderr
        )
        return None
    except Exception as e:
        print(
            f"An error occurred during inference execution: {e}", file=sys.stderr)
        return None
    finally:
        # Cleanup the temporary directory
        if temp_dir and Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e_clean:
                print(
                    f"Error cleaning up temp directory {temp_dir}: {e_clean}", file=sys.stderr)


async def run_terratorch_inference(
    config_path: str,
    checkpoint_path: str,
    input_dir: str,
    output_dir: str,
    project_code_dir: str,
    input_filename: str
) -> str:
    """
    Runs terratorch inference on a local TIFF file and returns the filename of the output file.
    
    Args:
        config_path: Path to the configuration file
        checkpoint_path: Path to the model checkpoint
        input_dir: Directory containing the input file
        output_dir: Directory where output will be saved
        project_code_dir: Directory where terratorch command should run
        input_filename: Name of the input file
        
    Returns:
        Filename of the output file if successful, None otherwise
    """
    predict_script = "terratorch"
    
    # Detect GPU availability
    accelerator = 'cpu'
    devices = 1
    try:
        if torch.cuda.is_available():
            accelerator = 'gpu'
            print("✅ GPU detected. Using accelerator='gpu'.")
        else:
            print("ℹ️ No GPU detected or PyTorch CUDA not available. Using accelerator='cpu'.")
    except Exception as e:
        print(f"⚠️ Error during GPU detection: {e}. Defaulting to CPU.", file=sys.stderr)
    
    # Construct the command
    command = [
        predict_script,
        "predict",
        "-c", config_path,
        "--ckpt_path", checkpoint_path,
        "--predict_output_dir", output_dir,
        "--data.init_args.predict_data_root", input_dir,
        # Use the specific input filename
        "--data.init_args.img_grep", input_filename,
        f"--trainer.accelerator={accelerator}",
        f"--trainer.devices={devices}",
        "--data.init_args.batch_size=1",
        "--trainer.default_root_dir=/app/data"
    ]
    
    print(f"\nExecuting command: {' '.join(command)}\nWorking directory: {project_code_dir}\n")
    
    try:
        process = subprocess.Popen(
            command,
            cwd=project_code_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy()
        )
        
        # Stream output for logging/debugging
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(output.strip(), flush=True)
        
        rc = process.poll()
        
        if rc == 0:
            print("\nTerratorch predict command finished successfully.")
            
            # Determine the output filename
            base_name = Path(input_filename).stem
            expected_output_filename = f"{base_name}_pred.tif"
            output_filepath = Path(output_dir) / expected_output_filename
            
            if not output_filepath.exists():
                output_files = list(Path(output_dir).glob('*.tif*'))
                if output_files:
                    print(
                        f"Warning: Expected output '{expected_output_filename}' not found. "
                        f"Using first found TIF: {output_files[0].name}")
                    output_filepath = output_files[0]
                else:
                    print(f"Error: No output TIF file found in {output_dir}", file=sys.stderr)
                    return None
            
            return output_filepath.name
        else:
            print(f"\nTerratorch predict command failed with exit code {rc}.", file=sys.stderr)
            return None
    
    except FileNotFoundError:
        print(
            f"Error: Command '{predict_script}' not found. Is terratorch installed and in PATH?",
            file=sys.stderr
        )
        return None
    except Exception as e:
        print(f"An error occurred during inference execution: {e}", file=sys.stderr)
        return None
