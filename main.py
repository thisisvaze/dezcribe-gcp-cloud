import os
import shutil
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from pydantic import BaseModel
import asyncio


from util.Constants import BUCKET_NAME
from util.gcs_bucket import download_from_gcs, upload_to_gcs
from util.text_to_speech import main_function


class VideoProcessRequest(BaseModel):
    video_path: str

app = FastAPI()

@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    file_location = f"/tmp/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    gcs_url = upload_to_gcs(BUCKET_NAME, file_location, file.filename)

    # Create a VideoProcessRequest object
    request = VideoProcessRequest(video_path=file_location)
    
    
    # Call your processing function here
    result = await process_video(request)
    
    return {"result": result, "gcs_url": gcs_url}



@app.post("/process_video")
async def process_video(request: VideoProcessRequest):
    video_path = request.video_path

    if not video_path:
        raise HTTPException(status_code=400, detail="video_path is required")

    result = await main_function(video_path)
    
    return result

@app.get("/")
async def hello_world():
    name = os.environ.get("NAME", "World")
    return {"message": f"Hello {name}!"}

@app.get("/download_video/{file_name}")
async def download_video(file_name: str):
    bucket_name = BUCKET_NAME
    destination_file_name = f"/tmp/{file_name}"
    
    try:
        download_from_gcs(bucket_name, file_name, destination_file_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {"file_path": destination_file_name}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), log_level="debug")