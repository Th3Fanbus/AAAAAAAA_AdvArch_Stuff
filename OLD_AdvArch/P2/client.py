from collections import Counter
from requests import Response
from wsgiref.handlers import format_date_time
import asyncio
import functools
import itertools
import random
import requests
import secrets
import sys
import time

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Host and port to try to connect to
HOST_PORT = "localhost:5000"

#############################
#  CONFIGURATION FUNCTIONS  #
#############################

# Vote generation function
def cf_get_vote_value():
    return random.randrange(20)

# Client delay function
def cf_client_wait():
    time.sleep(random.weibullvariate(0.5, 5.0)) # TODO: Make dynamic, backoff?

# Taken from Werkzeug code
def is_json(mt):
    return mt is not None and (
        mt == "application/json"
        or mt.startswith("application/")
        and mt.endswith("+json")
    )

def url_for(endpoint):
    return "http://" + HOST_PORT + endpoint

def use_endpoints(func):
    # Decorator for requests library functions with "endpoints" (c.f. `url_for()`)
    @functools.wraps(func)
    def wrapper(endpoint, **kwargs):
        return func(url_for(endpoint), **kwargs)
    # Return decorated function
    return wrapper

@use_endpoints
def do_get(url, **kwargs):
    return requests.get(url, **kwargs)

@use_endpoints
def do_post(url, **kwargs):
    return requests.post(url, **kwargs)

class Client:
    def __init__(self):
        self.username = secrets.token_hex(32)
        # TODO: Figure out if values are sane
        self.deferred_vote = None
        self.latest_etag = ""

    def __enter__(self):
        self._join_pool()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def _join_pool(self):
        r = do_post("/join_pool", auth = (self.username, ""), json = {})
        match r:
            case Response(status_code = 200 | 201, headers = headers):
                if is_json(headers["Content-Type"]):
                    data = r.json()
                    self.credentials = (self.username, data["password"])
                else:
                    raise NotImplementedError("Non-JSON response received")
            case Response(status_code = status_code, headers = headers):
                if is_json(headers["Content-Type"]):
                    raise RuntimeError("Unexpected HTTP %d: %s"%(status_code, r.json()["error"]))
                else:
                    raise RuntimeError("Unexpected HTTP %d"%status_code)
            case _:
                raise NotImplementedError("Unhandled response")

    def get_votes(self):
        condition = {"If-None-Match": self.latest_etag}
        r = do_get("/get_votes", auth = self.credentials, headers = condition)
        match r:
            case Response(status_code = 304):
                # If we get a Not Modified, we already know that consensus has
                # not been reached. We can only retry a vote we were unable to
                # post in a previous iteration due to e.g. failed precondition.
                #
                # TODO: When voting in lockstep, something needs to be done to
                # prevent deadlocks when consensus is not reached. Either have
                # the server increment a sequence number (which would make the
                # ETag change) or let clients vote whenever checking consensus.
                return None, False
            case Response(status_code = 200, headers = headers):
                if not is_json(headers["Content-Type"]):
                    raise NotImplementedError("Non-JSON response received")
                match r.json():
                    case {
                        "pool_size": pool_size,
                        "min_agree": min_agree,
                        "vote_data": vote_data
                    }:
                        self.latest_etag = headers["ETag"]
                        # Print info for debugging
                        print("pool size: %d"%pool_size)
                        print("min agree: %d"%min_agree)
                        print("vote data: %s\tVote\tSeq"%(" " * 56))
                        for k, (v, s) in vote_data.items():
                            print("    %s:\t%s\t%s"%(k, v, s))
                        print()

                        # Collect votes
                        votes = [v for v, _ in vote_data.values() if v is not None]
                        vlen = len(votes)
                        c = Counter(votes)
                        print(c)

                        # Decide what to do
                        if vlen == 0:
                            # Pool has no votes, should never happen
                            return None, True

                        number, count = c.most_common(1)[0]
                        if count >= min_agree:
                            # Reached consensus
                            return number, False

                        (myvote, myseq) = vote_data[self.username];
                        if myvote is None:
                            # We did not vote yet
                            return None, True

                        if self.deferred_vote is not None:
                            # Could not post last time, we can vote
                            return None, True

                        seqs = [s for _, s in vote_data.values() if s is not None]
                        if myseq < max(seqs):
                            # Our sequence number is trailing behind, we can vote
                            return None, True
                        else:
                            # We should only vote again if others have also voted
                            # Intended to enforce some sort of soft-lockstep mode
                            # where clients wait for each other's votes but still
                            # continue voting as long as there are enough of them
                            # to eventually reach consensus.
                            return None, sum(s == myseq for s in seqs) >= min_agree
                    case _:
                        raise RuntimeError("Cannot parse server response")
            case Response(status_code = status_code, headers = headers):
                if is_json(headers["Content-Type"]):
                    raise RuntimeError("Unexpected HTTP %d: %s"%(status_code, r.json()["error"]))
                else:
                    raise RuntimeError("Unexpected HTTP %d"%status_code)
            case _:
                raise NotImplementedError("Got a non-Response")

    def choose_vote(self):
        return cf_get_vote_value()

    def post_vote(self):
        proposed_vote = self.choose_vote() if self.deferred_vote is None else self.deferred_vote
        req = {
            self.username: proposed_vote
        }
        condition = {"If-Match": self.latest_etag}
        r = do_post("/post_vote", auth = self.credentials, headers = condition, json = req)
        match r:
            case Response(status_code = 412):
                print("Vote rejected as information has changed in the meantime")
                self.deferred_vote = proposed_vote
            case Response(status_code = 200, headers = headers):
                print("Vote posted successfully")
                self.deferred_vote = None
                if is_json(headers["Content-Type"]):
                    data = r.json()
                else:
                    raise NotImplementedError("Non-JSON response received")
            case Response(status_code = status_code, headers = headers):
                if is_json(headers["Content-Type"]):
                    raise RuntimeError("Unexpected HTTP %d: %s"%(status_code, r.json()["error"]))
                else:
                    raise RuntimeError("Unexpected HTTP %d"%status_code)
            case _:
                raise NotImplementedError("Got a non-Response")

    def loop(self):
        while True:
            decision_outcome, can_vote = self.get_votes()
            if decision_outcome is not None:
                return decision_outcome

            if can_vote or self.deferred_vote is not None:
                self.post_vote()

            if not can_vote or self.deferred_vote is not None:
                cf_client_wait()

def main():
    with Client() as client:
        return client.loop()

if __name__ == "__main__":
    retval = main()
    print()
    print(f"---> CONSENSUS REACHED ON {retval}")
    print()
    print("Byeeeee!")
