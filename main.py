from flask import Flask, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
import os
import shutil
from google.cloud import storage
from datetime import timedelta
import logging
import asyncio
from util.Constants import BUCKET_NAME
from util.gcs_bucket import download_from_gcs, download_multiple_from_gcs, upload_to_gcs, get_storage_client
from util.text_to_speech import main_function
import json
from google.oauth2 import service_account

storage_client = get_storage_client()

class VideoProcessRequest:
    def __init__(self, video_path: str):
        self.video_path = video_path

app = Flask(__name__)

VIDDYSCRIBE_API_KEY = os.getenv("VIDDYSCRIBE_API_KEY")

signed_urls = {}

# Add CORS middleware
from flask_cors import CORS
CORS(app, resources={r"/*": {"origins": "*"}})

def verify_api_key():
    api_key = request.headers.get("Authorization")
    if not api_key or api_key != f"Bearer {VIDDYSCRIBE_API_KEY}":
        return jsonify({"detail": "Invalid API Key"}), 403

@app.route("/upload_video", methods=["POST"])
def upload_video():
    error_response = verify_api_key()
    if error_response:
        return error_response

    try:
        file = request.files['file']
        filename = secure_filename(file.filename)
        file_location = f"/tmp/{filename}"
        file.save(file_location)
        
        gcs_url = upload_to_gcs(BUCKET_NAME, file_location, filename)

        # Generate the output video name
        output_video_name = os.path.splitext(filename)[0] + "_output.mp4"

        # Add the video processing task to the background
        asyncio.run(process_video_task(gcs_url))
        
        return jsonify({"status": "processing", "gcs_url": gcs_url, "output_video_name": output_video_name})
    except Exception as e:
        logging.error(f"Error in /upload_video: {e}")
        return jsonify({"detail": "Internal Server Error"}), 500

async def process_video_task(gcs_url: str):
    try:
        # Create a VideoProcessRequest object
        request = VideoProcessRequest(video_path=gcs_url)
        
        # Call your processing function here
        result = await process_video(request)
        
        if not isinstance(result, dict) or 'status' not in result:
            raise ValueError("Invalid result format from process_video")

        if result['status'] == 'error':
            logging.error(f"Error processing video: {result.get('message', 'Unknown error')}")
            return

        if 'output_url' not in result:
            logging.error("No output_url in result")
            return

        # Assuming the processed video is saved with a different name or in a different location
        processed_video_filename = os.path.basename(result["output_url"])
        
        # Generate signed URL for the processed video
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(processed_video_filename)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),  # URL valid for 15 minutes
            method="GET"
        )
        
        # Log the signed URL
        logging.info(f"Signed URL: {signed_url}")
        
        # Store the signed URL in the in-memory dictionary
        signed_urls[processed_video_filename] = signed_url
        
    except Exception as e:
        logging.error(f"Error in process_video_task: {str(e)}")

@app.route("/process_video", methods=["POST"])
async def process_video(request):
    video_path = request.video_path

    if not video_path:
        return jsonify({"status": "error", "message": "video_path is required"}), 400

    try:
        result = await main_function(video_path)
        if not isinstance(result, dict):
            raise ValueError("main_function did not return a dictionary")
        return result
    except Exception as e:
        logging.error(f"Error in process_video: {str(e)}")
        return {"status": "error", "message": str(e)}
    

@app.route("/download_sample_videos", methods=["GET"])
def download_sample_videos():
    bucket_name = BUCKET_NAME
    source_blob_names = ["sample_video1.mp4", "sample_video2.mp4"]
    ui_names = ["Battery", "Smoothie"]
    
    signed_urls = []
    bucket = storage_client.bucket(bucket_name)
    
    for blob_name, ui_name in zip(source_blob_names, ui_names):
        blob = bucket.blob(blob_name)
        try:
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15),  # URL valid for 15 minutes
                method="GET"
            )
            signed_urls.append({"name": ui_name, "url": signed_url})
        except Exception as e:
            logging.error(f"Error generating signed URL for {blob_name}: {e}")
            return jsonify({"detail": f"Error generating signed URL for {blob_name}"}), 500
    
    return jsonify(signed_urls)

@app.route("/serve_video/<video_name>", methods=["GET"])
def serve_video(video_name: str):
    bucket_name = BUCKET_NAME
    bucket = storage_client.bucket(bucket_name)
    
    # Mapping of UI names to blob names
    video_mapping = {
        "Battery": "sample_video1.mp4",
        "Smoothie": "sample_video2.mp4"
    }
    
    blob_name = video_mapping.get(video_name)
    if not blob_name:
        return jsonify({"detail": "Video not found"}), 404
    
    blob = bucket.blob(blob_name)
    
    try:
        video_data = blob.download_as_bytes()
        return Response(video_data, mimetype="video/mp4")
    except Exception as e:
        logging.error(f"Error serving video {video_name}: {e}")
        return jsonify({"detail": f"Error serving video {video_name}"}), 500

@app.route("/", methods=["GET"])
def hello_world():
    name = os.environ.get("NAME", "World")
    return jsonify({"message": f"Hello {name}!"})

@app.route("/download_video/<file_name>", methods=["GET"])
def download_video(file_name: str):
    try:
        # Retrieve the signed URL from the in-memory dictionary
        signed_url = signed_urls.get(file_name)
        if not signed_url:
            return jsonify({"detail": "File not found"}), 404
        
        return jsonify({"signed_url": signed_url})
    except Exception as e:
        logging.error(f"Error retrieving signed URL for {file_name}: {e}")
        return jsonify({"detail": "Error retrieving signed URL"}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))