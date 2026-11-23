"""API client for Energy Hub Poland."""

import asyncio
import logging
import ssl
from datetime import date
from typing import Any

import aiohttp
import async_timeout

from .const import API_URL, PSE_API_URL

_LOGGER = logging.getLogger(__package__)

# Intermediate CA certificate for PGE DataHub (datahub.gkpge.pl).
# As of 2026-11-12, the server serves CN=gkpge.pl without the intermediate
# "Certum DV TLS G2 R39 CA" certificate, breaking validation in Python/aiohttp.
# AIA URL: http://certumdvtlsg2r39ca.repository.certum.pl/certumdvtlsg2r39ca.cer
# SHA-256: 83:C0:A5:A7:68:44:C8:40:DF:AF:82:0F:FD:02:AD:F6:57:3A:26:82:3E:F6:AF:75:8A:33:84:A0:AC:04:40:83
# Valid until: 2039-06-05
_CERTUM_DV_TLS_G2_R39_CA = """-----BEGIN CERTIFICATE-----
MIIGnTCCBIWgAwIBAgIRAKgt2eXcr98TIF5wBD5rlagwDQYJKoZIhvcNAQENBQAwejELMAkGA1UE
BhMCUEwxITAfBgNVBAoTGEFzc2VjbyBEYXRhIFN5c3RlbXMgUy5BLjEnMCUGA1UECxMeQ2VydHVt
IENlcnRpZmljYXRpb24gQXV0aG9yaXR5MR8wHQYDVQQDExZDZXJ0dW0gVHJ1c3RlZCBSb290IENB
MB4XDTI0MDYxODA3NDEyMloXDTM5MDYwNTA3NDEyMlowUjELMAkGA1UEBhMCUEwxITAfBgNVBAoM
GEFzc2VjbyBEYXRhIFN5c3RlbXMgUy5BLjEgMB4GA1UEAwwXQ2VydHVtIERWIFRMUyBHMiBSMzkg
Q0EwggIiMA0GCSqGSIb3DQEBAQUAA4ICDwAwggIKAoICAQCo52NXEXWoO2w6zQeBtNerd5ahhe8R
gM8XVpwGEFoovjHc4K+Cp3auUWVlt7/ARthJoxOttF+jaSrlSve9mWnmTJOo1QLuoOTWuZ9XUkMj
DG1ztTbFsgRqQyOtZsDqniHD79wqD49DQW4geVslp9/LiTQKUpPawtAwpBeoaRXL8RJ8xjNA+2bE
r6vesz2MEvvhpWBSWNAIR5O5YbiLztQ9KdOuBYS0CW59ptuCjg3AuLcp8aOjk9z/kJc8xKkO48hL
Tp+HpdHkuI+iFWZn0aCLlM/ngpdoBw+NGs6TMC8B6BcK7y/zl8FsNC4gE86Kfd8J9zWhCA7umHnB
XCSYCKRxH5o7DtoGiWXvcRKYpGtWt9czdUa1edSk5mTrwZGEXLAkX1ECiAq4GS5vEGjrEQ1ux8ma
g2LDh7ZnXdcyzkKZKGsx7uExe3Nx5gWWZMXFrZ5v+uxynKogHUY2vdIMB3dn9qRYwpzvn3msfBbk
RTAcS9eis1AY0Xxqlt3aXkVyqfKhdJxOPpzATM+Ve4jZSd1nLzEj+kFuHnv2jyOY3Vb35n3EmW8y
AwG1OWX/QnemMA5s2fZ+ZydHOTG4DkwXnaTrR/vUhM+FNywNUlvzYjcM6zt3Ysf9M1hK5PjUEKzs
Pf5BrIp0fs1zhlVC+cgBN2+JPtYwxP1nNpxwBgtIPoTk6wIDAQABo4IBRDCCAUAwcQYIKwYBBQUH
AQEEZTBjMDcGCCsGAQUFBzAChitodHRwOi8vc3ViY2EucmVwb3NpdG9yeS5jZXJ0dW0ucGwvY3Ry
Y2EuY2VyMCgGCCsGAQUFBzABhhxodHRwOi8vc3ViY2Eub2NzcC1jZXJ0dW0uY29tMB8GA1UdIwQY
MBaAFIz7HHW8AtOfTi5I2flgVKrEs0/6MBIGA1UdEwEB/wQIMAYBAf8CAQAwNQYDVR0fBC4wLDAq
oCigJoYkaHR0cDovL3N1YmNhLmNybC5jZXJ0dW0ucGwvY3RyY2EuY3JsMB0GA1UdJQQWMBQGCCsG
AQUFBwMCBggrBgEFBQcDATAOBgNVHQ8BAf8EBAMCAQYwEQYDVR0gBAowCDAGBgRVHSAAMB0GA1Ud
DgQWBBQzqHe3AThvXx8kJKIebBTjbiID3zANBgkqhkiG9w0BAQ0FAAOCAgEACDQ1ggBelZZ/NYs1
nFKWHnDrA8Y4pv0lvxLzSAC4ejGavMXqPTXHA+DEh9kHNd8tVlo24+6YN96Gspb1kMXRuuql23/6
R6Fpqg49dkQ1/DobsWvAHoYeZvsaAgaKRD3bvsAcB0JBhyBVT/88S9guDnS5YKMldiLMkVW1Nosk
d4dHEJ2mkJcVzJIJ0Y4johA1lC1JnZMjkB8ZTNIblkgJK6PqlhYkeMOkx+XbmUuUgh29T0sPne7/
V6PHnbEJIxUs40+iLCF0HrdqZypjvWQqpSmHRHI3UWVERDeERca0uJ3I+a5ER9vUL9u5ilGG4afy
x7QwzitBG+1rU3nRsHyZg6osILL/MWc0AbWJMyKzQ9Guj+uwq47h6BC9BsWF34pJeDC8EuN3HNxP
lSWSII9lOmwtipvq0EL1iocJhXdlsG+jIUVs/Sl/Um9JiZV+h/MoytnrPrWMIj+0zz6BdaPP2sT6
wcLzpnwYcE9FWSbQrzNpL283EOUkObjc8AIxICzPHGusF0IqsO+sj9XzvLThTjKfFlzx4NR8gbK7
m8sXq6cgP4UAtyvDswebFIRQiuhjqOT9G7+56+4zC0RaEZx/LwoFE+ObVXxX674szQvIc+7WPCoo
VsUbwZIikzJqZb4gJQ1OQx23CgyyYlsPHIDN8FpPkganuCwy++7umTkM7+Q=
-----END CERTIFICATE-----"""

