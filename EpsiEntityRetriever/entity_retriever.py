import os
import json
from collections import OrderedDict
import boto3
import botocore.exceptions
import time
import logging
import requests

# Configure logging
logger = logging.getLogger()
# Use the LOG_LEVEL environmental variable if available, otherwise default to 'INFO'
log_level = os.environ.get('LOG_LEVEL', 'INFO')
logger.setLevel(log_level)

# Initialize the S3 client
s3 = boto3.client('s3')
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

# Define the external URL as an environment variable
epsi_endpoint = os.environ.get('EPSI_ENDPOINT')

# Check if the EPSI_ENDPOINT environmental variable is set
if not epsi_endpoint:
    logger.error("EPSI_ENDPOINT environmental variable is not set.")
    raise Exception("EPSI_ENDPOINT environmental variable is not set.")

# Define a threshold for deciding whether the RFS is signed
# Use the SIGNATURE_THRESHOLD environmental variable if available, otherwise default to 50% confidence
SIGNATURE_THRESHOLD = float(os.environ.get('SIGNATURE_THRESHOLD', '50'))

# Define a threshold for deciding whether the page is blank
# Use the BLANK_PAGE_THRESHOLD environmental variable if available, otherwise default to 20 words
BLANK_PAGE_THRESHOLD = int(os.environ.get('BLANK_PAGE_THRESHOLD', '20'))


def get_jobs(tracking_id, output_bucket):
    try:
        # Construct the S3 object key based on the tracking_id
        object_key = f'{tracking_id}/jobs.json'

        # Retrieve the JSON file content from S3
        response = s3.get_object(Bucket=output_bucket, Key=object_key)

        # Parse the JSON content
        json_content = response['Body'].read().decode('utf-8')
        parsed_json = json.loads(json_content)

        return parsed_json
    except botocore.exceptions.ClientError as e:
        # Handle errors, such as if the file doesn't exist
        logger.error(f"Error: {e}")
        return None


def get_page_data(job_id):
    # Create a Textract Client
    textract = boto3.client('textract')

    # Get Page Data
    response = textract.get_document_analysis(JobId=job_id)

    return response


def get_jobs_status(tracking_id, output_bucket):
    # Loop through each job associated with the tracking_id
    for job in get_jobs(tracking_id, output_bucket)['jobs']:
        # Check if the current job's status is not "SUCCEEDED"
        if get_page_data(job["JobId"])["JobStatus"] != "SUCCEEDED":
            # If any job is not complete, return "Not Complete" immediately
            return "Not Complete"

    # If all jobs have a "SUCCEEDED" status, return "Complete"
    return "Complete"


def get_query_results(job_id):
    # Get Page Data
    json_data = get_page_data(job_id)

    query_data = {"JobId": job_id, "queries": []}

    for block in json_data["Blocks"]:
        block_type = block["BlockType"]

        if block_type == "QUERY":
            alias = block['Query']["Alias"]
            query_text = block['Query']["Text"]
            query_id = block["Id"]
            answer_id = None
            if "Relationships" in block:

                for relationship in block["Relationships"]:
                    if relationship["Type"] == "ANSWER":
                        answer_id = relationship["Ids"][0]

            query_data["queries"].append(
                OrderedDict([
                    ("alias", alias),
                    ("query_id", query_id),
                    ("query_text", query_text),
                    ("answer_id", answer_id),
                    ("answer_text", None),
                    ("confidence", None)
                ]))

    for block in json_data["Blocks"]:
        block_type = block["BlockType"]

        if block_type == "QUERY_RESULT":
            for query in query_data["queries"]:
                if block["Id"] == query["answer_id"]:
                    query["answer_text"] = block["Text"]
                    query["confidence"] = round(block["Confidence"], 2)

    return query_data


