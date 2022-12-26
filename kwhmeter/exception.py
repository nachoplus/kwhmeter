class contadorException(Exception):
    pass


class ResponseException(contadorException):
    def __init__(self, status_code):
        super().__init__("Response error, code: {}".format(status_code))


class LoginException(contadorException):
    def __init__(self, username):
        super().__init__(f'Unable to log in with user {username}')


class SessionException(contadorException):
    def __init__(self):
        super().__init__('Session required, use login() method to obtain a session')


class NoResponseException(contadorException):
    pass
