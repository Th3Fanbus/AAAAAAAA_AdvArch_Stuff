import functools
import json
import secrets
import threading

from collections import Counter
from flask import Flask, Response, Request, jsonify, make_response
from flask import request as g_request
from hashlib import sha512
from http import HTTPStatus
from werkzeug.datastructures.auth import Authorization

################################
#       CONFIG CONSTANTS       #
################################

# Number of clients voting in the same consensus pool
CONSENSUS_POOL_SIZE = 3

################################
#       CONFIG FUNCTIONS       #
################################

# Given a pool size, return the minimum number of
# matching votes to reach consensus. This must be
# lower than the consensus pool size set above!
def cf_get_min_agree():
    return CONSENSUS_POOL_SIZE // 2 + 1

# Trust no one
assert cf_get_min_agree() <= CONSENSUS_POOL_SIZE

################################
#       HELPER FUNCTIONS       #
################################

def response_from_code(status_code, error_details = None):
    error_msg = ": ".join(filter(None, (status_code.phrase, error_details)))
    return make_response({"error": error_msg}, status_code)

################################
#        CONSENSUS POOL        #
################################

class ConsensusPool:
    # TODO: Unsure if thread safety is achieved
    pool_list = []
    pool_list_lock = threading.Lock()

    @classmethod
    def _find_first(cls, predicate):
        for p in cls.pool_list:
            if predicate(p):
                return p
        return None

    @classmethod
    def pool_for_username(cls, username):
        with cls.pool_list_lock:
            return cls._find_first(lambda p : username in p.login_cookies.keys())

    @classmethod
    def route_incoming_voter(cls, username, password):
        # Route clients with a known username back to their pool
        # Note that the client implementation does not reconnect
        pool = cls.pool_for_username(username)
        if pool is None:
            # We do not know this username, treat it as new client
            with cls.pool_list_lock:
                # Find an existing pool that can be joined
                pool = cls._find_first(lambda p : p.is_joinable())
                if pool is None:
                    # Or create a new pool if none could be found
                    pool = ConsensusPool()
                    cls.pool_list.append(pool)
            # Populate the pool with the client information
            pool.login_cookies[username] = secrets.token_hex(256)
            pool.vote_sequence[username] = (None, 0) # voted number, sequence number
            return make_response(({"password": pool.login_cookies[username]}, HTTPStatus.CREATED))
        else:
            # Known username that requested to rejoin, try to authenticate
            # TODO: If this fails, retry with other pools?
            def do_check_creds():
                return make_response(({}, HTTPStatus.OK))
            return pool.validate_creds_and_run(username, password, do_check_creds)

    def __init__(self):
        # TODO: There can be threading issues in this class
        #       specifically regarding the Etag calculation
        self.login_cookies = {}
        self.vote_sequence = {}

    def is_joinable(self):
        if len(self.login_cookies) < CONSENSUS_POOL_SIZE:
            # The pool itself has room, check if consensus has been reached
            votes = [v for v, _ in self.vote_sequence.values() if v is not None]
            if len(votes) == 0:
                # Empty pool? Should never happen
                return True
            # Do not allow joining a pool where consensus has already been reached
            _, count = Counter(votes).most_common(1)[0]
            return count < cf_get_min_agree()
        else:
            return False

    def validate_creds_and_run(self, username, password, func):
        if self.login_cookies[username] == password:
            return func() # N.B. this is meant to be a nested function
        else:
            return response_from_code(HTTPStatus.FORBIDDEN, "Incorrect password")

    def calculate_etag(self):
        return sha512(json.dumps(self.vote_sequence).encode("utf-8")).hexdigest()

    def get_votes(self, username, password, request):
        def do_get_votes():
            data = jsonify({
                "pool_size": CONSENSUS_POOL_SIZE,
                "min_agree": cf_get_min_agree(),
                "vote_data": self.vote_sequence,
            })
            resp = make_response((data, HTTPStatus.OK))
            resp.set_etag(self.calculate_etag())
            return resp
        return self.validate_creds_and_run(username, password, do_get_votes)

    def post_vote(self, username, password, request):
        def do_post_vote():
            print(request.if_match)
            if self.calculate_etag() in request.if_match:
                number = request.get_json()[username]
                (_, seq_number) = self.vote_sequence[username]
                self.vote_sequence[username] = (number, seq_number + 1)
                return make_response(({}, HTTPStatus.OK))
            else:
                return response_from_code(HTTPStatus.PRECONDITION_FAILED)
        return self.validate_creds_and_run(username, password, do_post_vote)

################################
#    CURSED DECORATOR STUFF    #
################################

# There was absolutely no need to overcomplicate
# ourselves making these decorators, but the fun
# of learning how to do it was worth the pain

def require_auth(func):
    # Decorator to verify request authorization, verification is done by the caller
    @functools.wraps(func)
    def wrapper(request):
        match request.authorization:
            case None:
                return response_from_code(HTTPStatus.UNAUTHORIZED)
            case Authorization(parameters = {"username": username, "password": password}):
                return func(username, password, request)
            case _:
                return response_from_code(HTTPStatus.BAD_REQUEST, "Unhandled authorization format")
    # Return decorated function
    return wrapper

def require_json(func):
    # Decorator to ensure request is JSON
    @functools.wraps(func)
    def wrapper(username, password, request):
        print(request.headers["Content-Type"])
        if request.is_json:
            return func(username, password, request)
        else:
            return response_from_code(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Request must be JSON")
    # Return decorated function
    return wrapper

def require_precondition(precondition):
    # Decorators with arguments are defined as a decorator factory
    def decorator(func):
        # Decorator to ensure request is conditional, e.g. If-(None-)Match <etag-list>
        @functools.wraps(func)
        def wrapper(username, password, request):
            if request.headers.get(precondition) is not None:
                return func(username, password, request)
            else:
                return response_from_code(HTTPStatus.PRECONDITION_REQUIRED, "Request must use " + precondition)
        # Return decorated function
        return wrapper
    # From the factory function, return the curried decorator function
    return decorator

def require_pool(func):
    # Decorator to retrieve a pool by username
    @functools.wraps(func)
    def wrapper(username, password, request):
        pool = ConsensusPool.pool_for_username(username)
        if pool is None:
            return response_from_code(HTTPStatus.UNAUTHORIZED)
        else:
            return func(pool, username, password, request)
    # Return decorated function
    return wrapper

################################
#       MAIN FLASK STUFF       #
################################

app = Flask(__name__)

@app.post("/join_pool")
def do_join_pool():
    @require_auth
    def join_pool(username, password, request):
        return ConsensusPool.route_incoming_voter(username, password)
    return join_pool(g_request._get_current_object())

@app.get("/get_votes")
def do_get_votes():
    @require_auth
    @require_pool
    def get_votes(pool, username, password, request):
        return pool.get_votes(username, password, request)
    return get_votes(g_request._get_current_object())

@app.post("/post_vote")
def do_post_vote():
    @require_auth
    @require_json
    @require_precondition("If-Match")
    @require_pool
    def post_vote(pool, username, password, request):
        return pool.post_vote(username, password, request)
    return post_vote(g_request._get_current_object())

@app.get("/get_pool_size")
def do_get_pool_size():
    return make_response(({"pool_size": CONSENSUS_POOL_SIZE}, HTTPStatus.OK))

@app.get("/brew_coffee")
def do_brew_coffee():
    return response_from_code(HTTPStatus.IM_A_TEAPOT)

if __name__ == "__main__":
    app.debug = True
    app.run(threaded = True, use_debugger = True, use_evalex = False, use_reloader = True)
