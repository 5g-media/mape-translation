import base64


def basic_token(username, password):
    """Generate the Authorization token for Resource Orchestrator (SO-ub container).

    Args:
        username (str): the SO-ub username
        password (str): the SO-ub password

    Returns:
        str: the Basic token
    """
    if not isinstance(username, str):
        raise TypeError("The given type of username is `{}`. Expected str.".format(type(username)))
    if not isinstance(password, str):
        raise TypeError("The given type of password is `{}`. Expected str.".format(type(password)))
    credentials = str.encode(username + ":" + password)
    return bytes.decode(base64.b64encode(credentials))
