from functools import wraps

from pinballmap.exceptions import (
    PinballMapAuthenticationFailure,
    TokenRequiredException,
)


def requires_authorization(f):
    @wraps(f)
    def wrapper(self, *args, **kwargs):
        if not self.authentication_token and self.user_email:
            if self.user_email and self.user_password:
                # we have credentials, why not try them?
                try:
                    self.auth_details(
                        self.user_email, self.user_password, update_self=True
                    )
                    return f(self, *args, **kwargs)
                except PinballMapAuthenticationFailure:
                    pass
            raise TokenRequiredException(
                "Pinball Map authentication_token and user_email required for this "
                "operation."
            )
        return f(self, *args, **kwargs)

    return wrapper
