from collections import Counter
from flask import Flask, Response, Request, jsonify, make_response
from flask import request as g_request
from hashlib import sha512
from werkzeug.datastructures.auth import Authorization
import functools
import json
import secrets
import threading

#############################
#  CONFIGURATION CONSTANTS  #
#############################

# Number of clients voting in the same consensus pool
CONSENSUS_POOL_SIZE = 3

#############################
#  CONFIGURATION FUNCTIONS  #
#############################

# Given a pool size, return the minimum number of
# matching votes to reach consensus. This must be
# lower than the consensus pool size set above!
def cf_get_min_agree():
    return CONSENSUS_POOL_SIZE // 2 + 1

# Trust no one
assert cf_get_min_agree() <= CONSENSUS_POOL_SIZE

STATUS_CODE_STRINGS = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "", # TODO: Figure out where this one went
    405: "Method Not Allowed",
    412: "Precondition Failed",
    415: "Unsupported Media Type",
    418: "I'm a teapot",
    428: "Precondition required"
}

def response_from_code(status_code, error_details = None):
    error_msg = ": ".join(filter(None, (STATUS_CODE_STRINGS.get(status_code), error_details)))
    return make_response({"error": error_msg}, status_code)

class ConsensusPool:
    # Unsure if thread safety is achieved
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
            pool.vote_sequence[username] = (None, 0)
            return make_response(({"password": pool.login_cookies[username]}, 201))
        else:
            # Known username, try to authenticate
            if pool.validate_creds(username, password):
                return make_response(({}, 200))
            else:
                # TODO: Retry with other pools?
                return response_from_code(403, "Incorrect password")

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
            _, count = Counter(votes).most_common(1)[0]
            return count < cf_get_min_agree()
        else:
            return False

    def validate_creds(self, username, password):
        return self.login_cookies[username] == password;

    def calculate_etag(self):
        return sha512(json.dumps(self.vote_sequence).encode("utf-8")).hexdigest()

    def get_votes(self, username, password, request):
        if self.validate_creds(username, password):
            data = jsonify({
                "pool_size": CONSENSUS_POOL_SIZE,
                "min_agree": cf_get_min_agree(),
                "vote_data": self.vote_sequence
            })
            resp = make_response((data, 200))
            resp.set_etag(self.calculate_etag())
            return resp
        else:
            return response_from_code(403, "Incorrect password")

    def post_vote(self, username, password, request):
        if self.validate_creds(username, password):
            print(request.if_match)
            if self.calculate_etag() in request.if_match:
                number = request.get_json()[username]
                (_, seq_number) = self.vote_sequence[username]
                self.vote_sequence[username] = (number, seq_number + 1)
                return make_response(({}, 200))
            else:
                return response_from_code(412)
        else:
            return response_from_code(403, "Incorrect password")

############################
#  CURSED DECORATOR STUFF  #
############################

# There was absolutely no need to overcomplicate
# ourselves making these decorators, but the fun
# of learning how to do it was worth the pain

def require_auth(func):
    # Decorator to verify request authorization, verification is done by the caller
    @functools.wraps(func)
    def wrapper(request):
        match request.authorization:
            case None:
                return response_from_code(401)
            case Authorization(parameters = {"username": username, "password": password}):
                return func(username, password, request)
            case _:
                return response_from_code(400, "Unhandled authorization format")
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
            return response_from_code(415, "Request must be JSON")
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
                return response_from_code(428, "Request must use " + precondition)
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
            return response_from_code(401)
        else:
            return func(pool, username, password, request)
    # Return decorated function
    return wrapper

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
    return make_response(({"pool_size": CONSENSUS_POOL_SIZE}, 200))

@app.get("/brew_coffee")
def do_brew_coffee():
    return response_from_code(418)

if __name__ == "__main__":
    app.debug = True
    app.run(threaded = True, use_debugger = True, use_evalex = False, use_reloader = True)
