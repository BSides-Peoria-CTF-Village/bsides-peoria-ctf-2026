docker build -t boarding .
docker run --rm -it --privileged -p 5000:5000 boarding