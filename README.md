# quic-v-stream

Server-Client service to stream video with [QUIC](https://www.chromium.org/quic)

## How to run

### Install Dependencies with pipenv
```sh
pipenv install
```

### Start pipenv shell
```sh
pipenv shell
```

### Run server
```sh
python -m src.server -c <certificate> -k <private_key> --host <ip_addr> --port <port no.>
```

### Run client
```sh
python -m src.client --host <ip_addr> --port <port_no> --request <file>
```