import streamlit as st
import openrouteservice
import numpy as np
import requests
import json
import os


def _get_secret(key: str, default=None):
    """Safely fetch a Streamlit secret without requiring secrets.toml."""
    try:
        secrets_obj = st.secrets
    except Exception:
        return default
    return secrets_obj.get(key, default)

# --- Caching Functions for API Calls ---


@st.cache_data
def get_distance_matrix(coords):
    """Fetches a distance matrix from OpenRouteService."""
    api_key = os.environ.get("ORS_API_KEY") or _get_secret("ORS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ORS_API_KEY is not configured. Set it in your .env file or .streamlit/secrets.toml."
        )
    client = openrouteservice.Client(key=api_key)
    matrix = client.distance_matrix(
        locations=coords, profile='driving-car', metrics=['distance'], units='km')
    return (np.array(matrix["distances"]) * 1000).astype(int)


@st.cache_data
def get_directions(route_coords):
    """Fetches detailed route geometry from OpenRouteService."""
    api_key = os.environ.get("ORS_API_KEY") or _get_secret("ORS_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ORS_API_KEY is not configured. Set it in your .env file or .streamlit/secrets.toml."
        )
    client = openrouteservice.Client(key=api_key)
    return client.directions(
        coordinates=route_coords,
        profile='driving-car',
        format='geojson'
    )


def get_flood_overlay_from_langflow(bbox, analysis_date):
    """
    Sends route coordinates and a single date to the Langflow endpoint.
    Returns structured data for flood detection.
    """
    url = "http://datastax-langflow-langflow.apps.cluster-r8fxn.r8fxn.sandbox753.opentlc.com/api/v1/run/8ea6762f-4e34-4354-a714-1ba99a02b236"
    api_key = _get_secret("LANGFLOW_API_KEY", "")

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Create the data structure as expected by your Langflow component
    input_data = {
        "bounding_box": ",".join(map(str, bbox)),
        "analysis_date": analysis_date
    }

    # The input to your flow should be a JSON string of this data
    input_value_string = json.dumps(input_data)

    payload = {
        "input_value": input_value_string,
        "output_type": "chat",
        "input_type": "chat"
    }

    try:
        st.write(f"🔍 Calling Langflow for tile: {bbox}")

        response = requests.post(url, headers=headers,
                                 json=payload, timeout=60)
        response.raise_for_status()

        st.write("✅ Received response from Langflow")

        response_data = response.json()
        if 'outputs' in response_data and response_data['outputs']:
            # Navigate through the nested structure to get the final message text
            message_text = response_data['outputs'][0]['outputs'][0]['results']['message']['text']

            # Log what we received
            st.write(f"📝 Response text: {message_text[:200]}...")

            # The response should contain either a URL or JSON data
            # Return the raw text for now - the flood_detection module will parse it
            return message_text
        else:
            st.warning(
                "Langflow response did not contain the expected output format.")
            return None

    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP error occurred: {http_err}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Request error: {e}")
        return None
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        return None
