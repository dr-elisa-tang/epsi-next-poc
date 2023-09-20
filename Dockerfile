# Use a base image with Python and AWS CLI preinstalled
FROM python:3.8

# Set environment variables for AWS credentials
ENV AWS_ACCESS_KEY_ID=<YourAccessKeyID>
ENV AWS_SECRET_ACCESS_KEY=<YourSecretAccessKey>
ENV AWS_DEFAULT_REGION=<YourRegion>

# Install required Python packages
RUN pip install boto3

# Create a directory for your application
WORKDIR /app

# Copy your Python script to the container
COPY pdf_to_textract.py /app/

# Make your Python script executable
RUN chmod +x /app/pdf_to_textract.py

# Run the Python script when the container starts
CMD ["/app/pdf_to_textract.py"]