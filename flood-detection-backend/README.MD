# Flood Detection - Dockerized Inference

This project provides a Dockerized setup for running the Granite Geospatial UKI Flood Detection model.

## 🛠 Build the Docker Image

To build the Docker image locally:

```bash
docker build -t flood-detection .
```

## ▶️ Run the Container

To run the container and mount local directories for input data and output results:

```bash
docker run -it --rm \
  -v /path/to/your/input:/app/data/input \
  -v /path/to/your/output:/app/data/output \
  flood-detection
```

Replace the paths with your actual directories:

- `/path/to/your/input` — directory containing input `.tif` images (e.g., Sentinel-1/2 composites)
- `/path/to/your/output` — directory where prediction outputs will be saved

## 📁 Directory Structure Inside Container

- Input files should be placed in: `/app/data/input`
- Output results will be saved to: `/app/data/output`

## 🔧 Notes

- Make sure the input files follow the expected naming and format (e.g., multi-band GeoTIFFs).
- Modify the entrypoint or command in the Dockerfile if you want automatic inference at container start.

## 📦 Clean Up

To stop the container and remove it:

```bash
# if running in detached mode
docker stop <container_id>
```
