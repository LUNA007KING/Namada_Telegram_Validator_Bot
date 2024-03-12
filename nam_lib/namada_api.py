import base64

from config.settings import NAMADA_RPC_URL
from nam_lib.result import Result
from nam_lib.client import NamHTTPClient, find_key
from structs.basic import *
from structs.bech32m import bech32m_encode
from structs.commission_rate import extract_commission_values


class NamadaAPI:
    def __init__(self, rpc_url: str = NAMADA_RPC_URL):
        self.rpc_url = rpc_url

    def get_latest_height(self):
        """Fetches the current blockchain height."""
        with NamHTTPClient(base_url=self.rpc_url) as client:
            result = client.send_request('status')
            if result.success:
                resp = result.data
                if 'result' in resp:
                    found, height = find_key(resp, 'latest_block_height')
                    found, catching_up = find_key(resp, 'catching_up')
                    if catching_up:
                        return Result(False, error="Node is still catching up.")
                    if height is not None:
                        return Result(True, height)
                    else:
                        return Result(False, error="Latest block height not found in response.")
                else:
                    return Result(False, error="Unexpected response structure.")
            return Result(False, error="Failed to fetch blockchain status.")

    def get_validators(self, height: int):
        """Fetches validator information for a specific block height."""
        validators_info = []
        page = 1
        per_page = 100
        with NamHTTPClient(base_url=self.rpc_url) as client:
            while True:
                endpoint = f'validators?height={height}&page={page}&per_page={per_page}'
                result = client.send_request(endpoint=endpoint, http_method="GET")
                if not result.success:
                    return Result(False, error=result.error)
                data = result.data
                find_result, validators = find_key(data, 'validators')
                if not find_result:
                    return Result(False, error=data)
                if validators:
                    validators_info.extend(
                        [(validator['address'], validator['voting_power']) for validator in validators])
                    total_validators = int(data['result']['total'])
                    if len(validators_info) >= total_validators:
                        break
                    page += 1
                else:
                    return Result(False, error="JSON data does not contain the required structure.")
        return Result(True, validators_info)

    def _fetch_abci_query_value(self, params):
        """Internal method to fetch and decode the value returned by an ABCI query."""
        with NamHTTPClient(base_url=self.rpc_url) as client:
            result = client.send_json_rpc_request("abci_query", params)
            if result.success:
                find_result, value = find_key(result.data, 'value')
                if not find_result:
                    return Result(False, error="Value not found in the response.")
                if value:
                    return Result(True, base64.b64decode(value))
                else:
                    return Result(False, error=result.data['result']['response']['info'])
            return Result(False, error=result.error)

    def get_validator_from_tm(self, tm_address: str):
        """Converts a Tendermint address to a Namada validator address."""
        params = {"path": f"/vp/pos/validator_by_tm_addr/{tm_address}"}
        result = self._fetch_abci_query_value(params)
        if result.success:
            address_bytes = [1] + list(result.data)[2:]
            validator_address = bech32m_encode('tnam', address_bytes)
            return Result(True, validator_address)
        return Result(False, error=result.error)

    def get_validator_metadata(self, validator_address: str):
        """Fetches and parses metadata for a given validator address."""
        params = {"path": f"/vp/pos/validator/metadata/{validator_address}"}
        result = self._fetch_abci_query_value(params)
        if result.success:
            data = ValidatorMetaData.parse(result.data[1:])
            metadata = {
                'email': data['email'],
                'description': data['description'],
                'website': data['website'],
                'discord_handle': data['discord_handle'],
                'avatar': data['avatar'],
            }
            return Result(True, metadata)
        return Result(False, result.error)

    def get_validator_commission(self, validator_address: str):
        """Fetches and parses commission information for a given validator address."""
        params = {"path": f"/vp/pos/validator/commission/{validator_address}"}
        result = self._fetch_abci_query_value(params)
        if result.success:
            return Result(True, extract_commission_values(result.data))
        return Result(False, result.error)

    def get_validator_state(self, validator_address: str):
        """Fetches and returns the state of a given validator address."""
        params = {"path": f"/vp/pos/validator/state/{validator_address}"}
        result = self._fetch_abci_query_value(params)
        if result.success:
            return Result(True, ValidatorState.parse(result.data[1:]).__class__.__name__)
        return Result(False, error=result.error)