def get_page_type(job_id):
    # Create a Textract Client
    textract = boto3.client('textract')

    # Get Job Data
    response = textract.get_document_analysis(JobId=job_id)
    json_data = json.loads(json.dumps(response))

    # Combine OCRed text into a single string
    text = ""
    for block in json_data["Blocks"]:
        block_type = block["BlockType"]

        if block_type == "LINE":
            text += block["Text"] + " "

    # Determine Page Type
    # Blank if the page content is less than the blank page threshold
    if len(text.split()) < BLANK_PAGE_THRESHOLD:
        page_type = "blank"
        logger.info(f"Page {job_id} is blank.")
    # RFS if the page contains the form number 10-10172
    elif text.find("10-10172") != -1:
        page_type = "RFS"
        logger.info(f"Page {job_id} is an RFS.")
    # Other if neither of the two previous conditions apply
    else:
        page_type = "other"
        logger.info(f"Page {job_id} is of type 'other'.")

    # text_data = {"JobId": job_id, "page_type": page_type, "text": text}

    return page_type


def get_signature_confidence(job_id):
    if get_page_type(job_id) == "RFS":
        page_data = get_page_data(job_id)

        for block in page_data["Blocks"]:
            block_type = block["BlockType"]

            if block_type == "SIGNATURE":
                signature_confidence = block["Confidence"]
                return round(signature_confidence, 2)
    else:
        return "Page is not an RFS"


# Function to write JSON data to S3
def write_json_to_s3(tracking_id, json_data, output_bucket):
    try:
        # Define the S3 key for the JSON file
        json_key = f"{tracking_id}/entities.json"

        # Upload the JSON data to the output S3 bucket
        s3.put_object(Bucket=output_bucket, Key=json_key, Body=json_data)
        logger.info(f"Uploaded entities JSON for tracking ID {tracking_id} to S3.")
    except botocore.exceptions.ClientError as e:
        logger.error(f"Error writing JSON to S3: {e}")


def get_file_entities(tracking_id, output_bucket):
    # Maximum number of retries

    max_retries = 60  # Retry for a total of 5 minutes (60 retries * 5 seconds)

    for attempt in range(max_retries):
        # Get the jobs data
        file_data = get_jobs(tracking_id, output_bucket)

        if file_data is None:
            logger.error(f'Jobs JSON file for {tracking_id} not found')
            return json.dumps({'ERROR': f'Jobs JSON file for {tracking_id} not found'}), 404
        elif get_jobs_status(tracking_id, output_bucket) == "Not Complete":
            # If the job is not complete, wait for 10 seconds before retrying
            logger.info(f'Jobs for {tracking_id} are still processing...')
            time.sleep(5)
        else:
            logger.info(f'Jobs for {tracking_id} are complete. Getting entities... ')
            # Match each job with their queries, page type, and, for RFSs, signature confidence
            for job in file_data['jobs']:
                # Get and store query results for each job
                job["queries"] = get_query_results(job["JobId"])["queries"]

                # Determine the page type for the job
                job["page_type"] = get_page_type(job["JobId"])

                # If the page type is "RFS," get and store the signature confidence
                if job["page_type"] == "RFS":
                    job["signature_confidence"] = get_signature_confidence(job["JobId"])

            # Rename "jobs" array to "pages" for clarity
            file_data["pages"] = file_data.pop("jobs")

            for page in file_data["pages"]:

                ordered_entities_page = []

                # Remove the "ResponseMetadata" object
                if "ResponseMetadata" in page:
                    del page["ResponseMetadata"]

                # Change "JobId" to "page_id"
                if "JobId" in page:
                    page["page_id"] = page.pop("JobId")

                # Change "PageNum" to "page_num"
                if "PageNum" in page:
                    page["page_num"] = page.pop("PageNum")

                # Rename "queries" to "entities"
                if "queries" in page:
                    page["entities"] = page.pop("queries")

                # Iterate through the entities and make changes
                for entity in page["entities"]:
                    # Remove query_id and answer_id
                    if "query_id" in entity:
                        del entity["query_id"]
                    if "answer_id" in entity:
                        del entity["answer_id"]

                    # Change "alias" to "entity"
                    if "alias" in entity:
                        entity["entity"] = entity.pop("alias")

                    # Change "answer_text" to "value"
                    if "answer_text" in entity:
                        entity["value"] = entity.pop("answer_text")

                    # Change "query_text" to "query"
                    if "query_text" in entity:
                        entity["query"] = entity.pop("query_text")

                    # Create an ordered dictionary for the entity
                    ordered_entities = OrderedDict([
                        ("entity", entity["entity"]),
                        ("value", entity["value"]),
                        ("query", entity["query"]),
                        ("confidence", entity["confidence"])
                    ])

                    # Append the ordered entity to the list
                    ordered_entities_page.append(ordered_entities)

                    # Sort the ordered entities by the value of entity["entity"]
                    ordered_entities_page = sorted(ordered_entities_page, key=lambda x: x["entity"])

                    # Update the entities for the page
                    page["entities"] = ordered_entities_page

                # Add the signature confidence as a new entity if available
                if "signature_confidence" in page:
                    signed = True if float(page["signature_confidence"]) >= SIGNATURE_THRESHOLD else False
                    signature_entity = {
                        "entity": "SIGNATURE",
                        "value": signed,
                        "query": "Is the RFS signed?",
                        "confidence": page["signature_confidence"]
                    }
                    ordered_entities_page.append(signature_entity)

            # Put keys in order for the final JSON output
            file_data = OrderedDict([
                ("tracking_id", file_data["tracking_id"]),
                ("filename", file_data["filename"]),
                ("pages", file_data["pages"]),
            ])

            # Write Entities JSON file to S3 Output Bucket
            try:
                write_json_to_s3(tracking_id, json.dumps(file_data, indent=4), output_bucket)
            except botocore.exceptions.ClientError as e:
                logger.error(f"Error writing JSON to S3: {e}")
            logger.info(f"Processed tracking ID {tracking_id} successfully.")

            return json.dumps(file_data, indent=4)

    # If all retries are exhausted and the job is still not complete, return an appropriate response
    logger.error(f"File processing not completed after retries for tracking ID {tracking_id}.")
    return json.dumps({'ERROR': 'File processing not completed after retries'}), 500


