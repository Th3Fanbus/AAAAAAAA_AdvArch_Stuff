# Networking activity

## How to use

Simply run one instance of `ds_server_wroom.py`, then run enough instances of `ds_client_wroom.py` to satisfy the room capacity (default 3).

Clients can disconnect before the waiting room is full, and this is handled appropriately. The server is reusable, but it likely does not delete unused rooms.
