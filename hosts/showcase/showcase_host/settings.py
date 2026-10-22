"""The showcase host's own settings: SHOWCASE_* variables, read from the same .env as
Lattice's LATTICE_* settings."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ShowcaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHOWCASE_", extra="ignore")

    sharepoint_site: str = Field("", description='A SharePoint site for the folder picker, e.g. '
                                 '"contoso.sharepoint.com:/sites/claims". Empty: no SharePoint.')
    sharepoint_library: str = Field("", description="The site's document library by name; empty: the default.")
    sharepoint_root: str = Field("", description="The folder inside the library the picker starts at and "
                                 "cannot go above; empty: the whole library.")
    m365_tenant_id: str = Field("", description="The SharePoint app registration's tenant (directory) id.")
    m365_client_id: str = Field("", description="Its application (client) id.")
    m365_client_secret: SecretStr = Field(SecretStr(""), description="Its client secret.")


settings = ShowcaseSettings()