def lambda_handler(event, context):
    start_time = time.time()
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        # Check if the object in S3 ends with 'jobs.json' before processing
        if key.endswith("jobs.json"):
            try:
                logger.info(f"Processing S3 object: {bucket}/{key}")

                response = s3.get_object(Bucket=bucket, Key=key)
                json_content = response['Body'].read().decode('utf-8')
                parsed_json = json.loads(json_content)

                # Assuming your 'jobs.json' has a 'tracking_id' field
                tracking_id = parsed_json.get('tracking_id')

                if tracking_id:
                    # Call the get_file_entities function to process the data with the extracted tracking_id
                    logger.info(f"Calling get_file_entities for tracking ID: {tracking_id}")
                    result = get_file_entities(tracking_id, output_bucket)

                    # Send the response body to the EPSI Endpoint
                    try:
                        response = requests.post(epsi_endpoint, json=result)

                        if response.status_code == 200:
                            logger.info(f"Successfully sent entities for {tracking_id} to {epsi_endpoint}")
                        else:
                            logger.error(
                                f"Failed to send entities for {tracking_id} to {epsi_endpoint}. "
                                f"Status code: {response.status_code}")
                    except Exception as e:
                        logger.error(f"Error sending entities for {tracking_id} to {epsi_endpoint}: {e}")

                    return {'statusCode': 200, 'body': json.dumps({'INFO': 'Processed tracking ID'
                                                                           f' {tracking_id} successfully'})}
                else:
                    logger.error('Tracking ID not found in jobs.json')
                    return {'statusCode': 400, 'body': json.dumps({'ERROR': 'Tracking ID not found in jobs.json'})}
            except botocore.exceptions.ClientError as e:
                logger.error(f"Error: {e}")
                return {'statusCode': 500, 'body': json.dumps({'ERROR': f"Error: {e}"})}

    elapsed_time = time.time() - start_time
    logger.info(f"Lambda execution time: {elapsed_time} seconds")
