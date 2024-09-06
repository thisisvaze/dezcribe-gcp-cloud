from google.cloud import storage

# Initialize Google Cloud Storage client
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