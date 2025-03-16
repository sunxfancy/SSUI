from pydantic import BaseModel, Field

class FreeUConfig(BaseModel):
    """
    Configuration for the FreeU hyperparameters.
    - https://huggingface.co/docs/diffusers/main/en/using-diffusers/freeu
    - https://github.com/ChenyangSi/FreeU
    """

    s1: float = Field(ge=-1, le=3)
    s2: float = Field(ge=-1, le=3)
    b1: float = Field(ge=-1, le=3)
    b2: float = Field(ge=-1, le=3)
