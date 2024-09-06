from google.cloud import storage
import os
import logging
import json
from google.oauth2 import service_account
from urllib.parse import unquote

def get_storage_client():
    gc_key_json = os.getenv("MY_GC_KEY_SECRET")
    if gc_key_json:
        gc_key_dict = json.loads(gc_key_json)
        credentials = service_account.Credentials.from_service_account_info(gc_key_dict)
        return storage.Client(credentials=credentials)
    else:
        logging.error("Google Cloud key JSON not found in environment variable MY_GC_KEY_SECRET")
        return storage.Client()



def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    storage_client = get_storage_client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    
    # Check if the file exists in the bucket
    if not blob.exists():
        raise Exception(f"Failed to upload {destination_blob_name} to bucket {bucket_name}")
    
    return destination_blob_name 

def download_from_gcs(bucket_name, source_blob_name, destination_file_name):
    storage_client = get_storage_client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(unquote(source_blob_name))
    
    #logging.info(f"Starting download of {source_blob_name} from bucket {bucket_name} to {destination_file_name}")
    blob.download_to_filename(destination_file_name)
    
    if os.path.getsize(destination_file_name) == 0:
        logging.error(f"Downloaded file {destination_file_name} is empty.")
        raise Exception(f"Failed to download {source_blob_name} from bucket {bucket_name}")
    
    #logging.info(f"Successfully downloaded {source_blob_name} to {destination_file_name}")
    return destination_file_name

def download_multiple_from_gcs(bucket_name, source_blob_names, destination_file_names):
    storage_client = get_storage_client()
    if len(source_blob_names) != len(destination_file_names):
        raise ValueError("Source and destination lists must have the same length")
    
    for source_blob_name, destination_file_name in zip(source_blob_names, destination_file_names):
        download_from_gcs(bucket_name, source_blob_name, destination_file_name)
    
    return destination_file_names