import uuid
from typing import Any, Dict, Optional, Union, List, Tuple
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .result import Result


class NamHTTPClient:
    def __init__(self, base_url: str, retries: int = 3, backoff_factor: float = 0.3,
                 status_forcelist: Optional[List[int]] = None):
        self.base_url = base_url
        self.session = self._create_session(retries, backoff_factor, status_forcelist or [429, 500, 502, 503, 504])

    def _create_session(self, retries: int, backoff_factor: float, status_forcelist: List[int]) -> requests.Session:
        retry_strategy = Retry(total=retries, read=retries, connect=retries,
                               backoff_factor=backoff_factor, status_forcelist=status_forcelist)
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def __enter__(self) -> 'NamHTTPClient':
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def send_request(self, endpoint: str, http_method: str = "GET", **kwargs) -> Result:
        url = urljoin(self.base_url, endpoint)
        try:
            response = self.session.request(http_method, url, **kwargs)
            response.raise_for_status()
            return Result(True, response.json())
        except requests.exceptions.HTTPError as e:
            return Result(False, error=f"HTTP error: {e.response.status_code} {e.response.reason}")
        except requests.exceptions.RequestException as e:
            return Result(False, error=f"Request exception: {str(e)}")

    def send_json_rpc_request(self, rpc_method: str, params: Optional[dict] = None, **kwargs) -> Result:
        json_id = str(uuid.uuid4())
        data = {"jsonrpc": "2.0", "id": json_id, "method": rpc_method, "params": params or []}
        return self.send_request("", http_method="POST", json=data, headers={"Content-Type": "application/json"},
                                 **kwargs)

    def close(self) -> None:
        self.session.close()


def find_key(data: Union[Dict, List], target_key: str) -> Tuple[bool, Any]:
    """
    Recursively search for a target key in a nested dictionary or list and return a tuple
    indicating whether the key was found and its value.

    :param data: Dictionary or list to search in.
    :param target_key: The key to search for.
    :return: A tuple (found: bool, value: Any). If the key is found, found is True and value is the key's value.
             If the key is not found, found is False and value is None.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key:
                return True, value
            elif isinstance(value, (dict, list)):
                found, result = find_key(value, target_key)
                if found:
                    return True, result
    elif isinstance(data, list):
        for item in data:
            found, result = find_key(item, target_key)
            if found:
                return True, result
    return False, None
