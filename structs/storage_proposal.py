from construct import Struct, GreedyBytes, Byte, Container
from borsh_construct import CStruct, U8, Vec, U64, String
from construct.core import Int64ul  # Use for direct integer parsing
from basic import Address
from bech32m import bech32m_encode

# This feature is not implemented due to issues with parsing the ProposalType.
StorageProposal = Struct(
    'id' / U64,
    'content' / Vec(CStruct('key' / String, 'value' / String)),
    'author' / Address,
    "rest_bytes" / GreedyBytes,
)


def parse_storage_proposal(data):
    initial_parse = StorageProposal.parse(data)

    # Extract fixed known fields from the end of rest_bytes
    end_fields_length = 8 * 3
    end_fields_bytes = initial_parse.rest_bytes[-end_fields_length:]
    voting_start_epoch, voting_end_epoch, grace_epoch = Int64ul[3].parse(end_fields_bytes)

    # Process the remaining part of rest_bytes before these known fields
    type_data_bytes = initial_parse.rest_bytes[:-end_fields_length]

    # Here you'd implement your logic based on the specific structure of type_data
    # For demonstration purposes, let's return the raw bytes
    # You would replace this with actual parsing logic based on 'type'
    type_data_parsed = type_data_bytes

    bytes_list = list(initial_parse.author.data)
    bytes_list[0] ^= 1
    author = bech32m_encode('tnam', bytes_list)

    # Constructing and returning a dictionary with properly parsed fields
    result = {
        'id': initial_parse.id,
        'content': {item.key: item.value for item in initial_parse.content},
        'author': author,
        'type_data': type_data_parsed,  # Placeholder for the actual parsed structure or interpretation
        'voting_start_epoch': voting_start_epoch,
        'voting_end_epoch': voting_end_epoch,
        'grace_epoch': grace_epoch,
    }

    return result



