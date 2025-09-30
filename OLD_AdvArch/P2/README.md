# RESTful communication

## How to use

Simply run one instance of `server.py` using Flask, e.g. `flask -A server run --debug --with-threads`

Then, run enough instances of `client.py` to possibly reach consensus. For the default
pool size of 3, this means only 2 clients are needed to reach consensus.

The server is reusable, and prevents new clients from joining pools that have reached consensus.
However, pools never get cleaned up, which means the server eventually runs out of memory.

## Implementation features

- HTTP basic authentication (horribly insecure, it is only used to distinguish between clients)
- HTTP conditional requests with `If-Match` precondition to safely update the server's state
- Python Decorators to make the code less verbose <sup>\[citation needed\]</sup>
- Soft-lockstep mode so that clients do not end up spam posting votes and starving others

The core of this implementation revolves around keeping global state on the server and ensuring
that clients can read/write this state in a thread-safe manner. The only sane way to do this in
HTTP is ensuring that POST requests are conditional, so that the server only updates its values
if a precondition is true. In this case, the precondition simply requires the server's data not
to have been modified since the last time it was fetched, even though the POST request performs
a partial update. To compare versions, an Etag is used, which is the SHA512 sum of the data.

Each client does not directly "talk" with other clients, but instead decides what to do based
on the state it reads from the server. Even though each client independently checks consensus
state, all (alive) clients end up with the same result thanks to conditional requests: should
one client observe consensus in the server at any given time, then it is not possible for any
other client to overwrite this state, as they would have had to observe the same state before
being allowed to modify it.

## Thoughts regarding adequacy

Although this approach works, it is undesirable for a number of reasons. Most notably, this
approach has a single point of failure: the server. Because of this, it will not scale well
as the server will eventually saturate given a large enough number of clients.
