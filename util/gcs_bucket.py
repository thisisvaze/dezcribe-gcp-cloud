from google.cloud import storage
import os
import logging
import json
from google.oauth2 import service_account

# Load the Google Cloud key JSON from the environment variable
gc_key_json = os.getenv("MY_GC_KEY_SECRET")
if gc_key_json:
    gc_key_dict = json.loads(gc_key_json)
    credentials = service_account.Credentials.from_service_account_info(gc_key_dict)
    storage_client = storage.Client(credentials=credentials)
else:
    logging.error("Google Cloud key JSON not found in environment variable MY_GC_KEY_SECRET")
    storage_client = storage.Client() 

def upload_to_gcs(bucket_name, source_file_name, destination_blob_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    return blob.public_url

def download_from_gcs(bucket_name, source_blob_name, destination_file_name):
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    blob.download_to_filename(destination_file_name)
    return destination_file_name

def download_multiple_from_gcs(bucket_name, source_blob_names, destination_file_names):
    if len(source_blob_names) != len(destination_file_names):
        raise ValueError("Source and destination lists must have the same length")
    
    for source_blob_name, destination_file_name in zip(source_blob_names, destination_file_names):
        download_from_gcs(bucket_name, source_blob_name, destination_file_name)
    
    return destination_file_names