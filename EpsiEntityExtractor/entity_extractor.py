import io
import json
import os
import PyPDF2 as PyPDF2
import boto3
import botocore.exceptions
import logging

# Initialize AWS S3 and Textract clients
s3 = boto3.client('s3')
textract = boto3.client('textract')

# Configure logging
logger = logging.getLogger()
# Use the LOG_LEVEL environmental variable if available, otherwise default to 'INFO'
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logger.setLevel(log_level)

# Get the S3 output bucket name from the environmental variable
output_bucket = os.environ.get('S3_OUTPUT_BUCKET')

# Check if the S3 output bucket exists
if not output_bucket:
    logger.error("S3_OUTPUT_BUCKET environmental variable is not set.")
    raise Exception("S3_OUTPUT_BUCKET environmental variable is not set.")

# Verify if the specified S3 bucket exists
s3_resource = boto3.resource('s3')
try:
    s3_resource.meta.client.head_bucket(Bucket=output_bucket)
except botocore.exceptions.ClientError as e:
    if e.response['Error']['Code'] == '404':
        logger.error(f"S3 output bucket '{output_bucket}' does not exist.")
        raise


# Function to download a PDF file from S3
def download_pdf_from_s3(bucket, key):
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        return response['Body'].read()
    except Exception as e:
        logger.error(f"Error downloading PDF from S3: {str(e)}")
        raise


# Function to split a PDF into multiple pages and return them as a list of PDF files
def split_pdf_into_pages(pdf_data):
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_data))
        pdf_pages = pdf_reader.pages

        # Create a list to store individual PDF pages
        pdf_page_list = []

        for page_num, pdf_page in enumerate(pdf_pages):
            # Create a new PDF writer for each page
            pdf_writer = PyPDF2.PdfWriter()
            pdf_writer.add_page(pdf_page)

            # Create a new PDF in-memory file
            pdf_output = io.BytesIO()
            pdf_writer.write(pdf_output)
            pdf_output.seek(0)

            # Append the PDF page data to the list
            pdf_page_list.append(pdf_output)

        return pdf_page_list
    except Exception as e:
        logger.error(f"Error splitting PDF into pages: {str(e)}")
        raise


# Function to write JSON data to S3
def write_json_to_s3(tracking_id, json_data, output_bucket):
    try:
        # Define the S3 key for the JSON file
        json_key = f"{tracking_id}/jobs.json"

        # Upload the JSON data to the output S3 bucket
        s3.put_object(Bucket=output_bucket, Key=json_key, Body=json_data)
    except Exception as e:
        logger.error(f"Error writing JSON to S3: {str(e)}")
        raise


# Function to move the original PDF to the output directory
def move_pdf_to_output_directory(input_bucket, output_bucket, input_key, tracking_id):
    try:
        # Define the destination key for the PDF file within the tracking_id directory
        destination_key = f"{tracking_id}/{input_key}"

        # Copy the PDF file from the input S3 bucket to the output S3 bucket
        s3.copy_object(CopySource={'Bucket': input_bucket, 'Key': input_key},
                       Bucket=output_bucket, Key=destination_key)

        # Delete the original PDF file from the input S3 bucket
        s3.delete_object(Bucket=input_bucket, Key=input_key)
    except Exception as e:
        logger.error(f"Error moving PDF to output directory: {str(e)}")
        raise


# Main function to analyze a document
def analyze_document(bucket, output_bucket, key, textract_client):
    try:
        # Download the PDF file from S3
        input_pdf_data = download_pdf_from_s3(bucket, key)
        logger.info(f"Processing object: {key}")
        jobs_list = []

        # Generate a tracking ID for the document based on the filename
        tracking_id = os.path.splitext(key)[0]

        # Split the entire PDF document into a list of separate PDF pages
        pdf_pages = split_pdf_into_pages(input_pdf_data)

        for page_num, pdf_page in enumerate(pdf_pages):
            # Define the S3 key for the output PDF page
            output_key = f"{tracking_id}/{key.rsplit('.', 1)[0]}_page_{(page_num + 1):03d}.pdf"

            # Upload the output PDF page to the output S3 bucket
            logger.info(f"Uploading file: {output_key}")
            s3.upload_fileobj(pdf_page, output_bucket, output_key)

            # Call Textract to analyze the document
            logger.info(f"Analyzing file: {output_key}")
            response = textract_client.start_document_analysis(
                DocumentLocation={'S3Object': {'Bucket': output_bucket, 'Name': output_key}},
                FeatureTypes=["QUERIES", 'SIGNATURES'],
                QueriesConfig={
                    "Queries": [
                        {
                            "Text": "What is the patient's or veteran's name?",
                            "Alias": "PATIENT_NAME"
                        },
                        {
                            "Text": "What is the patient's or veteran's date of birth?",
                            "Alias": "PATIENT_DOB"
                        },
                        {
                            "Text": "What is the ordering provider's or doctor's name?",
                            "Alias": "PROVIDER_NAME"
                        },
                        {
                            "Text": "What is the date in the fax header?",
                            "Alias": "FAX_DATE"
                        },
                        {
                            "Text": "What is the visit, procedure, or service date?",
                            "Alias": "SERVICE_DATE"
                        }
                    ]
                }
            )

            # Convert the Textract job response to JSON
            logger.info(f"Converting Textract job response to JSON")
            job = json.loads(json.dumps(response))
            job["PageNum"] = page_num + 1
            jobs_list.append(job)

        # Create a result for the current document
        logger.info(f"Creating final JSON")
        file_result = {
            "tracking_id": tracking_id,
            "filename": key,
            "jobs": jobs_list
        }

        # Convert the result to a formatted JSON string
        json_result = json.dumps(file_result, indent=4)

        # Write the JSON result to the S3 bucket within the tracking_id directory
        write_json_to_s3(tracking_id, json_result, output_bucket)

        # Move the original PDF file to the output directory
        logger.info(f"Moving PDF file to {output_bucket}: {key}")
        move_pdf_to_output_directory(bucket, output_bucket, key, tracking_id)

        logger.info(f"Processing complete: {key}")
        logger.info(f"Tracking ID: {tracking_id}")
        return tracking_id
    except Exception as e:
        logger.error(f"Error in analyze_document: {str(e)}")
        raise


def lambda_handler(event, context):
    try:
        for record in event['Records']:
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']

            # Check if the object in S3 ends with '.pdf' before processing
            if key.endswith('.pdf'):
                logger.info(f"Processing object: s3://{bucket}/{key}")
                analyze_document(bucket, output_bucket, key, textract)
                logger.info(f"Processing complete: s3://{bucket}/{key}")

    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