_DATAHUB_SSL_CONTEXT: ssl.SSLContext | None = None


def _build_datahub_ssl_context() -> ssl.SSLContext:
    """Build SSL context that includes Certum intermediate CA."""
    global _DATAHUB_SSL_CONTEXT
    if _DATAHUB_SSL_CONTEXT is None:
        try:
            import certifi

            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ctx = ssl.create_default_context()
        ctx.load_verify_locations(cadata=_CERTUM_DV_TLS_G2_R39_CA)
        _DATAHUB_SSL_CONTEXT = ctx
    return _DATAHUB_SSL_CONTEXT


class PSEApiClient:
    """API client from PSE."""

    def __init__(self, session: Any) -> None:
        """Initialize the API client."""
        self._session = session
        self._headers = {
            "Accept": "application/json",
            "User-Agent": "HomeAssistant-EnergyHub-Client",
        }
        self._last_response_schema: str | None = None

    async def _async_get_data(  # type: ignore[return]  # mypy baseline, see #46
        self, endpoint: str, select_fields: str, for_date: date
    ) -> list[dict[str, Any]] | None:
        """Fetch generic data from PSE API with retry logic."""
        date_str = for_date.strftime("%Y-%m-%d")
        url = f"{PSE_API_URL}/{endpoint}"
        params = {
            "$select": select_fields,
            "$filter": f"business_date ge '{date_str}'",
            "$first": 250,
        }

        for attempt in range(3):  # Retry up to 3 times
            try:
                async with async_timeout.timeout(15):
                    response = await self._session.get(
                        url, params=params, headers=self._headers
                    )
                    response.raise_for_status()
                    data = await response.json()
                    result = data.get("value", [])

                    if result:
                        current_schema = self._get_schema(result[0])
                        if self._last_response_schema != current_schema:
                            _LOGGER.info(
                                "API schema changed for %s: %s",
                                endpoint,
                                current_schema,
                            )
                            self._last_response_schema = current_schema

                    return result
            except Exception as e:
                if attempt < 2:  # Don't log on last attempt
                    _LOGGER.warning(
                        "Attempt %d failed for %s on %s: %s. Retrying...",
                        attempt + 1,
                        endpoint,
                        date_str,
                        e,
                    )
                    await asyncio.sleep(1)  # Wait 1 second before retry
                else:
                    _LOGGER.error(
                        "Error fetching %s from PSE for %s after 3 attempts: %s",
                        endpoint,
                        date_str,
                        e,
                    )
                    return None

    def _get_schema(self, record: dict[str, Any]) -> str:
        """Get a string representation of the record schema."""
        return ",".join(sorted(record.keys()))

    async def get_rce_prices(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch RCE prices."""
        return await self._async_get_data(
            "rce-pln", "business_date,dtime,rce_pln", for_date
        )

    async def get_rce_forecast(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch RCE price forecast."""
        return await self._async_get_data(
            "price-fcst", "business_date,dtime,cen_fcst,imb_energy", for_date
        )

    async def get_peak_hours(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch peak hours."""
        return await self._async_get_data(
            "pdgsz", "business_date,dtime,usage_fcst,is_active", for_date
        )

    async def get_load_data(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch KSE load data."""
        return await self._async_get_data(
            "kse-load", "business_date,dtime,load_actual,load_fcst", for_date
        )

    async def get_generation_plans(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch PV and Wind generation plans."""
        return await self._async_get_data(
            "pdgobpkd", "business_date,dtime,gen_wi,gen_fv,kse_pow_dem", for_date
        )


class EnergyHubApiClient:
    """API client for fetching energy prices from PSE/TGE (via PGE DataHub)."""

    def __init__(
        self, session: Any, ssl_context: ssl.SSLContext | None = None
    ) -> None:
        """Initialize the API client with an aiohttp session."""
        self._session = session
        self._ssl_context = ssl_context

    async def _async_get_ssl_context(self) -> ssl.SSLContext:
        """Get or lazily create the SSL context."""
        if self._ssl_context is None:
            loop = asyncio.get_running_loop()
            self._ssl_context = await loop.run_in_executor(
                None, _build_datahub_ssl_context
            )
        return self._ssl_context

    async def async_get_prices(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch prices for the requested trading date, or None if unavailable."""
        date_str = for_date.strftime("%Y-%m-%d")
        url = (
            f"{API_URL}?source=TGE&contract=Fix_2"
            f"&date_from={date_str} 00:00:00"
            f"&date_to={date_str} 23:59:59&limit=100"
        )

        ssl_context = await self._async_get_ssl_context()

        try:
            async with async_timeout.timeout(20):
                response = await self._session.get(
                    url,
                    headers={"User-Agent": "HomeAssistant/EnergyHubPoland"},
                    ssl=ssl_context,
                )
                response.raise_for_status()
                payload = await response.json()
                if isinstance(payload, list) and payload:
                    return payload
                if isinstance(payload, dict):
                    data = payload.get("data") or payload.get("value")
                    if isinstance(data, list) and data:
                        return data
        except TimeoutError:
            _LOGGER.warning(
                "Timeout connecting to PGE DataHub API (%s) for date %s",
                API_URL,
                date_str,
            )
        except (ssl.SSLError, aiohttp.ClientSSLError) as e:
            _LOGGER.warning(
                "SSL/TLS certificate verification error for PGE DataHub API (%s) on %s: %s",
                API_URL,
                date_str,
                e,
            )
        except aiohttp.ClientResponseError as e:
            _LOGGER.warning(
                "HTTP error %s communicating with PGE DataHub API for date %s: %s",
                e.status,
                date_str,
                e.message,
            )
        except aiohttp.ClientError as e:
            _LOGGER.warning(
                "Network connection error to PGE DataHub API for date %s: %s",
                date_str,
                e,
            )
        except Exception as e:
            _LOGGER.warning("Error communicating with API for date %s: %s", date_str, e)

        _LOGGER.debug("No price data available for %s", date_str)
        return None
