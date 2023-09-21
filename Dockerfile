# Use a base image with Python and AWS CLI preinstalled
FROM python:3.8

# Set environment variables for AWS credentials and region
ENV AWS_ACCESS_KEY_ID=$AWSAccessKeyID
ENV AWS_SECRET_ACCESS_KEY=$AWSSecretAccessKey
ENV AWS_DEFAULT_REGION=$AWSRegion

# Install required Python packages
RUN pip install boto3

# Create a directory for your application
WORKDIR /app

# Copy your Python script with the new name to the container
COPY upload_pdf.py /app/
COPY fetch_json.py /app/
COPY text-extraction.py /app/

# Make your Python script executable
RUN chmod +x /app/upload_pdf.py
RUN chmod +x /app/fetch_json.py
RUN chmod +x /app/text-extraction.py

# Create a directory to store input files within the Docker image
RUN mkdir /input

# Set the working directory to /app
WORKDIR /app

# Run the Python script
CMD ["/app/epsi-text-extraction.py"]