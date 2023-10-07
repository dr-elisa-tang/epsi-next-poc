import boto3
import os
import sys

# Read AWS credentials and region from environment variables
AWS_ACCESS_KEY_ID = os.environ.get('AWSAccessKeyID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWSSecretAccessKey')
AWS_REGION = os.environ.get('AWSRegion')
INBOUND_S3 = 'inbound-pdfs'
OUTBOUND_S3 = 'outbound-jsons'

def upload_pdf(file_path):
    try:
        # Initialize the S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        # Extract the file name from the path
        file_name = os.path.basename(file_path)

        # Upload the file to the specified S3 bucket
        s3_client.upload_file(file_path, INBOUND_S3, file_name)

        print(f"")
        print(f"'{file_name}' uploaded successfully.")
    except Exception as e:
        print(f"Error uploading file: {str(e)}")

def fetch_json(file_name):
    try:
        # Initialize the S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )

        # Retrieve the object from S3
        response = s3_client.get_object(Bucket=OUTBOUND_S3, Key=file_name)

        # Read and display the contents of the object (file)
        file_contents = response['Body'].read().decode('utf-8')
        print(f"")
        print (f"'{file_contents}'")
    except Exception as e:
        print(f"Error retrieving and displaying file: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python text-extraction.py <file_path>")
        sys.exit(1)

    file_path = sys.argv[1]
    upload_pdf(file_path)


    file_name = os.path.basename(file_path) + ".json"
    fetch_json(file_name)