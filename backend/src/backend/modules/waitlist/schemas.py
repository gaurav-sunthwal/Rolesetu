from pydantic import BaseModel, EmailStr


class WaitlistJoin(BaseModel):
    email: EmailStr


class WaitlistJoined(BaseModel):
    """The same answer whether or not the address was already on the list, so
    the endpoint cannot be used to find out who has signed up.
    """

    joined: bool = True
