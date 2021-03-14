# set base image (host OS)
FROM python:3.8

# set the working directory in the container
WORKDIR /code

# copy the dependencies file to the working directory
COPY bot-requirements.txt requirements.txt

# install dependencies
RUN pip install -r requirements.txt

# copy the content of the local src directory to the working directory
COPY trade_momentum_stocks.py .
COPY discord_webhook.py .

# command to run on container start
CMD [ "python", "./trade_momentum_stocks.py" ]