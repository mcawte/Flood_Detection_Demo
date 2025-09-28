# debug_container.py
import os
import sys

# Print environment
print("=== Python Environment ===")
print(f"Python version: {sys.version}")
print(f"GDAL_DATA: {os.environ.get('GDAL_DATA', 'Not set')}")

# Try to import and print versions of key libraries
print("\n=== Library Versions ===")
try:
    import rasterio
    print(f"Rasterio version: {rasterio.__version__}")
except ImportError:
    print("Rasterio not installed")

try:
    from osgeo import gdal
    print(f"GDAL version: {gdal.VersionInfo()}")
except ImportError:
    print("GDAL not installed")

try:
    import rioxarray
    print(f"Rioxarray version: {rioxarray.__version__}")
except ImportError:
    print("Rioxarray not installed")

# Check file structure
print("\n=== Directory Structure ===")
input_dir = "/app/data/input"
print(f"Input directory exists: {os.path.exists(input_dir)}")

# If input directory exists, list contents
if os.path.exists(input_dir):
    print("\nContents of /app/data/input:")
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        if os.path.isdir(item_path):
            print(f"  Directory: {item}")
            # List first few files in subdirectory
            files = os.listdir(item_path)[:5]  # Show up to 5 files
            for file in files:
                print(f"    - {file}")
            if len(os.listdir(item_path)) > 5:
                print(f"-... ({len(os.listdir(item_path)) - 5} more files)")
        else:
            print(f"  File: {item}")

# Check for TIF files
print("\n=== TIF Files ===")
tif_count = 0
for root, dirs, files in os.walk(input_dir):
    for file in files:
        if file.endswith('.tif'):
            tif_count += 1
            if tif_count <= 5:  # Show details for up to 5 files
                tif_path = os.path.join(root, file)
                print(f"Found TIF: {tif_path}")
                try:
                    # Try to open with rasterio
                    import rasterio
                    with rasterio.open(tif_path) as src:
                        print(f"  - Bands: {src.count}")
                        print(f"  - Size: {src.width}x{src.height}")
                except Exception as e:
                    print(f"  - Error opening file: {e}")

print(f"\nTotal TIF files found: {tif_count}")

# Check terratorch configuration
print("\n=== Config Check ===")
model_dir = "/app/models"
if os.path.exists(model_dir):
    print(f"Models directory exists: {os.listdir(model_dir)}")
else:
    print("Models directory doesn't exist")