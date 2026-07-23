FROM ubuntu:24.04 AS build
RUN apt-get update && apt-get install -y g++ make cmake && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY . .
RUN g++ -std=c++17 -O2 -pthread src/main.cpp -o kv_node

FROM ubuntu:24.04
COPY --from=build /src/kv_node /usr/local/bin/kv_node
EXPOSE 7070
ENTRYPOINT ["kv_node"]
