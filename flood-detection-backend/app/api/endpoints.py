import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

import inference  # Import the inference logic module
from model_paths import CONFIG_PATH, CHECKPOINT_PATH, PROJECT_CODE_DIR

router = APIRouter()


def cleanup_temp_dir(temp_dir: Path):
    """Removes the temporary directory."""
    try:
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temporary directory: {temp_dir}")
    except Exception as e:
        print(f"Error cleaning up temp directory {temp_dir}: {e}")


@router.post("/predict/", response_class=FileResponse)
async def predict_flood_map(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...,
                            description="Input TIFF file for flood detection.")
):
    """
    Accepts a TIFF file, runs flood detection inference, and returns the
    resulting flood map TIFF file.
    """
    if not file.filename.lower().endswith(".tif") and not file.filename.lower().endswith(".tiff"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Only .tif or .tiff files are accepted.")

    # Create a temporary directory for this request
    temp_dir = tempfile.mkdtemp(prefix="flood_detect_")
    temp_dir_path = Path(temp_dir)
    input_dir = temp_dir_path / "input"
    output_dir = temp_dir_path / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    input_filepath = input_dir / file.filename

    try:
        # Save the uploaded file temporarily
        with open(input_filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"Input file saved to: {input_filepath}")

        # Run inference using the logic from inference.py
        # Pass necessary paths and parameters
        output_filename = await inference.run_terratorch_inference(
            config_path=CONFIG_PATH,
            checkpoint_path=CHECKPOINT_PATH,
            # Pass the directory containing the input file
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            project_code_dir=PROJECT_CODE_DIR,
            input_filename=file.filename  # Needed to find the output
        )

        if output_filename is None:
            raise HTTPException(
                status_code=500, detail="Inference failed to produce an output file.")

        output_filepath = output_dir / output_filename
        print(f"Output file generated at: {output_filepath}")

        if not output_filepath.exists():
            raise HTTPException(
                status_code=500, detail=f"Inference finished but output file not found at {output_filepath}")

        # Add cleanup task to run after response is sent
        background_tasks.add_task(cleanup_temp_dir, temp_dir_path)

        # Return the generated prediction file
        return FileResponse(
            path=output_filepath,
            media_type='image/tiff',
            filename=output_filename  # Use the actual output filename
        )

    except HTTPException as http_exc:
        # Ensure cleanup happens even if there's an HTTP exception before response
        cleanup_temp_dir(temp_dir_path)
        raise http_exc  # Re-raise the exception
    except Exception as e:
        # Ensure cleanup happens on any unexpected error
        cleanup_temp_dir(temp_dir_path)
        print(f"An unexpected error occurred: {e}")
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {e}")
    finally:
        # Close the uploaded file explicitly
        await file.close()

# Add __init__.py files if they don't exist
# Create /Users/mcawte/Projects/flood_detection/app/__init__.py (can be empty)
# Create /Users/mcawte/Projects/flood_detection/app/api/__init__.py (can be empty)
