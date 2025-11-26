FROM ollama/ollama

# Start the server, pull the model, and then stop the server
# This bakes the model into the image so you don't have to pull it every time
RUN /bin/bash -c "ollama serve & pid=\$! && sleep 5 && ollama pull llama3.2:latest && kill \$pid"
