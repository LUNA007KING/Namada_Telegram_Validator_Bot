from borsh_construct import CStruct, String, Option, Enum, U8

ValidatorMetaData = CStruct(
    'email' / String,
    'description' / Option(String),
    'website' / Option(String),
    'discord_handle' / Option(String),
    'avatar' / Option(String),
)

ValidatorState = Enum(
    "Consensus",
    "BelowCapacity",
    "BelowThreshold",
    "Inactive",
    "Jailed",
    enum_name="ValidatorState",
)

Address = CStruct('data' / U8[21])
