# set base image (host OS)
FROM python:3.8

# set the working directory in the container
WORKDIR /code

# copy the dependencies file to the working directory
COPY requirements.txt .

# install dependencies
RUN pip install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY paper_trade.py .

# Copy the Google Cloud credentials
COPY splendid-cirrus-302501-7e3faab608d2.json .

# command to run on container start
CMD [ "python", "./paper_trade.py" ]