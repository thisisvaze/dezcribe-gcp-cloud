import os
import shutil
from fastapi import FastAPI, Request, HTTPException, Response, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import storage
from datetime import timedelta
from fastapi.logger import logger
import asyncio
from fastapi.responses import FileResponse, JSONResponse

from util.Constants import BUCKET_NAME
from util.gcs_bucket import download_from_gcs, download_multiple_from_gcs, upload_to_gcs
from util.text_to_speech import main_function


class VideoProcessRequest(BaseModel):
    video_path: str

app = FastAPI()

signed_urls = {}

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload_video")
async def upload_video(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    try:
        file_location = f"/tmp/{file.filename}"
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        gcs_url = upload_to_gcs(BUCKET_NAME, file_location, file.filename)

        # Generate the output video name
        output_video_name = os.path.splitext(file.filename)[0] + "_output.mp4"

        # Add the video processing task to the background
        background_tasks.add_task(process_video_task, file_location, file.filename)
        
        return {"status": "processing", "gcs_url": gcs_url, "output_video_name": output_video_name}
    except Exception as e:
        logger.error(f"Error in /upload_video: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

async def process_video_task(file_location: str, filename: str):
    try:
        # Create a VideoProcessRequest object
        request = VideoProcessRequest(video_path=file_location)
        
        # Call your processing function here
        result = await process_video(request)
        
        # Assuming the processed video is saved with a different name or in a different location
        processed_video_filename = os.path.basename(result["output_url"])
        processed_video_location = f"/tmp/{processed_video_filename}"
        
        # Generate signed URL for the processed video
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(processed_video_filename)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),  # URL valid for 15 minutes
            method="GET"
        )
        
        # Log the signed URL
        logger.info(f"Signed URL: {signed_url}")
        
        # Store the signed URL in the in-memory dictionary
        signed_urls[processed_video_filename] = signed_url
        
    except Exception as e:
        logger.error(f"Error in process_video_task: {e}")


    
@app.post("/process_video")
async def process_video(request: VideoProcessRequest):
    video_path = request.video_path

    if not video_path:
        raise HTTPException(status_code=400, detail="video_path is required")

    result = await main_function(video_path)
    
    return result

@app.get("/download_sample_videos")
async def download_sample_videos():
    bucket_name = BUCKET_NAME
    source_blob_names = ["sample_video1.mp4", "sample_video2.mp4"]
    ui_names = ["Battery", "Smoothie"]
    
    signed_urls = []
    storage_client = storage.Client()
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
            print(f"Error generating signed URL for {blob_name}: {e}")
            raise HTTPException(status_code=500, detail=f"Error generating signed URL for {blob_name}")
    
    return signed_urls

@app.get("/serve_video/{video_name}")
async def serve_video(video_name: str):
    bucket_name = BUCKET_NAME
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    
    # Mapping of UI names to blob names
    video_mapping = {
        "Battery": "sample_video1.mp4",
        "Smoothie": "sample_video2.mp4"
    }
    
    blob_name = video_mapping.get(video_name)
    if not blob_name:
        raise HTTPException(status_code=404, detail="Video not found")
    
    blob = bucket.blob(blob_name)
    
    try:
        video_data = blob.download_as_bytes()
        return Response(content=video_data, media_type="video/mp4")
    except Exception as e:
        print(f"Error serving video {video_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Error serving video {video_name}")

@app.get("/")
async def hello_world():
    name = os.environ.get("NAME", "World")
    return {"message": f"Hello {name}!"}

@app.get("/download_video/{file_name}")
async def download_video(file_name: str):
    try:
        # Retrieve the signed URL from the in-memory dictionary
        signed_url = signed_urls.get(file_name)
        if not signed_url:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {"signed_url": signed_url}
    except Exception as e:
        logger.error(f"Error retrieving signed URL for {file_name}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving signed URL")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="debug")